"""Verify that no temporary or uploaded files are persisted to disk during upload."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app


def get_dir_files(path: Path, exclude_dirs: tuple[str, ...]) -> set[str]:
    files = set()
    for root, dirs, filenames in os.walk(path):
        # Prune excluded directories in-place
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in filenames:
            full_path = os.path.join(root, f)
            files.add(full_path)
    return files


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    temp_dir = Path(tempfile.gettempdir())
    exclude = (".venv", ".git", "node_modules", "__pycache__", ".pytest_cache", "dist")

    repo_files_before = get_dir_files(repo_root, exclude)
    temp_files_before = set(os.listdir(temp_dir))

    client = TestClient(app)
    fake_doc = b"1. Rent. The monthly rent is $1,500 due on the first day.\n2. Term. Twelve months."

    response = client.post(
        "/api/documents",
        files={"file": ("test_upload.txt", fake_doc, "text/plain")},
    )

    repo_files_after = get_dir_files(repo_root, exclude)
    temp_files_after = set(os.listdir(temp_dir))

    new_repo_files = repo_files_after - repo_files_before
    new_temp_files = temp_files_after - temp_files_before

    print(f"API Upload Response Status: {response.status_code}")
    print(f"New repo files created: {len(new_repo_files)}")
    if new_repo_files:
        print(f"  Files: {new_repo_files}")

    print(f"New temp directory files created: {len(new_temp_files)}")
    if new_temp_files:
        print(f"  Files: {new_temp_files}")

    assert response.status_code == 201, f"Expected 201 Created, got {response.status_code}"
    assert len(new_repo_files) == 0, f"Leaked repo files: {new_repo_files}"
    assert len(new_temp_files) == 0, f"Leaked temp files: {new_temp_files}"
    print("\nAUDIT PASSED: Zero files written to disk or temp directory during document upload.")


if __name__ == "__main__":
    main()
