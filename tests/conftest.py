from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_dir() -> Path:
    return REPO_ROOT / "config"
