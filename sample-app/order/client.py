import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

INVENTORY_RETRY = Retry(total=2, connect=2, read=2, status=2,
                        backoff_factor=0.025, status_forcelist=[503],
                        allowed_methods=["GET"])


def call_inventory(run_id, logical_id):
    with requests.Session() as session:
        session.mount("http://", HTTPAdapter(max_retries=INVENTORY_RETRY))
        response = session.get(
            os.environ["INVENTORY_URL"] + "/inventory",
            headers={"X-CascadeGraph-Run-ID": run_id, "X-CascadeGraph-Logical-Request-ID": logical_id},
            timeout=0.1,
        )
        response.raise_for_status()
        return response.json()
