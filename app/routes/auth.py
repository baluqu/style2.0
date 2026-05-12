from __future__ import annotations

import os
import re
import smtplib
import secrets
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, Optional

from .. import db, limiter
from ..models import SellerProfile, User
from ..security import assign_role, audit

bp = Blueprint("auth", __name__)


def is_safe_redirect_target(target: str) -> bool:
    if not target:
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")


def seller_slug(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or f"brand-{uuid.uuid4().hex[:6]}"
    candidate = base
    step = 2
    while SellerProfile.query.filter_by(slug=candidate).first():
        candidate = f"{base}-{step}"
        step += 1
    return candidate


def with_query_params(target: str, **params: object) -> str:
    parts = urlsplit(target)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        query[str(key)] = str(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=120)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=40)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=220)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=200)])


class LoginForm(FlaskForm):
    identity = StringField("Email or username", validators=[DataRequired(), Length(min=3, max=220)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=1, max=200)])


class SellerRegisterForm(FlaskForm):
    business_name = StringField("Business name", validators=[DataRequired(), Length(min=2, max=180)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=220)])
    phone = StringField("Phone", validators=[DataRequired(), Length(min=7, max=40)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=200)])


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=220)])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=200)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), Length(min=8, max=200)])


class PhoneLoginForm(FlaskForm):
    phone = StringField("Phone Number", validators=[DataRequired(), Length(min=7, max=40)])
    otp_code = StringField("OTP code", validators=[Optional(), Length(min=4, max=8)])


def normalize_identity(raw_identity: str) -> str:
    identity = (raw_identity or "").strip().lower()
    if not identity:
        return ""
    if "@" in identity:
        return identity
    slug = re.sub(r"[^a-z0-9._-]+", "", identity).strip("._-")
    if len(slug) < 3:
        return ""
    return f"{slug}@stylebridge.local"


def username_slug(raw_username: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "", (raw_username or "").strip().lower()).strip("._-")


