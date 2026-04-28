from __future__ import annotations

import re
import uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from .. import db
from ..models import SellerOrder, SellerProduct, SellerProfile
from ..security import assign_role, audit
from ..storage import UploadStorageError, save_uploaded_file

bp = Blueprint("seller", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
BUSINESS_TYPE_OPTIONS = ["Clothing brand", "Thrift", "Boutique"]
ORDER_STATUS_OPTIONS = ["Pending", "Accepted", "Rejected", "Shipped", "Delivered"]
PRODUCT_STATUS_OPTIONS = ["Active", "Out of stock", "Draft"]
PRODUCT_CATEGORY_OPTIONS = [
    "Hoodie",
    "Jeans",
    "Dress",
    "Abaya",
    "Thobe",
    "Top",
    "Bottom",
    "Outerwear",
    "Shoes",
    "Bag",
    "Accessory",
    "Outfit",
]


def sanitize_text(text: str, max_length: int = 500) -> str:
    if not text:
        return ""
    return str(text).strip()[:max_length]


def sanitize_url(url: str, max_length: int = 1200) -> str:
    value = sanitize_text(url, max_length)
    if value and not (value.startswith("http://") or value.startswith("https://") or value.startswith("/static/")):
        return ""
    return value


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", sanitize_text(value, 180).lower()).strip("-")
    return slug or f"brand-{uuid.uuid4().hex[:8]}"


def unique_brand_slug(value: str, current_profile_id: int | None = None) -> str:
    base = slugify(value)
    candidate = base
    step = 2
    while True:
        existing = SellerProfile.query.filter_by(slug=candidate).first()
        if not existing or existing.id == current_profile_id:
            return candidate
        candidate = f"{base}-{step}"
        step += 1


def save_image(file_storage, prefix: str) -> str:
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename):
        return ""
    subdirectory = "seller-assets"
    return save_uploaded_file(file_storage, prefix, subdirectory=subdirectory)


def is_seller_account() -> bool:
    return current_user.is_authenticated and current_user.has_role("seller")


def seller_profile() -> SellerProfile | None:
    return getattr(current_user, "seller_profile", None) if current_user.is_authenticated else None


def ensure_seller_account():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))
    if not current_user.has_role("seller"):
        flash("This area is for seller accounts only.", "error")
        return redirect(url_for("main.feed" if current_user.onboarding_complete else "main.onboarding"))
    return None


def ensure_seller_ready():
    maybe_redirect = ensure_seller_account()
    if maybe_redirect:
        return None, maybe_redirect
    profile = seller_profile()
    if not profile:
        profile = SellerProfile(
            user_id=int(current_user.get_id()),
            brand_name=sanitize_text(current_user.email.split("@")[0].replace(".", " ").title(), 180) or "StyleBridge Seller",
            slug=unique_brand_slug(current_user.email.split("@")[0]),
            contact_email=current_user.email,
            contact_phone=current_user.phone,
            onboarding_complete=False,
        )
        db.session.add(profile)
        db.session.commit()
    if not profile.onboarding_complete:
        return None, redirect(url_for("seller.onboarding"))
    return profile, None


def seller_dashboard_stats(profile: SellerProfile) -> dict:
    products = SellerProduct.query.filter_by(seller_id=profile.id).order_by(SellerProduct.updated_at.desc()).all()
    orders = SellerOrder.query.filter_by(seller_id=profile.id).order_by(SellerOrder.created_at.desc()).all()
    total_sales = round(sum(order.total_amount for order in orders if order.status != "Rejected"), 2)
    available_balance = round(sum(order.total_amount for order in orders if order.status == "Delivered"), 2)
    pending_balance = round(sum(order.total_amount for order in orders if order.status in {"Pending", "Accepted", "Shipped"}), 2)
    low_stock = [product for product in products if product.stock_quantity <= 3 and product.status != "Draft"]
    total_views = sum(product.views_count for product in products)
    total_orders = sum(product.orders_count for product in products)
    conversion_rate = round((total_orders / total_views) * 100, 1) if total_views else 0.0
    best_sellers = sorted(products, key=lambda product: (-product.orders_count, -product.views_count, product.title))[:5]
    return {
        "products": products,
        "orders": orders,
        "total_sales": total_sales,
        "available_balance": available_balance,
        "pending_balance": pending_balance,
        "low_stock": low_stock,
        "total_views": total_views,
        "total_orders": total_orders,
        "conversion_rate": conversion_rate,
        "best_sellers": best_sellers,
    }


