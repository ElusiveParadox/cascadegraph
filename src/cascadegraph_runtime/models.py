"""Versioned domain contracts. None is unknown, never an implied default."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MODEL_VERSION = "des-1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(StrictModel):
    path: str
    line_start: int
    line_end: int
    excerpt: str
    sha256: str


class Backoff(StrictModel):
    kind: Literal["none", "fixed", "exponential", "unknown"] = "unknown"
    delay_ms: float | None = None
    multiplier: float = 2
    cap_ms: float | None = None
    jitter_ms: float = 0


class Policy(StrictModel):
    id: str
    framework: str
    symbol: str
    service_id: str | None = None
    edge_id: str | None = None
    source_semantics: str
    source_value: int | None = None
    max_total_attempts: int | None = None
    retry_on: list[str] = Field(default_factory=list)
    backoff: Backoff = Field(default_factory=Backoff)
    per_attempt_timeout_ms: float | None = None
    overall_deadline_ms: float | None = None
    resolution_status: str = "unresolved"
    extraction_method: str = "python_ast"
    confidence: str = "deterministic"
    evidence: list[Evidence] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    confirmed: bool = False
    confirmation_note: str | None = None
    category_limits: dict[str, int | None] = Field(default_factory=dict)
    allowed_methods: list[str] | None = None


class ServiceNode(StrictModel):
    id: str
    name: str
    startup_dependencies: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class DependencyEdge(StrictModel):
    id: str
    source: str
    target: str
    evidence_kind: str
    confirmed: bool = False
    policy_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confirmation_note: str | None = None


class Finding(StrictModel):
    severity: str
    title: str
    detail: str


class RepositorySource(StrictModel):
    repository_url: str
    commit_sha: str
    ref: str
    project_path: str = "."
    supplemented_paths: list[str] = Field(default_factory=list)


class Analysis(StrictModel):
    id: str
    name: str
    source_type: str
    status: str
    created_at: str
    expires_at: str
    file_count: int
    service_count: int = 0
    policy_count: int = 0
    fingerprint: str
    repository: RepositorySource | None = None
    requested_files: list[str] = Field(default_factory=list)
    nodes: list[ServiceNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class AnalysisInput(StrictModel):
    source_type: Literal["sample"]
    use_ai: bool = False


class RepositoryInput(StrictModel):
    repository_url: str = Field(min_length=10, max_length=300)
    ref: str = Field(default="", max_length=200)
    project_path: str = Field(default=".", max_length=200)
    use_ai: bool = False


class PolicyConfirmation(StrictModel):
    max_total_attempts: int = Field(ge=1, le=10, strict=True)
    note: str = Field(min_length=3, max_length=300)
    per_attempt_timeout_ms: float | None = Field(default=None, ge=1, le=60000)
    overall_deadline_ms: float | None = Field(default=None, ge=1, le=120000)


class EdgeConfirmation(StrictModel):
    note: str = Field(min_length=3, max_length=300)


class Scenario(StrictModel):
    name: str = Field(default="Downstream failure", min_length=1, max_length=80)
    mode: Literal["healthy", "latency", "timeout", "intermittent", "correlated"] = "intermittent"
    seed: int = Field(default=42, ge=0, le=2147483647, strict=True)
    requests: int = Field(default=50, ge=1, le=500, strict=True)
    arrival_rate: float = Field(default=5, ge=0.1, le=100)
    service_time_ms: float = Field(default=20, ge=1, le=5000)
    fault_latency_ms: float = Field(default=200, ge=0, le=10000)
    failure_rate: float = Field(default=0.5, ge=0, le=1)
    per_attempt_timeout_ms: float = Field(default=500, ge=1, le=10000)
    deadline_ms: float = Field(default=5000, ge=1, le=60000)
    concurrency: int = Field(default=10, ge=1, le=100, strict=True)
    queue_limit: int = Field(default=50, ge=0, le=1000, strict=True)
    candidate_attempts: int | None = Field(default=None, ge=1, le=10, strict=True)
    candidate_backoff_ms: float = Field(default=100, ge=0, le=5000)
    candidate_jitter_ms: float = Field(default=25, ge=0, le=5000)
    entry_service: str | None = None
