"""Conservative AST extraction: unsupported expressions stay unresolved."""

import ast
import re

import yaml

from .models import Backoff, Evidence, Policy
from .security import InputError, digest, redact, safe_yaml


def evidence(path: str, text: str, start: int = 1, end: int | None = None) -> Evidence:
    lines = text.splitlines()
    end = end or start
    return Evidence(
        path=path, line_start=start, line_end=end,
        excerpt=redact("\n".join(lines[start - 1:min(end, start + 14)]))[:1800],
        sha256=digest(text),
    )


def ev_node(path: str, text: str, node: ast.AST) -> Evidence:
    return evidence(path, text, node.lineno, node.end_lineno)


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def duration_ms(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)", value)
    if not match:
        return None
    return float(match[1]) * {"ms": 1, "s": 1000, "m": 60000}[match[2]]


def python_policies(path: str, text: str) -> list[Policy]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, RecursionError) as exc:
        raise InputError(f"Invalid or too deeply nested Python: {path}") from exc
    imports = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for alias in n.names:
                imports[alias.asname or alias.name] = f"{n.module}.{alias.name}"
        elif isinstance(n, ast.Import):
            for alias in n.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]

    def name(n):
        if isinstance(n, ast.Name):
            return imports.get(n.id, n.id)
        if isinstance(n, ast.Attribute):
            return name(n.value) + "." + n.attr
        return ""

    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    policies = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        canonical = name(node.func)
        framework = (
            "tenacity" if canonical == "tenacity.retry"
            else "urllib3" if canonical in {"urllib3.util.retry.Retry", "urllib3.util.Retry", "urllib3.Retry"}
            else None
        )
        if not framework:
            continue
        owner = parents.get(node)
        symbol = owner.name if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
        if isinstance(owner, ast.Assign) and isinstance(owner.targets[0], ast.Name):
            symbol = owner.targets[0].id
        p = Policy(
            id=digest(f"{path}:{node.lineno}:{canonical}")[:24],
            framework=framework, symbol=symbol or f"line_{node.lineno}",
            source_semantics="total_attempts" if framework == "tenacity" else "retries_after_initial",
            evidence=[ev_node(path, text, node)],
        )
        args = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        if framework == "urllib3":
            raw = literal(args.get("total")) if "total" in args else (literal(node.args[0]) if node.args else None)
            # Explicit False disables retries. None means unbounded by this category.
            if raw is False:
                raw = 0
            if type(raw) is int and 0 <= raw <= 100:
                p.source_value, p.max_total_attempts = raw, raw + 1
            else:
                p.unresolved.append("Retry total is missing, unbounded or dynamic")
            for cat in ("connect", "read", "status", "other", "redirect"):
                if cat in args:
                    value = literal(args[cat])
                    if value is False:
                        value = 0
                    if type(value) is int and value >= 0:
                        p.category_limits[cat] = value
                    else:
                        p.unresolved.append(f"{cat} retry budget is unbounded or dynamic")
            statuses = literal(args.get("status_forcelist")) if "status_forcelist" in args else []
            if isinstance(statuses, (list, tuple, set)) and all(type(s) is int for s in statuses):
                p.retry_on = [str(s) for s in sorted(statuses)] + ["connect", "timeout"]
            else:
                p.unresolved.append("status_forcelist is dynamic")
            if "allowed_methods" in args:
                methods = literal(args["allowed_methods"])
                if methods is None and isinstance(args["allowed_methods"], ast.Constant):
                    p.allowed_methods = None
                elif isinstance(methods, (list, tuple, set)) and all(isinstance(m, str) for m in methods):
                    p.allowed_methods = sorted(methods)
                else:
                    p.unresolved.append("allowed_methods is dynamic")
            else:
                p.allowed_methods = ["DELETE", "GET", "HEAD", "OPTIONS", "PUT", "TRACE"]
            factor = literal(args["backoff_factor"]) if "backoff_factor" in args else 0
            jitter = literal(args["backoff_jitter"]) if "backoff_jitter" in args else 0
            if type(factor) in (int, float) and factor >= 0 and type(jitter) in (int, float) and jitter >= 0:
                p.backoff = Backoff(kind="exponential" if factor else "none", delay_ms=factor * 1000, cap_ms=120000, jitter_ms=jitter * 1000)
            else:
                p.unresolved.append("backoff is dynamic")
            if any(k in args for k in ("respect_retry_after_header", "backoff_max")):
                p.unresolved.append("Retry-After/backoff_max overrides require explicit review")
        else:
            stop = args.get("stop")
            if isinstance(stop, ast.Call) and name(stop.func) == "tenacity.stop_after_attempt" and stop.args:
                raw = literal(stop.args[0])
                if type(raw) is int and 1 <= raw <= 100:
                    p.source_value = p.max_total_attempts = raw
                else:
                    p.unresolved.append("Attempt limit is dynamic or outside supported bounds")
            else:
                p.unresolved.append("Missing or unsupported Tenacity stop policy")
            wait = args.get("wait")
            if wait is None:
                p.backoff = Backoff(kind="none", delay_ms=0)
            elif isinstance(wait, ast.Call):
                wa = {k.arg: literal(k.value) for k in wait.keywords}
                first = literal(wait.args[0]) if wait.args else wa.get("multiplier", 1)
                kind = name(wait.func)
                if kind == "tenacity.wait_fixed" and type(first) in (int, float) and first >= 0:
                    p.backoff = Backoff(kind="fixed", delay_ms=first * 1000)
                elif kind in {"tenacity.wait_exponential", "tenacity.wait_random_exponential"} and type(first) in (int, float) and first >= 0 and all(type(v) in (int, float) for v in wa.values()):
                    if wa.get("min", 0) != 0 or wa.get("exp_base", 2) != 2 or kind.endswith("random_exponential"):
                        p.unresolved.append("Tenacity minimum/base/full-jitter wait needs review")
                    else:
                        p.backoff = Backoff(kind="exponential", delay_ms=first * 1000, cap_ms=wa.get("max", 1e6) * 1000)
                else:
                    p.unresolved.append("Unsupported Tenacity wait policy")
            else:
                p.unresolved.append("Dynamic Tenacity wait policy")
            retry = args.get("retry")
            if retry is None:
                p.retry_on = ["exception", "timeout", "connect", "5xx"]
            elif isinstance(retry, ast.Call) and name(retry.func) == "tenacity.retry_if_exception_type" and retry.args:
                expr = ast.unparse(retry.args[0])
                if any(x in expr for x in ("Exception", "HTTPError", "HTTPStatusError")):
                    p.retry_on = ["exception", "timeout", "connect", "5xx"]
                elif "Timeout" in expr:
                    p.retry_on = ["timeout"]
                elif "Connection" in expr or "Connect" in expr:
                    p.retry_on = ["connect"]
                else:
                    p.unresolved.append("Retry exception condition is unsupported")
            else:
                p.unresolved.append("Unsupported Tenacity retry predicate")
        # Only an unambiguous supported client call in the containing function
        # (or Retry module) can supply the request timeout.
        scope = owner if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) else tree
        timeouts = [
            (literal(kw.value), call)
            for call in ast.walk(scope) if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute) and call.func.attr in {"get", "request", "post"}
            for kw in call.keywords if kw.arg == "timeout"
        ]
        if len(timeouts) == 1:
            timeout, call = timeouts[0]
            if type(timeout) in (int, float) and timeout > 0:
                p.per_attempt_timeout_ms = timeout * 1000
                p.evidence.append(ev_node(path, text, call))
            else:
                p.unresolved.append("Client timeout is dynamic or has unsupported connect/read tuple semantics")
        p.resolution_status = "partially_resolved" if p.unresolved else "resolved"
        policies.append(p)
    return policies


