import base64
import io
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_dir() -> Path:
    return REPO_ROOT / "config"


def _tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (120, 120, 120)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def png_bytes() -> bytes:
    return _tiny_png()


@pytest.fixture
def png_b64() -> str:
    return base64.b64encode(_tiny_png()).decode("ascii")
