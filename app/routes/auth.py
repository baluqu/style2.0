from __future__ import annotations

import re
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length

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
    identity = StringField("Email or username", validators=[DataRequired(), Length(min=3, max=220)])
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


class PhoneLoginForm(FlaskForm):
    phone = StringField("Phone Number", validators=[DataRequired(), Length(min=7, max=40)])


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


@bp.get("/register")
def register():
    if current_user.is_authenticated and not current_user.has_role("seller"):
        return redirect(url_for("main.demo"))
    form = RegisterForm()
    return render_template("auth/register.html", form=form)


@bp.post("/register")
@limiter.limit("5 per hour")
def register_post():
    form = RegisterForm()
    if not form.validate_on_submit():
        flash("Please fix the errors and try again.", "error")
        return render_template("auth/register.html", form=form), 400

    email = normalize_identity(form.identity.data)
    if not email:
        flash("Enter a valid email or username.", "error")
        return render_template("auth/register.html", form=form), 400
    if User.query.filter_by(email=email).first():
        flash("Email already registered. Please log in.", "error")
        return redirect(url_for("auth.login"))

    user = User(email=email)
    user.set_password(form.password.data)
    assign_role(user, "user")
    db.session.add(user)
    db.session.commit()
    login_user(user)
    audit("auth.register", target=f"user:{user.id}", meta={"email": user.email})
    flash("Account created.", "success")
    return redirect(with_query_params(url_for("main.demo"), splash=1))


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

    user = User(email=email, phone=form.phone.data.strip())
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
        contact_phone=form.phone.data.strip(),
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
        return redirect(url_for("main.demo"))
    form = LoginForm()
    return render_template("auth/login.html", form=form)


@limiter.limit("10 per hour")
@bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        flash("Invalid input.", "error")
        return render_template("auth/login.html", form=form), 400

    email = normalize_identity(form.identity.data)
    if not email:
        flash("Enter a valid email or username.", "error")
        return render_template("auth/login.html", form=form), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(form.password.data):
        flash("Invalid credentials.", "error")
        return render_template("auth/login.html", form=form), 401

    login_user(user, remember=False)
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
    return redirect(with_query_params(url_for("main.demo"), splash=1))


@bp.get("/google")
def google_login():
    flash("Google login is the recommended next integration point. Email login is live right now.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/phone", methods=["GET", "POST"])
def phone_login():
    form = PhoneLoginForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Enter a valid phone number.", "error")
            return render_template("auth/phone_login.html", form=form), 400
        flash("Phone login UI is in place. OTP delivery is the next backend integration.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/phone_login.html", form=form)


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Enter the email tied to your account.", "error")
            return render_template("auth/forgot_password.html", form=form), 400

        audit("auth.password_reset_requested", meta={"email": form.email.data.strip().lower()})
        flash("If that account exists, reset instructions have been queued.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    current_id = current_user.get_id()
    audit("auth.logout", target=f"user:{current_id}" if current_id else None)
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.home", splash=1))