def istio_policies(path: str, text: str) -> list[Policy]:
    data = safe_yaml(text)
    if not isinstance(data, dict) or data.get("kind") != "VirtualService":
        return []
    policies = []
    for index, route in enumerate(data.get("spec", {}).get("http", [])):
        if not isinstance(route, dict) or "retries" not in route:
            continue
        r = route["retries"]
        if not isinstance(r, dict):
            raise InputError(f"Invalid Istio retries in {path}")
        raw = r.get("attempts")
        total = raw + 1 if type(raw) is int and 0 <= raw <= 100 else None
        condition = str(r.get("retryOn", ""))
        tokens = [x.strip() for x in condition.split(",") if x.strip()]
        retry_on = [("timeout" if x in {"reset", "cancelled"} else "connect" if x == "connect-failure" else x) for x in tokens]
        unresolved = [] if total is not None else ["Unknown Istio attempt count"]
        if not tokens:
            unresolved.append("Implicit Istio retry conditions are not modeled")
        timeout, deadline = duration_ms(r.get("perTryTimeout")), duration_ms(route.get("timeout"))
        if "perTryTimeout" in r and timeout is None:
            unresolved.append("Unsupported perTryTimeout")
        if "timeout" in route and deadline is None:
            unresolved.append("Unsupported route timeout")
        # Istio default backoff is runtime/version dependent: do not invent it.
        unresolved.append("Istio proxy backoff is not statically configured; supply a confirmed policy before binding")
        line = next((i + 1 for i, source_line in enumerate(text.splitlines()) if "attempts:" in source_line), 1)
        policies.append(Policy(
            id=digest(f"{path}:istio:{index}")[:24], framework="istio", symbol=f"route_{index}",
            source_semantics="istio_retry_count", source_value=raw if type(raw) is int else None,
            max_total_attempts=total, retry_on=retry_on, per_attempt_timeout_ms=timeout,
            overall_deadline_ms=deadline, evidence=[evidence(path, text, line, min(line + 4, len(text.splitlines())))],
            extraction_method="yaml", resolution_status="partially_resolved", unresolved=unresolved,
        ))
    return policies


def yaml_service_evidence(path: str, text: str, service: str) -> Evidence:
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            if key.value == "services" and isinstance(value, yaml.MappingNode):
                for sk, sv in value.value:
                    if sk.value == service:
                        return evidence(path, text, sk.start_mark.line + 1, sv.end_mark.line)
    return evidence(path, text)