def product_payload_from_form(product: SellerProduct | None = None) -> dict:
    title = sanitize_text(request.form.get("title", ""), 220)
    category = sanitize_text(request.form.get("category", ""), 120)
    description = sanitize_text(request.form.get("description", ""), 4000)
    try:
        price = float(request.form.get("price", "0") or 0)
        if price < 0:
            price = 0.0
    except (TypeError, ValueError):
        price = 0.0
    try:
        stock_quantity = int(request.form.get("stock_quantity", "0") or 0)
        if stock_quantity < 0:
            stock_quantity = 0
    except (TypeError, ValueError):
        stock_quantity = 0
    sizes = [sanitize_text(size, 20) for size in request.form.get("sizes", "").split(",") if sanitize_text(size, 20)]
    status = sanitize_text(request.form.get("status", "Active"), 40) or "Active"
    is_outfit = request.form.get("is_outfit") == "1"
    outfit_items = []
    for raw_id in request.form.getlist("outfit_items"):
        try:
            outfit_items.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    image_url = sanitize_url(request.form.get("image_url", ""), 1200)
    uploaded = save_image(request.files.get("image_file"), f"seller-product-{current_user.get_id()}")
    if uploaded:
        image_url = uploaded
    elif product and product.image_url:
        image_url = product.image_url
    return {
        "title": title,
        "category": category,
        "description": description,
        "price": round(price, 2),
        "stock_quantity": stock_quantity,
        "sizes": sizes,
        "status": status if status in PRODUCT_STATUS_OPTIONS else "Active",
        "is_outfit": is_outfit,
        "outfit_items": outfit_items,
        "image_url": image_url,
    }


@bp.get("/sell")
def entry():
    if current_user.is_authenticated and current_user.has_role("seller"):
        profile = seller_profile()
        if profile and profile.onboarding_complete:
            return redirect(url_for("seller.dashboard"))
        return redirect(url_for("seller.onboarding"))
    return render_template("seller/entry.html")


