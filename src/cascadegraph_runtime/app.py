"""HTTP boundary for the computational core; no uploaded code is executed."""

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from . import github_access, store
from .ai import ai_available
from .analysis import analyze, refresh_policy_findings, utcnow
from .github_routes import router as github_router
from .models import (
    MODEL_VERSION,
    Analysis,
    AnalysisInput,
    EdgeConfirmation,
    PolicyConfirmation,
    RepositoryInput,
    Scenario,
)
from .repository import fetch_repository, parse_repository_url
from .security import (
    MAX_ARCHIVE,
    MAX_BODY,
    MAX_EXPANDED,
    MAX_FILE,
    MAX_FILES,
    MAX_SOURCE,
    ROOT,
    InputError,
    ingest_zip,
    redact,
    sample_files,
    select_project,
    validate_source_path,
    validate_sources,
)
from .simulation import simulate
from .storage_connection import StorageUnavailable

logger = logging.getLogger("cascadegraph")
logging.basicConfig(level=logging.INFO, format="%(message)s")
LIMITATIONS = [
    "Supports bounded Python Tenacity/urllib3, Istio VirtualService and Compose syntax only.",
    "Custom-loop AI support is restricted to the bundled range-loop pattern and requires explicit opt-in.",
    "GitHub root URLs only. Private imports require your own read-only GitHub App authorization on selected repositories; uploads remain available.",
    "Analyses expire after 24 hours; anonymous history requires the original browser cookie. GitHub sign-in uses separate account-owned history.",
    "The simulator supports acyclic call paths and sequential fan-out, not arbitrary production behavior.",
    "Measured validation describes only the committed sample and matching CI scenarios, never an uploaded application.",
]


def storage_unavailable(correlation):
    # A lost COMMIT acknowledgement can leave a successful write. Do not advise
    # blindly retrying a mutation or pretend every 503 means it rolled back.
    return JSONResponse({
        "error": "History storage unavailable. Check history after recovery before retrying; no local fallback was used.",
        "code": "STORAGE_UNAVAILABLE", "correlation_id": correlation,
    }, 503, headers={"Cache-Control": "no-store", "X-Correlation-ID": correlation,
                    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})


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
        body_limit = MAX_BODY if request.url.path in {"/api/v1/analyses/archive", "/api/v1/analyses/sources"} else 65536
        if length < 0 or length > body_limit:
            return JSONResponse({"error": "Request exceeds its input limit; ZIP/source uploads allow 50 MiB plus multipart overhead", "code": "INPUT_TOO_LARGE"}, 413)
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
        try:
            new = not token or not store.session_exists(token)
            if new:
                token = store.create_session()
        except ValueError:
            return JSONResponse({"error": "Demo session capacity reached"}, 429)
        except Exception:
            logger.error(json.dumps({"correlation_id": correlation, "event": "storage_unavailable"}))
            return storage_unavailable(correlation)
        request.state.owner = token
        try:
            github_user = (None if request.method == "DELETE" and request.url.path == "/api/v1/github/connection"
                           else github_access.identity(request.cookies.get("cg_github", "")))
        except StorageUnavailable:
            logger.error(json.dumps({"correlation_id": correlation, "event": "storage_unavailable"}))
            return storage_unavailable(correlation)
        except HTTPException as exc:
            return JSONResponse({"error": exc.detail}, exc.status_code)
        if github_user:
            request.state.owner = github_user.owner
        if mutating:
            # Peer+session limits prevent bypass by discarding the cookie.
            peer = request.client.host if request.client else "unknown"
            now = time.monotonic()
            for key in ("ip:" + peer, "session:" + request.state.owner):
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
                try:
                    await asyncio.wait_for(self.semaphore.acquire(), timeout=2)
                except TimeoutError:
                    raise HTTPException(429, detail="Analysis capacity is busy; retry shortly") from None
                try:
                    # Hold admission while buffering/parsing, not only during analysis.
                    async def read_body():
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > body_limit:
                                raise HTTPException(413, detail="Request body exceeds the upload limit")
                        request._body = bytes(body)
                    try:
                        await asyncio.wait_for(read_body(), timeout=30)
                    except TimeoutError:
                        raise HTTPException(408, detail="Upload timed out; retry with the relevant source files") from None
                    response = await call_next(request)
                finally:
                    self.semaphore.release()
            else:
                response = await call_next(request)
        except StorageUnavailable:
            logger.error(json.dumps({"correlation_id": correlation, "event": "storage_unavailable"}))
            response = storage_unavailable(correlation)
        except HTTPException as exc:
            response = JSONResponse({"error": exc.detail}, exc.status_code)
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


@asynccontextmanager
async def lifespan(app):
    # No production schema mutation. Fail closed if PostgreSQL is unconfigured.
    await asyncio.to_thread(store.purge)

    async def retention():
        while True:
            await asyncio.sleep(60)
            try:
                await asyncio.to_thread(store.purge)
                await asyncio.to_thread(github_access.prune)
            except Exception:
                logger.error('{"event":"retention_cleanup_failed"}')

    task = asyncio.create_task(retention())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        # Durable encrypted authorization is not a process-owned resource.
        # Shutdown must not disconnect other replicas or returning users.


