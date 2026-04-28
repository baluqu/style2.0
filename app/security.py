from __future__ import annotations

import json
from functools import wraps
from typing import Callable, Iterable

from flask import abort, request
from flask_login import current_user

from . import db
from .models import AuditLog, Role, User


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "user": set(),
    "seller": set(),
    "inventory_manager": {"inventory:write"},
    "admin": {"inventory:write", "users:write"},
    "superadmin": {"*"},
}


def has_permission(user: User, permission: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    for role in (user.roles or []):
        perms = ROLE_PERMISSIONS.get((role.name or "").lower(), set())
        if "*" in perms or permission in perms:
            return True
    return False


def require_permission(permission: str):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not has_permission(current_user, permission):
                abort(403)
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def ensure_system_roles() -> None:
    # Create default roles if missing (idempotent)
    for name in ROLE_PERMISSIONS.keys():
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name))
    db.session.commit()


def ensure_bootstrap_admin(admin_email: str, admin_password: str) -> None:
    email = (admin_email or "").strip().lower()
    password = admin_password or ""
    if not email or not password:
        return
    if len(password) < 8:
        return

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.session.add(user)

    user.set_password(password)
    user.is_admin = True
    assign_role(user, "superadmin")
    db.session.commit()


def assign_role(user: User, role_name: str) -> None:
    rn = role_name.strip().lower()
    role = Role.query.filter_by(name=rn).first()
    if not role:
        role = Role(name=rn)
        db.session.add(role)
        db.session.flush()
    if role not in (user.roles or []):
        user.roles.append(role)


def audit(action: str, target: str | None = None, meta: dict | None = None) -> None:
    try:
        db.session.add(
            AuditLog(
                actor_user_id=int(current_user.get_id()) if current_user.is_authenticated else None,
                action=action,
                target=target,
                meta_json=json.dumps(meta or {}, ensure_ascii=False),
                ip=request.headers.get("X-Forwarded-For", request.remote_addr),
                user_agent=(request.headers.get("User-Agent") or "")[:300],
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

