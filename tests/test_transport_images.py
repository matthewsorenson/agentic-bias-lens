import httpx
import respx
from PIL import Image

from agentic_bias_lens.adapters.image import FalImage, GeminiImage, OpenAIImage
from agentic_bias_lens.capabilities import ImageRequest


def _assert_watermarked_png(path):
    assert path.exists()
    with Image.open(path) as im:
        assert im.size[0] > 0
        assert len(im.getexif()) == 0  # metadata stripped by finalize_image


@respx.mock
async def test_openai_image_b64(tmp_path, png_b64):
    respx.post("https://api.openai.com/v1/images/generations").mock(
        return_value=httpx.Response(200, json={"data": [{"b64_json": png_b64}]})
    )
    img = OpenAIImage("gpt-image-1", "https://api.openai.com/v1", "k", tmp_path, "gpt-image-1")
    res = await img.generate(ImageRequest(prompt="a coastal scene"))
    _assert_watermarked_png(res.image_path)
    assert res.prompt_original == "a coastal scene"
    assert res.prompt_as_sent == "a coastal scene"


@respx.mock
async def test_gemini_image_predict(tmp_path, png_b64):
    base = "https://generativelanguage.googleapis.com/v1beta"
    respx.post(f"{base}/models/imagen-4.0-fast-generate-001:predict").mock(
        return_value=httpx.Response(200, json={"predictions": [{"bytesBase64Encoded": png_b64}]})
    )
    img = GeminiImage("imagen-4-fast", base, "k", tmp_path, "imagen-4.0-fast-generate-001")
    res = await img.generate(ImageRequest(prompt="p"))
    _assert_watermarked_png(res.image_path)


@respx.mock
async def test_fal_image_downloads_url(tmp_path, png_bytes):
    respx.post("https://fal.run/fal-ai/qwen-image").mock(
        return_value=httpx.Response(200, json={"images": [{"url": "https://fal.media/x.png"}]})
    )
    respx.get("https://fal.media/x.png").mock(
        return_value=httpx.Response(200, content=png_bytes)
    )
    img = FalImage("qwen-image", "https://fal.run", "k", tmp_path, "fal-ai/qwen-image")
    res = await img.generate(ImageRequest(prompt="p"))
    _assert_watermarked_png(res.image_path)
