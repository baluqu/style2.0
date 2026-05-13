from __future__ import annotations

import json
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db


user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(220), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    onboarding_complete = db.Column(db.Boolean, nullable=False, default=False)
    profile_json = db.Column(db.Text, nullable=True)
    profile_vector_json = db.Column(db.Text, nullable=True)
    saved_looks_json = db.Column(db.Text, nullable=True)
    order_history_json = db.Column(db.Text, nullable=True)
    password_reset_token = db.Column(db.String(120), nullable=True, index=True)
    password_reset_expires_at = db.Column(db.DateTime, nullable=True)
    # Legacy flag (kept for backward compatibility); RBAC uses roles.
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    roles = db.relationship("Role", secondary=user_roles, lazy="selectin")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, role_name: str) -> bool:
        rn = role_name.strip().lower()
        return any((r.name or "").lower() == rn for r in (self.roles or []))

    def is_seller_account(self) -> bool:
        return self.has_role("seller")

    def _load_json_text(self, raw_value: str | None, default):
        if not raw_value:
            return default
        try:
            return json.loads(raw_value)
        except (TypeError, ValueError):
            return default

    def get_profile_data(self) -> dict:
        return self._load_json_text(self.profile_json, {})

    def set_profile_data(self, data: dict) -> None:
        self.profile_json = json.dumps(data)

    def get_profile_vector(self) -> dict:
        return self._load_json_text(self.profile_vector_json, {})

    def set_profile_vector(self, data: dict) -> None:
        self.profile_vector_json = json.dumps(data)

    def get_saved_looks(self) -> list[str]:
        return self._load_json_text(self.saved_looks_json, [])

    def set_saved_looks(self, data: list[str]) -> None:
        self.saved_looks_json = json.dumps(data)

    def get_order_history(self) -> list[dict]:
        return self._load_json_text(self.order_history_json, [])

    def set_order_history(self, data: list[dict]) -> None:
        self.order_history_json = json.dumps(data)

    def get_wardrobe_items(self) -> list[dict]:
        return [item.to_dict() for item in getattr(self, "wardrobe_items", []) if hasattr(item, "to_dict")]

    def get_saved_world_slugs(self) -> list[str]:
        return [entry.slug for entry in getattr(self, "saved_worlds", []) if getattr(entry, "slug", None)]

    def get_user_orders(self) -> list[dict]:
        return [order.to_dict() for order in getattr(self, "user_orders", []) if hasattr(order, "to_dict")]

    def get_identity_events(self) -> list[dict]:
        return [event.to_dict() for event in getattr(self, "identity_events", []) if hasattr(event, "to_dict")]


class WardrobeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(120), nullable=False, default="Accessory")
    color = db.Column(db.String(80), nullable=True)
    texture = db.Column(db.String(120), nullable=True)
    occasion = db.Column(db.String(120), nullable=True)
    layer_role = db.Column(db.String(120), nullable=True)
    silhouette = db.Column(db.String(80), nullable=True)
    fit = db.Column(db.String(80), nullable=True)
    layering_potential = db.Column(db.Float, nullable=True)
    color_palette = db.Column(db.String(80), nullable=True)
    material_appearance = db.Column(db.String(80), nullable=True)
    formality_level = db.Column(db.Float, nullable=True)
    visual_aggression = db.Column(db.Float, nullable=True)
    aesthetic_category = db.Column(db.String(120), nullable=True)
    fashion_era_influence = db.Column(db.String(80), nullable=True)
    image_url = db.Column(db.String(1200), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("wardrobe_items", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title or "",
            "category": self.category or "Accessory",
            "color": self.color or "",
            "texture": self.texture or "",
            "occasion": self.occasion or "",
            "layer_role": self.layer_role or "",
            "silhouette": self.silhouette or "",
            "fit": self.fit or "",
            "layering_potential": float(self.layering_potential) if self.layering_potential is not None else "",
            "color_palette": self.color_palette or "",
            "material_appearance": self.material_appearance or "",
            "formality_level": float(self.formality_level) if self.formality_level is not None else "",
            "visual_aggression": float(self.visual_aggression) if self.visual_aggression is not None else "",
            "aesthetic_category": self.aesthetic_category or "",
            "fashion_era_influence": self.fashion_era_influence or "",
            "image_url": self.image_url or "",
            "added_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }


class SavedWorld(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    slug = db.Column(db.String(120), nullable=False, index=True)
    source = db.Column(db.String(80), nullable=False, default="user_action")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("saved_worlds", lazy=True, cascade="all, delete-orphan"))


class IdentityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    type = db.Column(db.String(80), nullable=False, index=True)
    source = db.Column(db.String(80), nullable=True)
    world_slug = db.Column(db.String(80), nullable=True, index=True)
    look_slug = db.Column(db.String(80), nullable=True, index=True)
    recommendation_slug = db.Column(db.String(80), nullable=True, index=True)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    hover_ms = db.Column(db.Integer, nullable=False, default=0)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User", backref=db.backref("identity_events", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self) -> dict:
        return {
            "type": self.type or "",
            "source": self.source or "",
            "world_slug": self.world_slug or "",
            "look_slug": self.look_slug or "",
            "recommendation_slug": self.recommendation_slug or "",
            "duration_ms": int(self.duration_ms or 0),
            "hover_ms": int(self.hover_ms or 0),
            "meta": json.loads(self.meta_json) if self.meta_json else {},
            "timestamp": self.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created_at else "",
        }


class RecommendationHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    world_slug = db.Column(db.String(80), nullable=True, index=True)
    recommendation_slug = db.Column(db.String(120), nullable=True, index=True)
    look_slug = db.Column(db.String(120), nullable=True, index=True)
    score = db.Column(db.Float, nullable=False, default=0.0)
    source = db.Column(db.String(80), nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User", backref=db.backref("recommendation_history", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self) -> dict:
        return {
            "world_slug": self.world_slug or "",
            "recommendation_slug": self.recommendation_slug or "",
            "look_slug": self.look_slug or "",
            "score": float(self.score or 0.0),
            "source": self.source or "",
            "details": json.loads(self.details_json) if self.details_json else {},
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created_at else "",
        }


class UserOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    reference = db.Column(db.String(120), nullable=False, unique=True, index=True)
    items_json = db.Column(db.Text, nullable=True)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(80), nullable=True)
    shipping_name = db.Column(db.String(120), nullable=True)
    shipping_address = db.Column(db.String(240), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="Pending")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User", backref=db.backref("user_orders", lazy=True, cascade="all, delete-orphan"))

    def get_items(self) -> list[dict]:
        if not self.items_json:
            return []
        try:
            return json.loads(self.items_json)
        except (TypeError, ValueError):
            return []

    def set_items(self, items: list[dict]) -> None:
        self.items_json = json.dumps(items)

    def to_dict(self) -> dict:
        return {
            "reference": self.reference,
            "items": self.get_items(),
            "total": float(self.total_amount or 0.0),
            "payment_method": self.payment_method or "",
            "shipping_name": self.shipping_name or "",
            "shipping_address": self.shipping_address or "",
            "status": self.status or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M UTC") if self.created_at else "",
        }


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    image_url = db.Column(db.String(1200), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SellerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    brand_name = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), nullable=False, unique=True, index=True)
    location = db.Column(db.String(180), nullable=True)
    contact_email = db.Column(db.String(220), nullable=True)
    contact_phone = db.Column(db.String(40), nullable=True)
    business_type = db.Column(db.String(80), nullable=True)
    logo_url = db.Column(db.String(1200), nullable=True)
    banner_url = db.Column(db.String(1200), nullable=True)
    mobile_money_number = db.Column(db.String(80), nullable=True)
    bank_account_name = db.Column(db.String(160), nullable=True)
    bank_account_number = db.Column(db.String(120), nullable=True)
    bank_name = db.Column(db.String(160), nullable=True)
    delivery_areas_json = db.Column(db.Text, nullable=True)
    shipping_pricing = db.Column(db.String(200), nullable=True)
    about = db.Column(db.Text, nullable=True)
    onboarding_complete = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("seller_profile", uselist=False))

    def get_delivery_areas(self) -> list[str]:
        if not self.delivery_areas_json:
            return []
        try:
            return json.loads(self.delivery_areas_json)
        except (TypeError, ValueError):
            return []

    def set_delivery_areas(self, areas: list[str]) -> None:
        self.delivery_areas_json = json.dumps(areas)


class SellerProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("seller_profile.id"), nullable=False, index=True)
    title = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text, nullable=True)
    sizes_json = db.Column(db.Text, nullable=True)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(1200), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="Active")
    is_outfit = db.Column(db.Boolean, nullable=False, default=False)
    outfit_items_json = db.Column(db.Text, nullable=True)
    views_count = db.Column(db.Integer, nullable=False, default=0)
    orders_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    seller = db.relationship("SellerProfile", backref=db.backref("products", lazy=True, cascade="all, delete-orphan"))

    def get_sizes(self) -> list[str]:
        if not self.sizes_json:
            return []
        try:
            return json.loads(self.sizes_json)
        except (TypeError, ValueError):
            return []

    def set_sizes(self, sizes: list[str]) -> None:
        self.sizes_json = json.dumps(sizes)

    def get_outfit_items(self) -> list[int]:
        if not self.outfit_items_json:
            return []
        try:
            return json.loads(self.outfit_items_json)
        except (TypeError, ValueError):
            return []

    def set_outfit_items(self, item_ids: list[int]) -> None:
        self.outfit_items_json = json.dumps(item_ids)


class SellerOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("seller_profile.id"), nullable=False, index=True)
    buyer_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    external_reference = db.Column(db.String(120), nullable=False, index=True)
    customer_name = db.Column(db.String(180), nullable=False)
    customer_email = db.Column(db.String(220), nullable=True)
    customer_phone = db.Column(db.String(40), nullable=True)
    delivery_location = db.Column(db.String(240), nullable=False)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(40), nullable=False, default="Pending")
    payout_status = db.Column(db.String(40), nullable=False, default="Pending")
    items_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    seller = db.relationship("SellerProfile", backref=db.backref("orders", lazy=True, cascade="all, delete-orphan"))
    buyer = db.relationship("User", backref=db.backref("seller_orders", lazy=True), foreign_keys=[buyer_user_id])

    def get_items(self) -> list[dict]:
        if not self.items_json:
            return []
        try:
            return json.loads(self.items_json)
        except (TypeError, ValueError):
            return []

    def set_items(self, items: list[dict]) -> None:
        self.items_json = json.dumps(items)


class OAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    token = db.Column(db.JSON, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("oauth_tokens", lazy=True))


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    target = db.Column(db.String(240), nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)


