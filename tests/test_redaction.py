from agentic_bias_lens.redaction import PLACEHOLDER, redact


def test_redacts_auth_header():
    out = redact({"headers": {"Authorization": "Bearer sk-abc123def456"}})
    assert out["headers"]["Authorization"] == PLACEHOLDER


def test_redacts_nested_and_url_token():
    out = redact({"url": "https://x.test/api?key=sk-secretvalue999", "nested": {"api_key": "v"}})
    assert "sk-secretvalue999" not in out["url"]
    assert out["nested"]["api_key"] == PLACEHOLDER


def test_clean_dict_unchanged():
    clean = {"model": "gpt-image-1", "n": 1, "list": ["a", "b"]}
    assert redact(clean) == clean
