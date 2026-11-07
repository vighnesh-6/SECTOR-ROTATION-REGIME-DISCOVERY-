"""
deployment/tests/test_strict_isolation.py
=========================================
Verifies that the research project boundary is 100% preserved.
Asserts that no existing research files outside deployment/ were created, modified, or deleted.
"""

import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_research_directories_untouched():
    # 1. Assert git diff against HEAD is 100% clean across all tracked files
    result_diff = subprocess.run(
        ["git", "diff", "HEAD", "--", ":!deployment"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result_diff.returncode == 0
    assert result_diff.stdout.strip() == "", (
        f"Strict isolation violation! Tracked research files modified: {result_diff.stdout}"
    )

    # 2. Assert no staged or modified files outside deployment/
    result_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result_status.returncode == 0

    lines = result_status.stdout.strip().split("\n")
    modified_outside_deployment = []

    for line in lines:
        if not line.strip():
            continue
        status = line[:2]
        filepath = line[3:].strip().strip('"')

        # Only check modified (' M', 'M ', 'MM') or deleted (' D', 'D ') status
        if any(c in status for c in ["M", "D", "A", "R", "C"]) and not filepath.startswith("deployment/"):
            modified_outside_deployment.append((status, filepath))

    assert len(modified_outside_deployment) == 0, (
        f"Strict isolation violation! Files modified outside deployment/: {modified_outside_deployment}"
    )
