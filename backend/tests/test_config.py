from app.config import settings


def test_settings_load():
    assert settings.alibaba_base_url.startswith("https://")
    assert settings.sie_base_url.startswith("http")
    assert set(settings.providers) == {"transcribe", "notes", "extract", "embed", "rerank"}
    assert all(v in ("cloud", "sie") for v in settings.providers.values())
