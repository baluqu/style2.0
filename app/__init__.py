from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Flask
from flask import flash
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask_login import current_user
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text
try:
    from flask_talisman import Talisman  # pyright: ignore[reportMissingImports]
except ImportError:
    Talisman = None
from flask_wtf.csrf import CSRFProtect
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from .style_worlds import STYLE_WORLD_OPTIONS, style_world_by_slug

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
limiter = Limiter(key_func=get_remote_address)

def SQLAlchemyOAuthBackend():
    return None


def ensure_user_flow_schema() -> None:
    inspector = inspect(db.engine)
    if "user" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("user")}
    statements = {
        "phone": "ALTER TABLE user ADD COLUMN phone VARCHAR(40)",
        "onboarding_complete": "ALTER TABLE user ADD COLUMN onboarding_complete BOOLEAN NOT NULL DEFAULT 0",
        "profile_json": "ALTER TABLE user ADD COLUMN profile_json TEXT",
        "profile_vector_json": "ALTER TABLE user ADD COLUMN profile_vector_json TEXT",
        "saved_looks_json": "ALTER TABLE user ADD COLUMN saved_looks_json TEXT",
        "order_history_json": "ALTER TABLE user ADD COLUMN order_history_json TEXT",
    }

    changed = False
    for column_name, statement in statements.items():
        if column_name in existing_columns:
            continue
        db.session.execute(text(statement))
        changed = True

    if changed:
        db.session.commit()


def normalize_database_uri(raw_uri: str, ssl_mode: str = "") -> str:
    uri = (raw_uri or "").strip()
    if not uri:
        return uri

    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://") :]

    if not uri.startswith(("postgresql://", "postgresql+psycopg2://")):
        return uri

    parts = urlsplit(uri)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    host = (parts.hostname or "").strip().lower()

    if ssl_mode and "sslmode" not in query and host not in {"", "localhost", "127.0.0.1"}:
        query["sslmode"] = ssl_mode

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def configure_database_engine_options(app: Flask) -> None:
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip().lower()
    if not uri.startswith("postgresql"):
        return

    engine_options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
    engine_options.setdefault("pool_pre_ping", True)
    engine_options.setdefault("pool_recycle", int(app.config.get("DB_POOL_RECYCLE", 1800)))

    pool_size = int(app.config.get("DB_POOL_SIZE", 5))
    if pool_size > 0:
        engine_options.setdefault("pool_size", pool_size)

    max_overflow = int(app.config.get("DB_MAX_OVERFLOW", 10))
    if max_overflow >= 0:
        engine_options.setdefault("max_overflow", max_overflow)

    connect_timeout = int(app.config.get("DB_CONNECT_TIMEOUT", 10))
    if connect_timeout > 0:
        connect_args = dict(engine_options.get("connect_args") or {})
        connect_args.setdefault("connect_timeout", connect_timeout)
        engine_options["connect_args"] = connect_args

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options


def configure_app_logging(app: Flask) -> None:
    raw_level = str(os.environ.get("LOG_LEVEL", app.config.get("LOG_LEVEL", "INFO"))).upper()
    level = getattr(logging, raw_level, logging.INFO)

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
    else:
        for handler in app.logger.handlers:
            handler.setFormatter(formatter)

    app.logger.setLevel(level)
    app.logger.propagate = False


