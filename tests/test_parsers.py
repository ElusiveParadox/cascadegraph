import pytest
from hypothesis import given
from hypothesis import strategies as st

from cascadegraph_runtime.parsers import duration_ms, istio_policies, python_policies
from cascadegraph_runtime.security import InputError, safe_yaml


@given(st.integers(min_value=1, max_value=100))
def test_attempt_semantics(n):
    ten = python_policies("client.py", f"from tenacity import retry, stop_after_attempt\n@retry(stop=stop_after_attempt({n}))\ndef call(): pass")[0]
    url = python_policies("client.py", f"from urllib3.util import Retry\nP = Retry(total={n})")[0]
    assert ten.max_total_attempts == n
    assert url.max_total_attempts == n + 1
    assert ten.source_semantics != url.source_semantics


def test_aliases_and_dynamic_values():
    p = python_policies("x.py", "from urllib3.util import Retry as R\nP = R(total=os.getenv('COUNT'),backoff_factor=1,allowed_methods=['POST'],status_forcelist=[503])")[0]
    assert p.max_total_attempts is None
    assert p.unresolved
    assert p.allowed_methods == ["POST"]
    assert p.evidence[0].line_start == 2


def test_no_false_unimported_retry():
    assert python_policies("x.py", "Retry(total=3)") == []


def test_category_limits_and_timeout():
    p = python_policies("x.py", "from urllib3.util import Retry\nP=Retry(total=3,status=1,read=0,status_forcelist=[503])\nsession.get(url, timeout=0.2)")[0]
    assert p.category_limits == {"status": 1, "read": 0}
    assert p.per_attempt_timeout_ms == 200


def test_tenacity_backoff_and_condition():
    p = python_policies("x.py", "import tenacity as t\n@t.retry(stop=t.stop_after_attempt(3),wait=t.wait_exponential(multiplier=0.5,max=3),retry=t.retry_if_exception_type(TimeoutError))\ndef call(): pass")[0]
    assert p.backoff.delay_ms == 500
    assert p.backoff.cap_ms == 3000
    assert p.retry_on == ["timeout"]


def test_istio_retries_not_total():
    p = istio_policies("mesh.yml", "kind: VirtualService\nspec:\n  http:\n    - timeout: 2s\n      retries:\n        attempts: 3\n        perTryTimeout: 100ms\n        retryOn: 5xx,connect-failure\n")[0]
    assert p.max_total_attempts == 4
    assert p.per_attempt_timeout_ms == 100
    assert p.overall_deadline_ms == 2000
    assert p.backoff.kind == "unknown"


@pytest.mark.parametrize("text", ["a: 1\na: 2", "a: &a [1]\nb: *a", "a: !!python/object:os.system {}", "[", "{1: x}"])
def test_unsafe_yaml_rejected(text):
    with pytest.raises(InputError):
        safe_yaml(text)


@pytest.mark.parametrize("duration,expected", [("1s", 1000), ("2.5ms", 2.5), ("2m", 120000), ("${TIMEOUT}", None), ("-1s", None)])
def test_duration(duration, expected):
    assert duration_ms(duration) == expected


def test_dynamic_stop_not_guessed():
    p = python_policies("x.py", "from tenacity import retry,stop_after_attempt\n@retry(stop=stop_after_attempt(RETRIES))\ndef f():pass")[0]
    assert p.max_total_attempts is None
    assert p.resolution_status == "partially_resolved"
