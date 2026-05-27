from pathlib import Path


def test_runtime_prompt_includes_developer_output_contract_requirements() -> None:
    text = Path("core/runtime/prompts.py").read_text(encoding="utf-8")
    assert "Developer output contract is strict" in text
    assert "Each code_changes item must include path, change_type, description, content." in text
    assert "Each tests item must include path, test_type, description, content." in text