@bp.route("/seller/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    maybe_redirect = ensure_seller_account()
    if maybe_redirect:
        return maybe_redirect

    profile = seller_profile()
    if not profile:
        profile = SellerProfile(
            user_id=int(current_user.get_id()),
            brand_name=sanitize_text(current_user.email.split("@")[0].replace(".", " ").title(), 180) or "StyleBridge Seller",
            slug=unique_brand_slug(current_user.email.split("@")[0]),
            contact_email=current_user.email,
            contact_phone=current_user.phone,
            onboarding_complete=False,
        )
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        brand_name = sanitize_text(request.form.get("brand_name", ""), 180)
        if not brand_name:
            flash("Brand name is required.", "error")
            return render_template("seller/onboarding.html", profile=profile, business_type_options=BUSINESS_TYPE_OPTIONS), 400

        logo_url = sanitize_url(request.form.get("logo_url", ""), 1200) or profile.logo_url or ""
        banner_url = sanitize_url(request.form.get("banner_url", ""), 1200) or profile.banner_url or ""
        try:
            uploaded_logo = save_image(request.files.get("logo_file"), f"seller-logo-{current_user.get_id()}")
            uploaded_banner = save_image(request.files.get("banner_file"), f"seller-banner-{current_user.get_id()}")
        except UploadStorageError as exc:
            flash(str(exc), "error")
            return render_template("seller/onboarding.html", profile=profile, business_type_options=BUSINESS_TYPE_OPTIONS), 500
        if uploaded_logo:
            logo_url = uploaded_logo
        if uploaded_banner:
            banner_url = uploaded_banner

        profile.brand_name = brand_name
        profile.slug = unique_brand_slug(brand_name, profile.id)
        profile.location = sanitize_text(request.form.get("location", ""), 180)
        profile.contact_email = sanitize_text(request.form.get("contact_email", ""), 220) or current_user.email
        profile.contact_phone = sanitize_text(request.form.get("contact_phone", ""), 40) or current_user.phone
        profile.business_type = sanitize_text(request.form.get("business_type", ""), 80)
        profile.logo_url = logo_url
        profile.banner_url = banner_url
        profile.mobile_money_number = sanitize_text(request.form.get("mobile_money_number", ""), 80)
        profile.bank_account_name = sanitize_text(request.form.get("bank_account_name", ""), 160)
        profile.bank_account_number = sanitize_text(request.form.get("bank_account_number", ""), 120)
        profile.bank_name = sanitize_text(request.form.get("bank_name", ""), 160)
        profile.shipping_pricing = sanitize_text(request.form.get("shipping_pricing", ""), 200)
        profile.about = sanitize_text(request.form.get("about", ""), 2500)
        profile.set_delivery_areas(
            [sanitize_text(area, 80) for area in request.form.get("delivery_areas", "").split(",") if sanitize_text(area, 80)]
        )
        profile.onboarding_complete = True
        current_user.phone = profile.contact_phone or current_user.phone
        db.session.commit()
        audit("seller.onboarding_completed", target=f"seller:{profile.id}", meta={"brand_name": profile.brand_name})
        flash("Seller profile created.", "success")
        return redirect(url_for("seller.dashboard"))

    return render_template("seller/onboarding.html", profile=profile, business_type_options=BUSINESS_TYPE_OPTIONS)


@bp.get("/seller/dashboard")
@login_required
def dashboard():
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response
    stats = seller_dashboard_stats(profile)
    return render_template("seller/dashboard.html", profile=profile, stats=stats)


@bp.route("/seller/products/new", methods=["GET", "POST"])
@login_required
def product_create():
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response

    existing_products = SellerProduct.query.filter_by(seller_id=profile.id).order_by(SellerProduct.title.asc()).all()
    if request.method == "POST":
        try:
            payload = product_payload_from_form()
        except UploadStorageError as exc:
            flash(str(exc), "error")
            return render_template(
                "seller/product_form.html",
                profile=profile,
                product=None,
                existing_products=existing_products,
                category_options=PRODUCT_CATEGORY_OPTIONS,
                status_options=PRODUCT_STATUS_OPTIONS,
            ), 500
        if not payload["title"] or not payload["category"] or not payload["image_url"]:
            flash("Title, category, and an image are required.", "error")
            return render_template(
                "seller/product_form.html",
                profile=profile,
                product=None,
                existing_products=existing_products,
                category_options=PRODUCT_CATEGORY_OPTIONS,
                status_options=PRODUCT_STATUS_OPTIONS,
            ), 400

        product = SellerProduct(
            seller_id=profile.id,
            title=payload["title"],
            category=payload["category"],
            price=payload["price"],
            description=payload["description"],
            stock_quantity=payload["stock_quantity"],
            image_url=payload["image_url"],
            status="Out of stock" if payload["stock_quantity"] == 0 else payload["status"],
            is_outfit=payload["is_outfit"],
        )
        product.set_sizes(payload["sizes"])
        product.set_outfit_items(payload["outfit_items"])
        db.session.add(product)
        db.session.commit()
        audit("seller.product_created", target=f"seller_product:{product.id}", meta={"seller_id": profile.id})
        flash("Product saved.", "success")
        return redirect(url_for("seller.dashboard"))

    return render_template(
        "seller/product_form.html",
        profile=profile,
        product=None,
        existing_products=existing_products,
        category_options=PRODUCT_CATEGORY_OPTIONS,
        status_options=PRODUCT_STATUS_OPTIONS,
    )


@bp.route("/seller/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def product_edit(product_id: int):
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response

    product = SellerProduct.query.filter_by(id=product_id, seller_id=profile.id).first_or_404()
    existing_products = SellerProduct.query.filter_by(seller_id=profile.id).order_by(SellerProduct.title.asc()).all()

    if request.method == "POST":
        try:
            payload = product_payload_from_form(product)
        except UploadStorageError as exc:
            flash(str(exc), "error")
            return render_template(
                "seller/product_form.html",
                profile=profile,
                product=product,
                existing_products=existing_products,
                category_options=PRODUCT_CATEGORY_OPTIONS,
                status_options=PRODUCT_STATUS_OPTIONS,
            ), 500
        if not payload["title"] or not payload["category"] or not payload["image_url"]:
            flash("Title, category, and an image are required.", "error")
            return render_template(
                "seller/product_form.html",
                profile=profile,
                product=product,
                existing_products=existing_products,
                category_options=PRODUCT_CATEGORY_OPTIONS,
                status_options=PRODUCT_STATUS_OPTIONS,
            ), 400

        product.title = payload["title"]
        product.category = payload["category"]
        product.price = payload["price"]
        product.description = payload["description"]
        product.stock_quantity = payload["stock_quantity"]
        product.image_url = payload["image_url"]
        product.status = "Out of stock" if payload["stock_quantity"] == 0 else payload["status"]
        product.is_outfit = payload["is_outfit"]
        product.set_sizes(payload["sizes"])
        product.set_outfit_items(payload["outfit_items"])
        db.session.commit()
        audit("seller.product_updated", target=f"seller_product:{product.id}", meta={"seller_id": profile.id})
        flash("Product updated.", "success")
        return redirect(url_for("seller.dashboard"))

    return render_template(
        "seller/product_form.html",
        profile=profile,
        product=product,
        existing_products=existing_products,
        category_options=PRODUCT_CATEGORY_OPTIONS,
        status_options=PRODUCT_STATUS_OPTIONS,
    )


@bp.post("/seller/products/<int:product_id>/delete")
@login_required
def product_delete(product_id: int):
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response
    product = SellerProduct.query.filter_by(id=product_id, seller_id=profile.id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    audit("seller.product_deleted", target=f"seller_product:{product_id}", meta={"seller_id": profile.id})
    flash("Product removed.", "info")
    return redirect(url_for("seller.dashboard"))


@bp.post("/seller/products/<int:product_id>/status")
@login_required
def product_status(product_id: int):
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response
    product = SellerProduct.query.filter_by(id=product_id, seller_id=profile.id).first_or_404()
    status = sanitize_text(request.form.get("status", ""), 40)
    if status in PRODUCT_STATUS_OPTIONS:
        product.status = status
        if status == "Out of stock":
            product.stock_quantity = 0
        db.session.commit()
        audit("seller.product_status_updated", target=f"seller_product:{product.id}", meta={"status": status})
        flash("Product status updated.", "success")
    return redirect(url_for("seller.dashboard"))


@bp.post("/seller/orders/<int:order_id>/status")
@login_required
def order_status(order_id: int):
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response
    order = SellerOrder.query.filter_by(id=order_id, seller_id=profile.id).first_or_404()
    status = sanitize_text(request.form.get("status", ""), 40)
    if status not in ORDER_STATUS_OPTIONS:
        abort(400)
    order.status = status
    if status == "Delivered":
        order.payout_status = "Available"
    elif status == "Rejected":
        order.payout_status = "Cancelled"
    else:
        order.payout_status = "Pending"
    db.session.commit()
    audit("seller.order_status_updated", target=f"seller_order:{order.id}", meta={"status": status})
    flash("Order status updated.", "success")
    return redirect(url_for("seller.dashboard"))


@bp.post("/seller/payouts/withdraw")
@login_required
def withdraw():
    profile, redirect_response = ensure_seller_ready()
    if redirect_response:
        return redirect_response
    stats = seller_dashboard_stats(profile)
    if stats["available_balance"] <= 0:
        flash("No available balance yet. Delivered orders unlock withdrawals.", "info")
        return redirect(url_for("seller.dashboard"))
    audit("seller.withdraw_requested", target=f"seller:{profile.id}", meta={"amount": stats["available_balance"]})
    flash("Withdrawal request queued for review.", "success")
    return redirect(url_for("seller.dashboard"))


@bp.get("/brands/<slug>")
def brand_page(slug: str):
    profile = SellerProfile.query.filter_by(slug=slug, onboarding_complete=True).first_or_404()
    products = SellerProduct.query.filter_by(seller_id=profile.id).order_by(SellerProduct.created_at.desc()).all()
    active_products = [product for product in products if product.status != "Draft"]
    outfits = [product for product in active_products if product.is_outfit]
    items = [product for product in active_products if not product.is_outfit]
    delivered_orders = SellerOrder.query.filter_by(seller_id=profile.id, status="Delivered").count()
    return render_template(
        "seller/brand_page.html",
        profile=profile,
        products=items,
        outfits=outfits,
        delivered_orders=delivered_orders,
    )


@bp.get("/brands/<slug>/products/<int:product_id>")
def brand_product_detail(slug: str, product_id: int):
    profile = SellerProfile.query.filter_by(slug=slug, onboarding_complete=True).first_or_404()
    product = SellerProduct.query.filter_by(id=product_id, seller_id=profile.id).first_or_404()
    product.views_count += 1
    db.session.commit()
    related = (
        SellerProduct.query.filter(SellerProduct.seller_id == profile.id, SellerProduct.id != product.id)
        .order_by(SellerProduct.orders_count.desc(), SellerProduct.views_count.desc())
        .limit(4)
        .all()
    )
    outfit_products = []
    if product.is_outfit and product.get_outfit_items():
        outfit_products = SellerProduct.query.filter(
            SellerProduct.seller_id == profile.id,
            SellerProduct.id.in_(product.get_outfit_items()),
        ).all()
    return render_template(
        "seller/brand_product_detail.html",
        profile=profile,
        product=product,
        related=related,
        outfit_products=outfit_products,
    )


@bp.post("/brands/products/<int:product_id>/add")
def brand_product_add_to_cart(product_id: int):
    product = SellerProduct.query.get_or_404(product_id)
    if product.status == "Out of stock" or product.stock_quantity <= 0:
        flash("That item is out of stock.", "error")
        return redirect(url_for("seller.brand_product_detail", slug=product.seller.slug, product_id=product.id))

    cart = session.setdefault("cart", [])
    item_id = f"seller-product:{product.id}"
    existing = next((item for item in cart if item.get("id") == item_id), None)
    if existing:
        existing["quantity"] = int(existing.get("quantity", 1)) + 1
    else:
        cart.append(
            {
                "id": item_id,
                "seller_product_id": product.id,
                "seller_profile_id": product.seller_id,
                "look_slug": "",
                "look_title": product.seller.brand_name,
                "title": product.title,
                "brand": product.seller.brand_name,
                "price": product.price,
                "quantity": 1,
            }
        )
    session.modified = True
    flash("Added to cart.", "success")
    return redirect(url_for("main.cart"))
