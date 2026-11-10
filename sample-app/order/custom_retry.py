"""Optional alternate retry implementation; not bound in the default topology."""
import time

import requests


def custom_retry_request(url):
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=0.1)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(0.05 * (2 ** attempt))
