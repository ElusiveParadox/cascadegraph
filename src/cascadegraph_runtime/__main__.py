"""Start the Python service using the artifact-provided port."""

import os

import uvicorn

port = int(os.environ["PORT"])
if not 0 < port < 65536:
    raise ValueError("PORT must be between 1 and 65535")

if __name__ == "__main__":
    uvicorn.run(
        "cascadegraph_runtime.app:app",
        host="0.0.0.0",
        port=port,
        access_log=False,
    )
