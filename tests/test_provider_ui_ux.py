from pathlib import Path


def test_provider_discovered_models_panel_is_scrollable() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "max-h-[22rem]" in text
    assert "overflow-y-auto" in text
    assert "Search models..." in text


def test_provider_model_cards_are_click_selectable_and_prefill_runtime_controls() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "selectModel(provider, profile)" in text
    assert "setSelectedModelsByProvider" in text
    assert "setRuntimeContextByProvider" in text
    assert "border-primary bg-primary/5" in text


def test_provider_has_per_agent_overrides_section() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "Advanced Per-Agent Overrides" in text
    assert "Use default" in text
    assert "parser_strategy" in text
    assert "compact_mode_enabled" in text


def test_provider_ui_shows_lmstudio_load_unload_token_errors() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "LM Studio API token is required for model listing/loading/unloading." in text
    assert "Unauthorized. Check LM Studio token and Authorization mode." in text


def test_provider_ui_has_local_runtime_token_editor() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "Local Runtime Token" in text
    assert "Save token" in text
    assert "Paste LM Studio/Ollama API token" in text


def test_provider_ui_includes_auth_mode_selector_and_human_readable_401_message() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "Auth mode: raw" in text
    assert "Auth mode: bearer" in text
    assert "Unauthorized. Check LM Studio token and Authorization mode." in text


def test_provider_ui_extract_error_renders_structured_detail_instead_of_object_object() -> None:
    text = Path("frontend/features/providers/provider-management.tsx").read_text(encoding="utf-8")
    assert "Array.isArray(payload.detail)" in text
    assert "JSON.stringify(payload.detail)" in text
