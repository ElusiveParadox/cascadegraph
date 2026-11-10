import os

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed


@retry(stop=stop_after_attempt(3), wait=wait_fixed(0.05),
       retry=retry_if_exception_type(requests.RequestException), reraise=True)
def call_order(run_id, logical_id):
    response = requests.get(
        os.environ["ORDER_URL"] + "/order",
        headers={"X-CascadeGraph-Run-ID": run_id, "X-CascadeGraph-Logical-Request-ID": logical_id},
        timeout=0.5,
    )
    response.raise_for_status()
    return response.json()
