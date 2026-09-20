import os
from pathlib import Path

from src.util.filesystem import project_root


def list_directory(root : Path) -> list[Path]:
    results = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip __pycache__
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]

        # Compute relative directory path
        rel_dir = os.path.relpath(dirpath, root)

        # Add directories
        for d in dirnames:
            results.append(os.path.join(rel_dir, d))

        # Add files
        for f in filenames:
            results.append(os.path.join(rel_dir, f))

    # Normalize slashes for readability
    return [p.replace("\\", "/") for p in results]


if __name__ == "__main__":
    p_root = project_root()  # or any path you want
    for item in list_directory(p_root):
        print(item)