app = FastAPI(title="CascadeGraph", version="1.0.0", docs_url="/api/docs", lifespan=lifespan,
              openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(SafetyMiddleware)
app.include_router(github_router)


@app.exception_handler(InputError)
async def bad_input(request, exc):
    return JSONResponse({"error": str(exc), "code": "UNSUPPORTED_INPUT"}, 422)


@app.exception_handler(PermissionError)
async def unavailable_record(request, exc):
    return JSONResponse({"error": "Analysis not found or expired"}, 404)


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
    limitations = list(LIMITATIONS)
    if store.backend() == "sqlite":
        limitations.append("SQLite demo storage may reset on republish; export reports.")
    return dict(version="1.0.0", model_version=MODEL_VERSION, ai_available=ai_available(),
                ai_provider=os.getenv("LLM_PROVIDER", "replit_openai"),
                storage=store.description(),
                supported_parsers=["Docker Compose", "Tenacity", "urllib3 / requests", "Istio VirtualService", "Sample custom loop (opt-in AI)"],
                limitations=limitations, max_archive_mb=MAX_ARCHIVE // (1024 * 1024), max_files=MAX_FILES,
                max_expanded_mb=MAX_EXPANDED // (1024 * 1024), max_source_mb=MAX_SOURCE // (1024 * 1024),
                max_file_kb=MAX_FILE // 1024, max_source_files=100)


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
async def upload(request: Request, file: UploadFile = File(...), use_ai: bool = Form(False), project_path: str = Form(".", max_length=200)):
    try:
        raw = await file.read(MAX_ARCHIVE + 1)
        files = ingest_zip(raw)
        result = await analyze_submission(request, files, "Uploaded repository", "archive", use_ai, project_path)
        return result
    except ValueError as exc:
        raise InputError(str(exc)) from exc
    finally:
        await file.close()


async def analyze_submission(request, files, name, source_type, use_ai, project_path=".", repository=None):
    files = select_project(validate_sources(files), project_path)
    try:
        result = await asyncio.wait_for(analyze(files, name, source_type, use_ai), 90)
    except TimeoutError:
        raise InputError("Analysis exceeded its time budget. Select a smaller project folder or upload relevant source files") from None
    result.repository = repository
    if repository:
        repository.project_path = project_path.strip() or "."
        result.assumptions.append(f"GitHub snapshot pinned to commit {repository.commit_sha}; no repository code was executed.")
        if repository.supplemented_paths:
            result.assumptions.append("User-uploaded source supplements/overrides repository paths; those excerpts are not claimed to originate from the pinned commit.")
    try:
        store.save_analysis(request.state.owner, result.model_dump())
    except ValueError as exc:
        raise InputError(str(exc)) from exc
    return result


@app.post("/api/v1/analyses/repository", status_code=201, operation_id="analyzeRepository")
async def repository_analysis(data: RepositoryInput, request: Request):
    files, repository = await fetch_for_user(request, data.repository_url, data.ref, data.private_access)
    return await analyze_submission(request, files, repository.repository_url, "github", data.use_ai,
                                    data.project_path, repository)


async def fetch_for_user(request, repository_url, ref, private_access):
    if not private_access:
        return await fetch_repository(repository_url, ref)
    owner, repo, _ = parse_repository_url(repository_url)
    try:
        async with asyncio.timeout(45):
            token = await github_access.authorized_token(request.cookies.get("cg_github", ""), owner, repo)
            return await fetch_repository(repository_url, ref, access_token=token)
    except TimeoutError:
        raise InputError("GitHub authorization/import timed out. Retry or upload the relevant source files.") from None


@app.post("/api/v1/analyses/sources", status_code=201, operation_id="analyzeSources")
async def source_analysis(
    request: Request, files: list[UploadFile] = File(...), paths: list[str] | None = Form(None),
    repository_url: str = Form("", max_length=300), ref: str = Form("", max_length=200),
    project_path: str = Form(".", max_length=200), use_ai: bool = Form(False), private_access: bool = Form(False),
):
    try:
        if not 1 <= len(files) <= 100 or paths is not None and len(paths) != len(files):
            raise InputError("Provide 1–100 source files with one relative path per file")
        source = {}
        for index, file in enumerate(files):
            path = validate_source_path(paths[index] if paths is not None else file.filename or "")
            if path in source:
                raise InputError("Duplicate uploaded source path")
            raw = await file.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE:
                raise InputError("A supported source file exceeds 512 KiB")
            try:
                source[path] = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise InputError("Source files must be UTF-8 text") from None
        validate_sources(source)
        repository = None
        if repository_url.strip():
            base, repository = await fetch_for_user(request, repository_url, ref, private_access)
            repository.supplemented_paths = sorted(source)
            base.update(source)
            source = base
        return await analyze_submission(request, source, "Uploaded source files" if not repository else repository.repository_url,
                                        "source_files" if not repository else "github_with_sources", use_ai, project_path, repository)
    finally:
        for file in files:
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
    refresh_policy_findings(a)
    store.save_analysis(request.state.owner, a.model_dump(), update_only=True)
    return a


@app.post("/api/v1/analyses/{analysisId}/edges/{edgeId}/confirm", operation_id="confirmEdge")
def confirm_edge(analysisId: str, edgeId: str, data: EdgeConfirmation, request: Request):
    a = owned(request, analysisId)
    e = next((e for e in a.edges if e.id == edgeId), None)
    if not e:
        raise HTTPException(404, detail="Edge not found")
    e.confirmed, e.confirmation_note = True, redact(data.note)
    store.save_analysis(request.state.owner, a.model_dump(), update_only=True)
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
