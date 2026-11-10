"""Copy a clean source snapshot without exporting Replit checkpoint history.

The platform history contains uploaded account screenshots and migration backups.
Keep that history local; use a separate Git clone for public feature PRs.
This helper never pushes, commits, or handles credentials.
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "generated-artifacts" / "github-export"
EXCLUDE = {".migration-backup", "attached_assets", ".agents", "generated-artifacts", ".local"}

if not (DESTINATION / ".git").is_dir():
    DESTINATION.parent.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "clone", "https://github.replit.internal/ElusiveParadox/cascadegraph.git", str(DESTINATION)],
        check=True,
    )

paths = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT).split(b"\0")
copied = 0
for raw in sorted(set(paths)):
    if not raw:
        continue
    path = Path(raw.decode())
    if path.parts[0] in EXCLUDE or path.suffix in {".sqlite3", ".png", ".jpg", ".jpeg"}:
        continue
    source = ROOT / path
    if not source.is_file() or source.is_symlink():
        continue
    dest = DESTINATION / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    copied += 1
print(f"Exported {copied} source/configuration files. No credentials, uploads or checkpoint history copied.")
