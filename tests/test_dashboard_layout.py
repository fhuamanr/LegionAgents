from pathlib import Path


def test_playground_page_uses_dashboard_shell() -> None:
    text = Path("frontend/app/dashboard/playground/page.tsx").read_text(encoding="utf-8")
    assert "AppShell" in text
    assert "<AppShell>" in text


def test_app_shell_highlights_active_route() -> None:
    text = Path("frontend/components/layout/app-shell.tsx").read_text(encoding="utf-8")
    assert "usePathname" in text
    assert "pathname === item.href" in text
