from pathlib import Path


def test_nginx_routes_webpack_hmr_to_frontend_with_upgrade_headers() -> None:
    content = Path("deployment/nginx/nginx.conf").read_text(encoding="utf-8")
    assert "location /_next/webpack-hmr" in content
    assert "proxy_pass http://frontend_upstream;" in content
    assert "proxy_set_header Upgrade $http_upgrade;" in content
