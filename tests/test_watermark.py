from PIL import Image

from agentic_bias_lens.watermark import finalize_image, strip_and_reencode, watermark


def _make(path, size=(128, 128), color=(200, 30, 30)):
    Image.new("RGB", size, color).save(path)
    return path


def test_watermark_same_size_no_exif(tmp_path):
    src = _make(tmp_path / "src.png")
    out = watermark(src, tmp_path / "wm.png")
    with Image.open(out) as im:
        assert im.size == (128, 128)
        assert len(im.getexif()) == 0


def test_strip_removes_metadata(tmp_path):
    src = _make(tmp_path / "src.png")
    out = strip_and_reencode(src, tmp_path / "clean.png")
    with Image.open(out) as im:
        assert im.getexif() == {} or len(im.getexif()) == 0
        assert "icc_profile" not in im.info


def test_finalize_writes_watermarked(tmp_path):
    src = _make(tmp_path / "src.png")
    out = finalize_image(src, tmp_path / "final.png")
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (128, 128)
