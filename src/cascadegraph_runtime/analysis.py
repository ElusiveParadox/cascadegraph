"""Orchestration of bounded parsers and provenance-preserving graph binding."""

import ast
import posixpath
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from urllib.parse import urlparse

from .ai import extract_custom_loop
from .models import Analysis, DependencyEdge, Finding, ServiceNode
from .parsers import evidence, istio_policies, python_policies, yaml_service_evidence
from .security import InputError, digest, safe_yaml


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def add_finding(a, title, detail, severity="warning"):
    a.findings.append(Finding(title=title, detail=detail, severity=severity))


def refresh_policy_findings(a: Analysis) -> None:
    """Regenerate derived statements after review without altering source facts."""
    a.findings = [
        f for f in a.findings
        if f.title not in {"Policy needs review", "Multiple attempts configured"}
    ]
    for policy in a.policies:
        if policy.unresolved:
            add_finding(a, "Policy needs review", f"{policy.framework} {policy.symbol}: {'; '.join(policy.unresolved)}")
        if policy.max_total_attempts is not None and policy.max_total_attempts >= 3:
            qualifier = "Reviewer-confirmed" if policy.confirmed else "Extracted"
            add_finding(a, "Multiple attempts configured",
                        f"{qualifier} {policy.symbol} permits up to {policy.max_total_attempts} total attempts; amplification depends on eligibility, deadlines and topology.",
                        "info")
    a.status = "partial" if any(f.severity in {"warning", "error"} for f in a.findings) else "succeeded"