def normalize_phone(raw_phone: str) -> str:
    if not raw_phone:
        return ""
    cleaned = re.sub(r"[^0-9+]+", "", raw_phone.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


def find_user_for_phone(raw_phone: str) -> User | None:
    phone = normalize_phone(raw_phone)
    if not phone:
        return None
    user = User.query.filter_by(phone=phone).first()
    if user:
        return user
    alternate = (raw_phone or "").strip()
    if alternate and alternate != phone:
        return User.query.filter_by(phone=alternate).first()
    return None


def create_phone_otp(phone: str) -> dict[str, str]:
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    session["phone_login_otp"] = {"phone": phone, "code": code, "expires_at": expires_at}
    session.modified = True
    return {"phone": phone, "code": code, "expires_at": expires_at}


def get_phone_otp_state() -> dict[str, str] | None:
    raw = session.get("phone_login_otp")
    if not isinstance(raw, dict):
        return None
    return {"phone": str(raw.get("phone", "")), "code": str(raw.get("code", "")), "expires_at": str(raw.get("expires_at", ""))}


def clear_phone_otp_state() -> None:
    session.pop("phone_login_otp", None)
    session.modified = True


def send_password_reset_email(recipient_email: str, reset_url: str) -> None:
    sender = os.environ.get("SMTP_FROM_EMAIL", "noreply@stylebridge.app").strip()
    subject = "StyleBridge password reset"
    message_body = (
        f"Use the link below to reset your StyleBridge password:\n\n{reset_url}\n\n"
        "If you did not request this, ignore this message."
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient_email
    msg.set_content(message_body)

    smtp_server = os.environ.get("SMTP_SERVER", "").strip()
    if not smtp_server:
        current_app.logger.warning("Password reset email backend not configured. Reset link for %s: %s", recipient_email, reset_url)
        return

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
    except Exception:
        current_app.logger.exception("Failed to send password reset email to %s", recipient_email)
        current_app.logger.info("Password reset link for %s: %s", recipient_email, reset_url)


def get_user_by_reset_token(token: str) -> User | None:
    if not token:
        return None
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or not user.password_reset_expires_at:
        return None
    try:
        expires_at = user.password_reset_expires_at
        if expires_at < datetime.utcnow():
            return None
    except Exception:
        return None
    return user


def persist_user_cart_to_profile(user: User, cart_items: list[dict]) -> None:
    profile = user.get_profile_data()
    profile["cart"] = cart_items
    user.set_profile_data(profile)
    db.session.commit()


def merge_cart_items(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in list(existing or []) + list(incoming or []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "") or "").strip()
        if not item_id:
            continue
        quantity = max(1, int(item.get("quantity", 1) or 1))
        if item_id in merged:
            merged[item_id]["quantity"] = max(1, merged[item_id].get("quantity", 1) + quantity)
        else:
            merged[item_id] = {**item, "quantity": quantity}
    return list(merged.values())


def persist_session_cart_after_login(user: User) -> None:
    saved_cart = user.get_profile_data().get("cart", [])
    if not isinstance(saved_cart, list):
        saved_cart = []
    session_cart = session.get("cart") if isinstance(session.get("cart"), list) else []
    merged = merge_cart_items(saved_cart, session_cart)
    if merged != saved_cart:
        profile = user.get_profile_data()
        profile["cart"] = merged
        user.set_profile_data(profile)
        db.session.commit()
    session["cart"] = merged
    session.modified = True


def username_taken(username: str) -> bool:
    wanted = username_slug(username)
    if not wanted:
        return True
    users = User.query.all()
    for user in users:
        profile = user.get_profile_data() if hasattr(user, "get_profile_data") else {}
        existing = username_slug(str(profile.get("username", ""))) if isinstance(profile, dict) else ""
        if existing == wanted:
            return True
    return False


def find_user_for_login(raw_identity: str) -> User | None:
    identity = (raw_identity or "").strip()
    if not identity:
        return None

    lowered = identity.lower()
    if "@" in lowered:
        return User.query.filter_by(email=lowered).first()

    legacy_email = normalize_identity(identity)
    if legacy_email:
        user = User.query.filter_by(email=legacy_email).first()
        if user:
            return user

    wanted_username = username_slug(identity)
    if not wanted_username:
        return None
    for user in User.query.all():
        profile = user.get_profile_data() if hasattr(user, "get_profile_data") else {}
        existing = username_slug(str(profile.get("username", ""))) if isinstance(profile, dict) else ""
        if existing == wanted_username:
            return user
    return None


@bp.get("/register")
def register():
    if current_user.is_authenticated and not current_user.has_role("seller"):
        if current_user.onboarding_complete:
            return redirect(url_for("main.feed"))
        return redirect(url_for("main.onboarding"))
    form = RegisterForm()
    return render_template("auth/register.html", form=form)


@bp.post("/register")
@limiter.limit("5 per hour")
def register_post():
    form = RegisterForm()
    if not form.validate_on_submit():
        flash("Please fix the errors and try again.", "error")
        return render_template("auth/register.html", form=form), 400

    full_name = form.name.data.strip()
    username = username_slug(form.username.data)
    email = form.email.data.strip().lower()

    if not username:
        flash("Choose a valid username.", "error")
        return render_template("auth/register.html", form=form), 400

    if username_taken(username):
        flash("That username is already taken.", "error")
        return render_template("auth/register.html", form=form), 400

    if User.query.filter_by(email=email).first():
        flash("Email already registered. Please log in.", "error")
        return redirect(url_for("auth.login"))

    user = User(email=email)
    user.set_password(form.password.data)
    user.set_profile_data(
        {
            "display_name": full_name,
            "username": username,
            "show_intro_splash": True,
            "saved_look_reminders": False,
            "daily_outfit_suggestions": True,
        }
    )
    assign_role(user, "user")
    db.session.add(user)
    db.session.commit()
    login_user(user)
    audit("auth.register", target=f"user:{user.id}", meta={"email": user.email, "username": username})
    flash("Account created. Build your identity to unlock your personalized style system.", "success")
    return redirect(with_query_params(url_for("main.onboarding"), splash=1, phase="identity"))


@bp.get("/seller-register")
def seller_register():
    form = SellerRegisterForm()
    return render_template("auth/seller_register.html", form=form)


@bp.post("/seller-register")
@limiter.limit("5 per hour")
def seller_register_post():
    form = SellerRegisterForm()
    if not form.validate_on_submit():
        flash("Please fix the errors and try again.", "error")
        return render_template("auth/seller_register.html", form=form), 400

    email = form.email.data.strip().lower()
    if User.query.filter_by(email=email).first():
        flash("Email already registered. Please log in.", "error")
        return redirect(url_for("auth.login"))

    phone = normalize_phone(form.phone.data)
    user = User(email=email, phone=phone)
    user.set_password(form.password.data)
    assign_role(user, "seller")
    db.session.add(user)
    db.session.flush()

    brand_name = form.business_name.data.strip()
    profile = SellerProfile(
        user_id=user.id,
        brand_name=brand_name,
        slug=seller_slug(brand_name),
        contact_email=email,
        contact_phone=phone,
        onboarding_complete=False,
    )
    db.session.add(profile)
    db.session.commit()
    login_user(user)
    audit("auth.seller_register", target=f"user:{user.id}", meta={"email": user.email, "brand_name": brand_name})
    flash("Seller account created.", "success")
    return redirect(with_query_params(url_for("seller.onboarding"), splash=1))


@bp.get("/login")
def login():
    if current_user.is_authenticated and not current_user.has_role("seller"):
        if current_user.onboarding_complete:
            return redirect(url_for("main.feed"))
        return redirect(url_for("main.onboarding"))
    form = LoginForm()
    return render_template("auth/login.html", form=form)


@limiter.limit("10 per hour")
@bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        flash("Invalid input.", "error")
        return render_template("auth/login.html", form=form), 400

    user = find_user_for_login(form.identity.data)
    if not user or not user.check_password(form.password.data):
        flash("Invalid credentials.", "error")
        return render_template("auth/login.html", form=form), 401

    login_user(user, remember=False)
    persist_session_cart_after_login(user)
    audit("auth.login", target=f"user:{user.id}")
    flash("Welcome back.", "success")
    next_url = request.args.get("next")
    if next_url and is_safe_redirect_target(next_url):
        return redirect(with_query_params(next_url, splash=1))
    if user.has_role("seller"):
        seller_profile = getattr(user, "seller_profile", None)
        if seller_profile and seller_profile.onboarding_complete:
            return redirect(with_query_params(url_for("seller.dashboard"), splash=1))
        return redirect(with_query_params(url_for("seller.onboarding"), splash=1))
    if user.onboarding_complete:
        return redirect(with_query_params(url_for("main.feed"), splash=1))
    return redirect(with_query_params(url_for("main.onboarding"), splash=1, phase="identity"))


@bp.get("/google")
def google_login():
    flash("Google sign-in is queued for integration. Email signup is live now.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/phone", methods=["GET", "POST"])
def phone_login():
    form = PhoneLoginForm()
    otp_required = False
    phone_hint = ""
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Enter a valid phone number.", "error")
            return render_template("auth/phone_login.html", form=form), 400

        phone = normalize_phone(form.phone.data)
        if not phone:
            flash("Enter a valid phone number.", "error")
            return render_template("auth/phone_login.html", form=form), 400

        otp_code = (form.otp_code.data or "").strip()
        if otp_code:
            state = get_phone_otp_state()
            if not state or state.get("phone") != phone or state.get("code") != otp_code:
                flash("The code is invalid or has expired. Request a new one.", "error")
                return render_template("auth/phone_login.html", form=form, otp_required=True, phone_hint=phone), 401
            try:
                expires_at = datetime.fromisoformat(state.get("expires_at", ""))
            except Exception:
                expires_at = datetime.utcnow() - timedelta(minutes=1)
            if expires_at < datetime.utcnow():
                clear_phone_otp_state()
                flash("The code has expired. Request a new one.", "error")
                return render_template("auth/phone_login.html", form=form, otp_required=False), 401

            user = find_user_for_phone(phone)
            if not user:
                flash("No account is linked to that phone number. Please use email login or register.", "error")
                clear_phone_otp_state()
                return render_template("auth/phone_login.html", form=form), 404

            login_user(user, remember=False)
            persist_session_cart_after_login(user)
            clear_phone_otp_state()
            audit("auth.phone_login", target=f"user:{user.id}")
            flash("Welcome back.", "success")
            next_url = request.args.get("next")
            if next_url and is_safe_redirect_target(next_url):
                return redirect(with_query_params(next_url, splash=1))
            if user.has_role("seller"):
                seller_profile = getattr(user, "seller_profile", None)
                if seller_profile and seller_profile.onboarding_complete:
                    return redirect(with_query_params(url_for("seller.dashboard"), splash=1))
                return redirect(with_query_params(url_for("seller.onboarding"), splash=1))
            if user.onboarding_complete:
                return redirect(with_query_params(url_for("main.feed"), splash=1))
            return redirect(with_query_params(url_for("main.onboarding"), splash=1, phase="identity"))

        user = find_user_for_phone(phone)
        if not user:
            flash("No account is linked to that phone number. Please use email login or register.", "error")
            return render_template("auth/phone_login.html", form=form), 404

        otp_state = create_phone_otp(phone)
        current_app.logger.info("Phone login OTP generated for %s: %s", phone, otp_state["code"])
        flash("A login code has been generated. Enter it below to continue.", "success")
        otp_required = True
        phone_hint = phone

    return render_template("auth/phone_login.html", form=form, otp_required=otp_required, phone_hint=phone_hint)


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Enter the email tied to your account.", "error")
            return render_template("auth/forgot_password.html", form=form), 400

        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(24)
            user.password_reset_token = token
            user.password_reset_expires_at = datetime.utcnow() + timedelta(hours=2)
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_password_reset_email(user.email, reset_url)
            audit("auth.password_reset_requested", target=f"user:{user.id}")
        else:
            audit("auth.password_reset_requested", meta={"email": email})

        flash("If that account exists, reset instructions have been queued.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    user = get_user_by_reset_token(token)
    if not user:
        flash("Reset link is invalid or expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Enter a valid new password.", "error")
            return render_template("auth/reset_password.html", form=form, token=token), 400
        if form.password.data != form.confirm_password.data:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", form=form, token=token), 400

        user.set_password(form.password.data)
        user.password_reset_token = None
        user.password_reset_expires_at = None
        db.session.commit()
        audit("auth.password_reset_completed", target=f"user:{user.id}")
        flash("Password updated. You may now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@bp.post("/logout")
@login_required
def logout():
    current_id = current_user.get_id()
    audit("auth.logout", target=f"user:{current_id}" if current_id else None)
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.home", splash=1))

