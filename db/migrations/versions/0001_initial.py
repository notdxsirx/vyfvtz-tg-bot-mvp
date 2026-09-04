"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "memes",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("file_id", sa.Text, nullable=False),
        sa.Column("file_unique_id", sa.Text, nullable=False, unique=True),
        sa.Column("media_type", sa.Text, nullable=False),
        sa.Column("phash", sa.BigInteger, nullable=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("submitted_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_memes_status", "memes", ["status"])
    op.execute(
        "CREATE INDEX idx_memes_name_trgm ON memes USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_memes_description_trgm ON memes USING gin (description gin_trgm_ops)"
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("category", sa.Text, nullable=True),
    )
    op.execute("CREATE INDEX idx_tags_name_trgm ON tags USING gin (name gin_trgm_ops)")

    op.create_table(
        "meme_tags",
        sa.Column("meme_id", sa.BigInteger, sa.ForeignKey("memes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.BigInteger, sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("meme_tags")
    op.drop_table("tags")
    op.drop_table("memes")
