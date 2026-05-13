"""Add wardrobe, saved worlds, identity events, recommendation history, and orders tables

Revision ID: a3df1b67c2d4
Revises: 55a27275fadb
Create Date: 2026-05-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3df1b67c2d4'
down_revision = '55a27275fadb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wardrobe_item',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('title', sa.String(length=220), nullable=False),
        sa.Column('category', sa.String(length=120), nullable=False, server_default='Accessory'),
        sa.Column('color', sa.String(length=80), nullable=True),
        sa.Column('texture', sa.String(length=120), nullable=True),
        sa.Column('occasion', sa.String(length=120), nullable=True),
        sa.Column('layer_role', sa.String(length=120), nullable=True),
        sa.Column('silhouette', sa.String(length=80), nullable=True),
        sa.Column('fit', sa.String(length=80), nullable=True),
        sa.Column('layering_potential', sa.Float(), nullable=True),
        sa.Column('color_palette', sa.String(length=80), nullable=True),
        sa.Column('material_appearance', sa.String(length=80), nullable=True),
        sa.Column('formality_level', sa.Float(), nullable=True),
        sa.Column('visual_aggression', sa.Float(), nullable=True),
        sa.Column('aesthetic_category', sa.String(length=120), nullable=True),
        sa.Column('fashion_era_influence', sa.String(length=80), nullable=True),
        sa.Column('image_url', sa.String(length=1200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'saved_world',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('slug', sa.String(length=120), nullable=False, index=True),
        sa.Column('source', sa.String(length=80), nullable=False, server_default='user_action'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'identity_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('type', sa.String(length=80), nullable=False, index=True),
        sa.Column('source', sa.String(length=80), nullable=True),
        sa.Column('world_slug', sa.String(length=80), nullable=True, index=True),
        sa.Column('look_slug', sa.String(length=80), nullable=True, index=True),
        sa.Column('recommendation_slug', sa.String(length=80), nullable=True, index=True),
        sa.Column('duration_ms', sa.Integer(), nullable=False, default=0),
        sa.Column('hover_ms', sa.Integer(), nullable=False, default=0),
        sa.Column('meta_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
    )

    op.create_table(
        'recommendation_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('world_slug', sa.String(length=80), nullable=True, index=True),
        sa.Column('recommendation_slug', sa.String(length=120), nullable=True, index=True),
        sa.Column('look_slug', sa.String(length=120), nullable=True, index=True),
        sa.Column('score', sa.Float(), nullable=False, default=0.0),
        sa.Column('source', sa.String(length=80), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
    )

    op.create_table(
        'user_order',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('reference', sa.String(length=120), nullable=False, unique=True, index=True),
        sa.Column('items_json', sa.Text(), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=False, default=0.0),
        sa.Column('payment_method', sa.String(length=80), nullable=True),
        sa.Column('shipping_name', sa.String(length=120), nullable=True),
        sa.Column('shipping_address', sa.String(length=240), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='Pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
    )


def downgrade():
    op.drop_table('user_order')
    op.drop_table('recommendation_history')
    op.drop_table('identity_event')
    op.drop_table('saved_world')
    op.drop_table('wardrobe_item')
