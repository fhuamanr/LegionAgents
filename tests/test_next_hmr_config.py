from pathlib import Path


def test_next_config_allows_local_dev_origins_for_hmr() -> None:
    content = Path("frontend/next.config.ts").read_text(encoding="utf-8")
    assert "allowedDevOrigins" in content
    assert "127.0.0.1" in content
    assert "localhost" in content
    assert "experimental" not in content