async def analyze(files: dict[str, str], name: str, source_type: str, use_ai=False, provider=None) -> Analysis:
    started = time.monotonic()
    a = Analysis(
        id=str(uuid.uuid4()), name=name, source_type=source_type, status="succeeded",
        created_at=utcnow(), expires_at=(datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        file_count=len(files), fingerprint=digest("".join(p + digest(t) for p, t in sorted(files.items()))),
        stages=["Input bounded and filtered"],
        assumptions=[
            "Static references and explicit declarations are not observations of runtime traffic.",
            "Uploaded source is parsed as data, never executed. Raw upload bytes are not retained.",
            "Analyses expire after 24 hours; demo filesystem storage is not durable production storage.",
        ],
    )
    compose_paths = [p for p in files if PurePosixPath(p).name in {"compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"}]
    services = {}
    contexts = {}
    compose_source = None
    if len(compose_paths) == 1:
        compose_source = compose_paths[0]
        try:
            data = safe_yaml(files[compose_source])
            services = data.get("services", {}) if isinstance(data, dict) else {}
            if not isinstance(services, dict) or len(services) > 20:
                raise InputError("Compose must contain at most 20 services")
            for key, service in services.items():
                if not isinstance(service, dict) or len(key) > 80:
                    raise InputError("Unsupported Compose service shape")
                dep = service.get("depends_on", [])
                if not isinstance(dep, (dict, list)):
                    raise InputError("Unsupported depends_on shape")
                a.nodes.append(ServiceNode(id=key, name=key, startup_dependencies=list(dep),
                    evidence=[yaml_service_evidence(compose_source, files[compose_source], key)]))
                build = service.get("build", key)
                relative = build.get("context", key) if isinstance(build, dict) else str(build)
                if not isinstance(relative, str) or "://" in relative or relative.startswith("/"):
                    add_finding(a, "Unsupported build context", f"{key}: provide local source files for this service")
                    continue
                context = posixpath.normpath(str(PurePosixPath(compose_source).parent / relative))
                if context == ".." or context.startswith("../"):
                    add_finding(a, "Unsupported build context", f"{key}: build context escapes the submitted project")
                    continue
                contexts[key] = context
        except InputError as exc:
            add_finding(a, "Compose could not be parsed", str(exc), "error")
    else:
        add_finding(a, "Select one Compose file", "No Compose file found." if not compose_paths else "Multiple Compose files are ambiguous; upload a single supported application.", "error")
    a.stages.append("Compose services parsed")
    for path, text in sorted(files.items()):
        if time.monotonic() - started > 20:
            raise InputError("Deterministic parsing exceeded 20 seconds")
        try:
            if path.endswith(".py"):
                parsed = python_policies(path, text)
                custom = await extract_custom_loop(path, text, use_ai, provider)
                if custom:
                    parsed.append(custom)
                for p in parsed:
                    matches = [key for key, context in contexts.items() if context == "." or path.startswith(context + "/")]
                    p.service_id = matches[0] if len(matches) == 1 else None
                a.policies.extend(parsed)
            elif path.endswith((".yml", ".yaml")) and path not in compose_paths and PurePosixPath(path).name != "cascadegraph.yaml":
                a.policies.extend(istio_policies(path, text))
        except (InputError, SyntaxError, ValueError, TypeError, AttributeError) as exc:
            add_finding(a, "Unsupported source file", f"{path}: {str(exc)[:200]}")
    if len(a.policies) > 100:
        raise InputError("At most 100 policies are supported")
    a.stages.append("Supported policies extracted with source evidence")
    declared = [p for p in files if PurePosixPath(p).name == "cascadegraph.yaml"]
    if len(declared) > 1:
        raise InputError("Multiple topology declarations are ambiguous")
    if declared:
        path = declared[0]
        data = safe_yaml(files[path])
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("edges"), list):
            raise InputError("cascadegraph.yaml requires version: 1 and an edges list")
        for item in data["edges"]:
            if not isinstance(item, dict) or item.get("source") not in services or item.get("target") not in services:
                raise InputError("Declared edge must reference existing Compose services")
            eid = f"{item['source']}--{item['target']}"
            if any(e.id == eid for e in a.edges):
                raise InputError("Duplicate declared edge")
            edge = DependencyEdge(id=eid, source=item["source"], target=item["target"],
                evidence_kind="explicit_topology", evidence=[evidence(path, files[path], 1, len(files[path].splitlines()))])
            for symbol in item.get("policy_symbols", []):
                matches = [p for p in a.policies if p.symbol == symbol and p.service_id == edge.source]
                if len(matches) != 1:
                    add_finding(a, "Unresolved policy binding", f"{eid}: {symbol} does not identify exactly one caller policy", "error")
                    continue
                policy = matches[0]
                if policy.edge_id:
                    raise InputError("One policy cannot be silently bound to multiple call sites")
                policy.edge_id = eid
                edge.policy_ids.append(policy.id)
            a.edges.append(edge)
    # A supported endpoint variable plus a supported client call is inferred,
    # never the Compose startup dependency alone.
    if compose_source and not declared:
        for caller, config in services.items():
            env = config.get("environment", {})
            if isinstance(env, list):
                env = dict(s.split("=", 1) for s in env if isinstance(s, str) and "=" in s)
            if not isinstance(env, dict):
                continue
            for var, value in env.items():
                if not isinstance(value, str) or not var.endswith("_URL"):
                    continue
                target = urlparse(value).hostname
                if target not in services:
                    add_finding(a, "Unresolved endpoint", f"{caller}: {var} does not resolve to a Compose service")
                    continue
                for pth, text in files.items():
                    if not pth.endswith(".py") or not pth.startswith(contexts[caller] + "/"):
                        continue
                    try:
                        tree = ast.parse(text)
                    except SyntaxError:
                        continue
                    env_call = any(isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == var
                                   and ast.unparse(n.value) == "os.environ" for n in ast.walk(tree))
                    client = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                 and n.func.attr in {"get", "post", "request"}
                                 and n.args and isinstance(n.args[0], ast.Subscript)
                                 and ast.unparse(n.args[0].value) == "os.environ"
                                 and isinstance(n.args[0].slice, ast.Constant) and n.args[0].slice.value == var
                                 for n in ast.walk(tree))
                    if env_call and client and not any(e.source == caller and e.target == target for e in a.edges):
                        a.edges.append(DependencyEdge(id=f"{caller}--{target}", source=caller, target=target,
                            evidence_kind="static_endpoint_reference", evidence=[
                                yaml_service_evidence(compose_source, files[compose_source], caller), evidence(pth, text)]))
                        add_finding(a, "Policy binding needs declaration", f"{caller} → {target} is inferred; add cascadegraph.yaml policy_symbols to bind the retry call boundary.")
    if len(a.edges) > 40:
        raise InputError("At most 40 call edges are supported")
    if not a.edges:
        add_finding(a, "No evidence-backed call edges", "Startup dependencies do not prove communication. Supply explicit topology or supported endpoint references.", "error")
    a.stages.extend(["Original retry semantics normalized", "Evidence-labelled graph assembled"])
    a.service_count, a.policy_count = len(a.nodes), len(a.policies)
    refresh_policy_findings(a)
    if len(compose_paths) != 1 or not a.nodes:
        a.requested_files.append("Provide one compose.yaml/docker-compose.yml defining the services, or select its project folder.")
    if a.nodes and not a.edges:
        a.requested_files.append("Provide cascadegraph.yaml with explicit service-to-service edges and policy_symbols, or supported client endpoint references.")
    if not a.policies:
        a.requested_files.append("Provide the Python retry/client source files or Istio VirtualService YAML containing the actual retry policy.")
    if any(p.service_id is None for p in a.policies) and not any(p.edge_id for p in a.policies):
        a.requested_files.append("Provide source files under the service build-context paths declared by Compose so policies can be attributed.")
    if any(f.title == "Unresolved policy binding" for f in a.findings):
        a.requested_files.append("Provide the named retry functions/configurations at their service-relative paths, or correct cascadegraph.yaml policy_symbols.")
    return a
