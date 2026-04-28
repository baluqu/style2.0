from pathlib import Path
import os

from app import create_app


app = create_app()


def parse_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    env = (os.environ.get("FLASK_ENV") or "development").strip().lower()
    debug = parse_bool(os.environ.get("DEBUG"), default=(env == "development"))
    host = (os.environ.get("HOST") or ("127.0.0.1" if debug else "0.0.0.0")).strip()
    port = int(os.environ.get("PORT", "5000"))

    ssl_context = None
    cert_file = (os.environ.get("SSL_CERT_FILE") or "").strip()
    key_file = (os.environ.get("SSL_KEY_FILE") or "").strip()
    if cert_file and key_file and Path(cert_file).exists() and Path(key_file).exists():
        ssl_context = (cert_file, key_file)

    app.run(
        host=host,
        port=port,
        debug=debug,
        ssl_context=ssl_context,
        threaded=True,
        use_reloader=debug,
    )
