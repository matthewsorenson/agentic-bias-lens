"""Guard tests for the public repo: no generated images leak, docs follow the
owner style rule.
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=False
    )
    return out.stdout.splitlines()


def test_no_images_tracked_under_runs():
    offenders = [
        f for f in _tracked_files() if f.startswith("runs/") and f.lower().endswith(IMAGE_EXT)
    ]
    assert offenders == [], offenders


def test_tracked_images_only_in_sanctioned_example_dir():
    offenders = [
        f
        for f in _tracked_files()
        if f.lower().endswith(IMAGE_EXT) and not f.startswith("examples/mock-run/images/")
    ]
    assert offenders == [], offenders


def test_repo_docs_have_no_em_dashes():
    for name in ["README.md", "NOTICE.md", "ETHICS.md"]:
        text = (REPO / name).read_text(encoding="utf-8")
        assert "—" not in text, name
