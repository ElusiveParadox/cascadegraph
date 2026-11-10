"""HTTP boundary for the computational core; no uploaded code is executed."""

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from . import store
from .ai import ai_available
from .analysis import analyze, utcnow
from .models import MODEL_VERSION, Analysis, AnalysisInput, EdgeConfirmation, PolicyConfirmation, Scenario
from .security import MAX_ARCHIVE, MAX_FILES, ROOT, InputError, ingest_zip, redact, sample_files
from .simulation import simulate

logger = logging.getLogger("cascadegraph")
logging.basicConfig(level=logging.INFO, format="%(message)s")
LIMITATIONS = [
    "Supports bounded Python Tenacity/urllib3, Istio VirtualService and Compose syntax only.",
    "Custom-loop AI support is restricted to the bundled range-loop pattern and requires explicit opt-in.",
    "No arbitrary URL fetching or private repository ingestion. Use a bounded ZIP archive.",
    "SQLite demo storage may reset on republish; export reports. Analyses expire after 24 hours.",
    "The simulator supports acyclic call paths and sequential fan-out, not arbitrary production behavior.",
    "Measured validation describes only the committed sample and matching CI scenarios, never an uploaded application.",
]


class SafetyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.rates = defaultdict(deque)
        self.semaphore = asyncio.Semaphore(2)

    async def dispatch(self, request, call_next):
        correlation = str(uuid.uuid4())
        started = time.monotonic()
        mutating = request.method in {"POST", "PATCH", "DELETE"}
        origin = request.headers.get("origin")
        if mutating and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"error": "Cross-origin mutation rejected", "code": "ORIGIN_REJECTED"}, 403)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"error": "Invalid Content-Length"}, 400)
        if length < 0 or length > MAX_ARCHIVE + 65536:
            return JSONResponse({"error": "Upload exceeds 5 MiB", "code": "INPUT_TOO_LARGE"}, 413)
        # Read with a hard limit, including chunked requests, before multipart parsing.
        if mutating:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_ARCHIVE + 65536:
                    return JSONResponse({"error": "Request body exceeds limit"}, 413)
            request._body = bytes(body)
        peer = request.client.host if request.client else "unknown"
        now = time.monotonic()
        reads = self.rates["all:" + peer]
        while reads and reads[0] < now - 60:
            reads.popleft()
        if len(reads) >= 240:
            return JSONResponse({"error": "Request limit reached. Retry in one minute."}, 429)
        reads.append(now)
        token = request.cookies.get("cg_session", "")
        if len(token) > 64:
            token = ""
        new = not token or not store.session_exists(token)
        if new:
            try:
                token = store.create_session()
            except ValueError:
                return JSONResponse({"error": "Demo session capacity reached"}, 429)
        request.state.owner = token
        if mutating:
            # Peer+session limits prevent bypass by discarding the cookie.
            peer = request.client.host if request.client else "unknown"
            now = time.monotonic()
            for key in ("ip:" + peer, "session:" + token):
                q = self.rates[key]
                while q and q[0] < now - 60:
                    q.popleft()
                if len(q) >= (60 if key.startswith("ip:") else 20):
                    return JSONResponse({"error": "Too many requests. Retry in one minute.", "code": "RATE_LIMITED"}, 429)
                q.append(now)
            if len(self.rates) > 10000:
                self.rates = defaultdict(deque, {k: v for k, v in self.rates.items() if v and v[-1] > now - 60})
        try:
            if mutating:
                async with self.semaphore:
                    response = await call_next(request)
            else:
                response = await call_next(request)
        except Exception:
            logger.error(json.dumps({"correlation_id": correlation, "event": "unexpected_error"}))
            response = JSONResponse({"error": "Operation failed; retry or inspect the supported input format.", "code": "INTERNAL_ERROR", "correlation_id": correlation}, 500)
        if new:
            secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
            response.set_cookie("cg_session", token, max_age=86400, httponly=True, secure=secure, samesite="strict", path="/api")
        response.headers.update({
            "X-Correlation-ID": correlation, "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        })
        logger.info(json.dumps({"correlation_id": correlation, "method": request.method,
                               "status": response.status_code, "duration_ms": round((time.monotonic() - started) * 1000)}))
        return response


app = FastAPI(title="CascadeGraph", version="1.0.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(SafetyMiddleware)


@app.exception_handler(InputError)
async def bad_input(request, exc):
    return JSONResponse({"error": str(exc), "code": "UNSUPPORTED_INPUT"}, 422)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # FastAPI's default error includes raw input values; avoid echoing secrets.
    return JSONResponse({"error": "Invalid request fields", "code": "VALIDATION_ERROR",
                         "fields": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]}, 422)


def owned(request, aid) -> Analysis:
    data = store.get_analysis(request.state.owner, aid)
    if not data:
        raise HTTPException(404, detail="Analysis not found or expired")
    return Analysis.model_validate(data)


@app.get("/api/healthz", operation_id="healthCheck")
@app.get("/api/v1/health/live")
def health():
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def ready():
    with store.database() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/v1/status", operation_id="getSystemStatus")
def system_status():
    return dict(version="1.0.0", model_version=MODEL_VERSION, ai_available=ai_available(),
                ai_provider=os.getenv("LLM_PROVIDER", "replit_openai"),
                storage="SQLite · session-owned · 24-hour retention · ephemeral demo",
                supported_parsers=["Docker Compose", "Tenacity", "urllib3 / requests", "Istio VirtualService", "Sample custom loop (opt-in AI)"],
                limitations=LIMITATIONS, max_archive_mb=5, max_files=MAX_FILES)


@app.get("/api/v1/analyses", operation_id="listAnalyses")
def list_runs(request: Request):
    keys = {"id", "name", "source_type", "status", "created_at", "expires_at", "file_count", "service_count", "policy_count"}
    return [{k: v for k, v in row.items() if k in keys} for row in store.list_analyses(request.state.owner)]


@app.post("/api/v1/analyses", status_code=201, operation_id="createAnalysis")
async def create_run(data: AnalysisInput, request: Request):
    result = await asyncio.wait_for(analyze(sample_files(), "Checkout reliability sample", "sample", data.use_ai), 90)
    try:
        store.save_analysis(request.state.owner, result.model_dump())
    except ValueError as exc:
        raise InputError(str(exc)) from exc
    return result


@app.post("/api/v1/analyses/archive", status_code=201, operation_id="uploadArchive")
async def upload(request: Request, file: UploadFile = File(...), use_ai: bool = Form(False)):
    try:
        raw = await file.read(MAX_ARCHIVE + 1)
        files = ingest_zip(raw)
        result = await asyncio.wait_for(analyze(files, "Uploaded repository", "archive", use_ai), 90)
        store.save_analysis(request.state.owner, result.model_dump())
        return result
    except ValueError as exc:
        raise InputError(str(exc)) from exc
    finally:
        await file.close()


@app.get("/api/v1/analyses/{analysisId}", operation_id="getAnalysis")
def analysis_detail(analysisId: str, request: Request):
    return owned(request, analysisId)


@app.delete("/api/v1/analyses/{analysisId}", status_code=204, operation_id="deleteAnalysis")
def delete_run(analysisId: str, request: Request):
    owned(request, analysisId)
    store.delete_analysis(request.state.owner, analysisId)
    return Response(status_code=204)


@app.patch("/api/v1/analyses/{analysisId}/policies/{policyId}", operation_id="confirmPolicy")
def confirm_policy(analysisId: str, policyId: str, data: PolicyConfirmation, request: Request):
    a = owned(request, analysisId)
    p = next((p for p in a.policies if p.id == policyId), None)
    if p is None:
        raise HTTPException(404, detail="Policy not found")
    p.max_total_attempts = data.max_total_attempts
    if "per_attempt_timeout_ms" in data.model_fields_set:
        p.per_attempt_timeout_ms = data.per_attempt_timeout_ms
    if "overall_deadline_ms" in data.model_fields_set:
        p.overall_deadline_ms = data.overall_deadline_ms
    p.confirmed, p.confirmation_note = True, redact(data.note)
    p.confidence = "user_confirmed"
    # Original source_value and source evidence remain immutable.
    store.save_analysis(request.state.owner, a.model_dump())
    return a


@app.post("/api/v1/analyses/{analysisId}/edges/{edgeId}/confirm", operation_id="confirmEdge")
def confirm_edge(analysisId: str, edgeId: str, data: EdgeConfirmation, request: Request):
    a = owned(request, analysisId)
    e = next((e for e in a.edges if e.id == edgeId), None)
    if not e:
        raise HTTPException(404, detail="Edge not found")
    e.confirmed, e.confirmation_note = True, redact(data.note)
    store.save_analysis(request.state.owner, a.model_dump())
    return a


@app.post("/api/v1/analyses/{analysisId}/simulations", status_code=201, operation_id="runSimulation")
def run_simulation(analysisId: str, data: Scenario, request: Request):
    a = owned(request, analysisId)
    result = dict(id=str(uuid.uuid4()), analysis_id=a.id, created_at=utcnow(), model_version=MODEL_VERSION,
                  scenario=data.model_dump(), baseline=simulate(a, data),
                  candidate=simulate(a, data, candidate=True) if data.candidate_attempts is not None else None,
                  policies=[p.model_dump() for p in a.policies])
    try:
        store.save_simulation(request.state.owner, result)
    except ValueError as exc:
        raise InputError(str(exc)) from exc
    return result


@app.get("/api/v1/simulations/{simulationId}", operation_id="getSimulation")
def simulation_detail(simulationId: str, request: Request):
    data = store.get_simulation(request.state.owner, simulationId)
    if data is None:
        raise HTTPException(404, detail="Simulation not found or expired")
    return data


def validation_status():
    # Only a release-maintainer verified, tracked sample report is trusted.
    path = ROOT / "validation" / "verified-sample.json"
    if not path.exists():
        return dict(status="unavailable", detail="No verified CI measurement has been bundled. Run the committed Compose validation workflow; simulated values are not measurements.",
                    workflow_url=None, commit_sha=None, measured_at=None, cases=[])
    return json.loads(path.read_text())


@app.get("/api/v1/validation", operation_id="getValidation")
def validation():
    return validation_status()


@app.get("/api/v1/analyses/{analysisId}/report", operation_id="getReport")
def report(analysisId: str, request: Request):
    a = owned(request, analysisId)
    return dict(schema_version="1.0", generated_at=utcnow(), analysis=a,
                simulations=store.simulations(request.state.owner, analysisId),
                measured_validation=validation_status(), limitations=LIMITATIONS)
