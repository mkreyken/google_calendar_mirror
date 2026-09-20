import os
import shutil
import subprocess
from pathlib import Path

from src.util.filesystem import project_root


def remove_dir(path: Path) -> None:
    if path.exists() and path.is_dir():
        subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(path)],
            shell=True
        )


# Source: dist folder inside project root
dist_source = project_root(installed=False) / "dist"
if not dist_source.exists():
    raise FileNotFoundError(f"Source folder does not exist: {dist_source}")

# Target: user's Downloads\ICal
target = Path(os.environ["USERPROFILE"]) / "Downloads" / "ICal"
# remove_dir(target)

target.mkdir(parents=True, exist_ok=True)

# --- Copy dist ---
dist_target = target / "dist"
shutil.copytree(dist_source, dist_target, dirs_exist_ok=True)

# --- Copy secrets ---
secrets_source = project_root() / "secrets"
secrets_target = target / "secrets"
if secrets_source.exists():
    shutil.copytree(secrets_source, secrets_target, dirs_exist_ok=True)

# --- Copy data ---
data_source = project_root() / "data"
data_target = target / "data"
if data_source.exists():
    shutil.copytree(data_source, data_target, dirs_exist_ok=True)

data_target = target / "logs"
data_target.mkdir(parents=True, exist_ok=True)

print(f"Copied dist, secrets, and data to {target}")
