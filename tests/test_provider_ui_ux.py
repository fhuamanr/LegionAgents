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
    assert "LM Studio rejected the API token." in text