def create_app(config_class=None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # Load .env automatically (DX in VS Code)
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass

    if config_class is None:
        from .config import config

        env_name = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "").strip().lower()
        if not env_name:
            env_name = "production" if os.environ.get("RENDER") else "development"
        config_class = config.get(env_name, config["default"])

    app.config.from_object(config_class)
    configure_app_logging(app)
    if app.config.get("FLASK_ENV") == "production" and app.config.get("SECRET_KEY") in {"", "dev-change-me"}:
        app.logger.warning("SECRET_KEY is using a development default. Set a strong SECRET_KEY in production.")

    if app.config.get("TRUST_PROXY_HEADERS"):
        trusted_proxy_count = max(int(app.config.get("TRUSTED_PROXY_COUNT", 1)), 1)
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_count,
            x_proto=trusted_proxy_count,
            x_host=trusted_proxy_count,
            x_port=trusted_proxy_count,
            x_prefix=trusted_proxy_count,
        )

    # Ensure instance folder exists
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # DB uri: prefer env DATABASE_URL, else instance/app.db
    if not (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip():
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "app.db")
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_uri(
            app.config.get("SQLALCHEMY_DATABASE_URI", ""),
            app.config.get("DATABASE_SSL_MODE", ""),
        )
    configure_database_engine_options(app)

    # Uploads: default to app/static/uploads
    if not (app.config.get("UPLOAD_FOLDER") or "").strip():
        app.config["UPLOAD_FOLDER"] = str(Path(app.root_path) / "static" / "uploads")

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    csrf.init_app(app)
    
    # Configure Talisman for security headers
    if Talisman:
        csp = {
            'default-src': ["'self'"],
            'script-src': [
                "'self'",
                "'unsafe-inline'",
                "'unsafe-eval'",
                "'wasm-unsafe-eval'",
                "https://cdn.tailwindcss.com",
                "https://cdn.jsdelivr.net",
            ],
            'style-src': ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://fonts.googleapis.com"],
            'img-src': ["'self'", "data:", "https:", "blob:"],
            'font-src': ["'self'", "https://fonts.gstatic.com"],
            'connect-src': ["'self'", "https://cdn.jsdelivr.net", "https://storage.googleapis.com"],
            'worker-src': ["'self'", "blob:"],
            'frame-ancestors': ["'none'"],
            'base-uri': ["'self'"],
            'form-action': ["'self'"],
        }
        Talisman(
            app,
            force_https=app.config.get("FORCE_HTTPS", True),
            strict_transport_security=True,
            strict_transport_security_max_age=31536000,
            strict_transport_security_include_subdomains=True,
            strict_transport_security_preload=True,
            content_security_policy=csp,
            referrer_policy='strict-origin-when-cross-origin',
            frame_options='DENY',
        )
    
    login_manager.init_app(app)

    from .models import User  # noqa: F401
    from .security import ensure_system_roles, ensure_bootstrap_admin

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Microsoft OAuth (optional)
    if app.config.get("MICROSOFT_OAUTH_CLIENT_ID") and app.config.get("MICROSOFT_OAUTH_CLIENT_SECRET"):
        from flask_dance.contrib.microsoft import make_microsoft_blueprint # type: ignore
        microsoft_bp = make_microsoft_blueprint(
            client_id=app.config.get("MICROSOFT_OAUTH_CLIENT_ID"),
            client_secret=app.config.get("MICROSOFT_OAUTH_CLIENT_SECRET"),
            backend=SQLAlchemyOAuthBackend(),
            redirect_to="auth.oauth_callback",
        )
        app.register_blueprint(microsoft_bp, url_prefix="/login")

    # GitHub OAuth (optional)
    if app.config.get("GITHUB_OAUTH_CLIENT_ID") and app.config.get("GITHUB_OAUTH_CLIENT_SECRET"):
        from flask_dance.contrib.github import make_github_blueprint # pyright: ignore[reportMissingImports]
        github_bp = make_github_blueprint(
            client_id=app.config.get("GITHUB_OAUTH_CLIENT_ID"),
            client_secret=app.config.get("GITHUB_OAUTH_CLIENT_SECRET"),
            backend=SQLAlchemyOAuthBackend(),
            redirect_to="auth.oauth_callback",
        )
        app.register_blueprint(github_bp, url_prefix="/login")

    from .routes.auth import bp as auth_bp
    from .routes.main import bp as main_bp
    from .routes.seller import bp as seller_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(seller_bp)

    @app.context_processor
    def inject_flow_state():
        cart = session.get("cart", [])
        cart_count = sum(int(item.get("quantity", 1)) for item in cart)
        cart_avatar = {"top": False, "bottom": False, "shoes": False, "accessory": False}
        for item in cart:
            category = str(item.get("category", "")).strip().lower()
            title = str(item.get("title", "")).strip().lower()
            hint = f"{category} {title}"
            if any(token in hint for token in ("top", "shirt", "blouse", "jacket", "hoodie", "sweater", "outerwear")):
                cart_avatar["top"] = True
            if any(token in hint for token in ("bottom", "trouser", "pants", "jean", "skirt", "shorts")):
                cart_avatar["bottom"] = True
            if any(token in hint for token in ("shoe", "sneaker", "boot", "loafer", "heel", "sandals")):
                cart_avatar["shoes"] = True
            if any(token in hint for token in ("accessory", "bag", "watch", "chain", "bracelet", "ring", "glasses", "hat", "cap")):
                cart_avatar["accessory"] = True

        raw_profile = current_user.get_profile_data() if current_user.is_authenticated and hasattr(current_user, "get_profile_data") else {}
        raw_splash_preference = raw_profile.get("show_intro_splash") if isinstance(raw_profile, dict) else None
        if isinstance(raw_splash_preference, bool):
            show_intro_splash = raw_splash_preference
        elif raw_splash_preference is None:
            show_intro_splash = True
        else:
            show_intro_splash = str(raw_splash_preference).strip().lower() in {"1", "true", "yes", "on"}
        force_intro_splash = (request.args.get("splash") or "").strip().lower() in {"1", "true", "yes", "on"}
        world_from_query = (request.args.get("style_world") or request.args.get("world") or "").strip().lower()
        active_style_world = world_from_query if style_world_by_slug(world_from_query) else ""
        style_world_theme_map = {
            world["slug"]: {
                "title": world.get("title", ""),
                "lighting": world.get("lighting", ""),
                "motion": world.get("motion", ""),
                "typography": world.get("typography", ""),
                "palette": world.get("palette", []),
            }
            for world in STYLE_WORLD_OPTIONS
        }
        return {
            "cart_count": cart_count,
            "has_completed_onboarding": bool(
                current_user.is_authenticated
                and not current_user.has_role("seller")
                and getattr(current_user, "onboarding_complete", False)
            ),
            "is_seller_account": bool(current_user.is_authenticated and current_user.has_role("seller")),
            "has_completed_seller_onboarding": bool(
                current_user.is_authenticated
                and current_user.has_role("seller")
                and getattr(getattr(current_user, "seller_profile", None), "onboarding_complete", False)
            ),
            "seller_brand_slug": getattr(getattr(current_user, "seller_profile", None), "slug", None),
            "cart_avatar": cart_avatar,
            "show_intro_splash": show_intro_splash,
            "force_intro_splash": force_intro_splash,
            "active_style_world": active_style_world,
            "style_world_theme_map": style_world_theme_map,
        }

    @app.after_request
    def disable_html_caching(response):
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        flash("Your form token expired or the page was stale. Refresh the page and try again.", "error")
        target = request.referrer or "/"
        return redirect(target), 302

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found"}), 404
        return render_template("error.html", title="Not found", message="That page does not exist."), 404

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        if isinstance(error, HTTPException):
            return error
        if app.debug:
            raise error
        app.logger.exception("Unhandled exception while processing %s", request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal_server_error"}), 500
        return render_template("error.html", title="Server error", message="Something went wrong. Please try again."), 500

    # Ensure default roles exist once tables are present.
    # In dev, tables may be created via db.create_all() before migrations are set up.
    with app.app_context():
        try:
            db.create_all()
            ensure_user_flow_schema()
            ensure_system_roles()
            ensure_bootstrap_admin(
                app.config.get("ADMIN_EMAIL", ""),
                app.config.get("ADMIN_PASSWORD", ""),
            )
        except Exception:
            pass

    return app
