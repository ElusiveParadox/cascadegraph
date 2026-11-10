"""Test-only launcher: inject faults, then run the real production entry point."""

import json
import multiprocessing
import os
import runpy
import time
from pathlib import Path

from storage_faults import tracked_fault

from cascadegraph_runtime import store
from cascadegraph_runtime.storage_execution import StorageExecutor


def install_faults(directory):
    original_run = StorageExecutor.run
    original_close = StorageExecutor.close

    async def run(self, function, *args, **kwargs):
        control = directory / "fault"
        if function == store.save_analysis and control.exists():
            stage = control.read_text()
            # One invocation record per attempted save, including its generated ID.
            with (directory / "writes").open("a") as file:
                file.write(json.dumps({"id": args[1]["id"], "stage": stage}) + "\n")
            return await original_run(
                self, tracked_fault, function, args, stage,
                str(directory / "blocked"), str(directory / "calls"), str(directory / "worker"), **kwargs,
            )
        return await original_run(self, function, *args, **kwargs)

    async def close(self):
        started = time.monotonic()
        await original_close(self)
        (directory / "closed").write_text(json.dumps({
            "seconds": time.monotonic() - started,
            "active": self.active,
            "children": [p.pid for p in multiprocessing.active_children() if p.name == "cascadegraph-storage"],
        }))

    StorageExecutor.run = run
    StorageExecutor.close = close


if __name__ == "__main__":
    install_faults(Path(os.environ["CG_TEST_DIRECTORY"]))
    runpy.run_module("cascadegraph_runtime", run_name="__main__")
