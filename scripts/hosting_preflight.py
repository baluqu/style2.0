from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_FILES = [
    PROJECT_ROOT / "render.yaml",
    PROJECT_ROOT / "requirements.txt",
    PROJECT_ROOT / "wsgi.py",
    PROJECT_ROOT / "migrations",
    PROJECT_ROOT / "docs" / "render-deploy.md",
]
REQUIRED_PACKAGES = {
    "Flask==3.1.3",
    "gunicorn==23.0.0",
    "psycopg2-binary==2.9.11",
    "supabase==2.28.3",
}
REQUIRED_ENV_KEYS = [
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SECRET_KEY",
    "ADMIN_KEY",
]


def read_requirements() -> set[str]:
    path = PROJECT_ROOT / "requirements.txt"
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def env_snapshot() -> dict[str, bool]:
    values: dict[str, bool] = {}
    env_path = PROJECT_ROOT / ".env"
    file_values: dict[str, str] = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            file_values[key.strip()] = value.strip()

    for key in REQUIRED_ENV_KEYS:
        values[key] = bool(os.environ.get(key) or file_values.get(key))
    return values


def git_ready() -> bool:
    return (PROJECT_ROOT / ".git").exists()


def create_app_ready() -> tuple[bool, str]:
    try:
        from app import create_app

        app = create_app()
        route_count = sum(1 for _ in app.url_map.iter_rules())
        return True, f"create_app() loaded with {route_count} routes"
    except Exception as exc:  # pragma: no cover - diagnostics only
        return False, str(exc)


def main() -> int:
    file_status = {str(path.relative_to(PROJECT_ROOT)): path.exists() for path in REQUIRED_FILES}
    requirements = read_requirements()
    package_status = {package: package in requirements for package in REQUIRED_PACKAGES}
    env_status = env_snapshot()
    app_ok, app_message = create_app_ready()

    summary = {
        "files": file_status,
        "packages": package_status,
        "env": env_status,
        "git_initialized": git_ready(),
        "app_boots": app_ok,
        "app_message": app_message,
    }

    print(json.dumps(summary, indent=2))

    missing_env = [key for key, present in env_status.items() if not present]
    failed_checks = [
        *(name for name, present in file_status.items() if not present),
        *(name for name, present in package_status.items() if not present),
    ]
    if missing_env:
        failed_checks.append("missing_env")
    if not summary["git_initialized"]:
        failed_checks.append("git_not_initialized")
    if not app_ok:
        failed_checks.append("app_boot_failed")

    return 0 if not failed_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
