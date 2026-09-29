"""tag normalization, tags.id type fix, missing indexes, media storage_path

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Tag normalization -------------------------------------------------
    # Collapse existing case/whitespace duplicates ("Мем"/"мем"/"МЕМ") onto one row
    # before adding the case-insensitive unique index, or the index creation will
    # fail on the first duplicate it finds.
    op.execute(
        """
        WITH normalized AS (
            SELECT id, TRIM(LOWER(name)) AS norm_name
            FROM tags
        ),
        canonical AS (
            -- keep the lowest id per normalized name as the row we merge onto
            SELECT norm_name, MIN(id) AS keep_id
            FROM normalized
            GROUP BY norm_name
        ),
        remap AS (
            SELECT n.id AS dup_id, c.keep_id
            FROM normalized n
            JOIN canonical c ON c.norm_name = n.norm_name
            WHERE n.id <> c.keep_id
        )
        -- repoint meme_tags rows from duplicate tag ids to the canonical id,
        -- skipping ones that would create a duplicate (meme_id, tag_id) pair
        UPDATE meme_tags mt
        SET tag_id = r.keep_id
        FROM remap r
        WHERE mt.tag_id = r.dup_id
          AND NOT EXISTS (
              SELECT 1 FROM meme_tags mt2
              WHERE mt2.meme_id = mt.meme_id AND mt2.tag_id = r.keep_id
          )
        """
    )
    # drop now-unreferenceable meme_tags rows left pointing at a duplicate tag
    # (the ones that would've collided above and were skipped)
    op.execute(
        """
        WITH normalized AS (
            SELECT id, TRIM(LOWER(name)) AS norm_name FROM tags
        ),
        canonical AS (
            SELECT norm_name, MIN(id) AS keep_id FROM normalized GROUP BY norm_name
        )
        DELETE FROM meme_tags mt
        USING normalized n, canonical c
        WHERE mt.tag_id = n.id AND n.norm_name = c.norm_name AND n.id <> c.keep_id
        """
    )
    # delete the now-orphaned duplicate tag rows
    op.execute(
        """
        WITH normalized AS (
            SELECT id, TRIM(LOWER(name)) AS norm_name FROM tags
        ),
        canonical AS (
            SELECT norm_name, MIN(id) AS keep_id FROM normalized GROUP BY norm_name
        )
        DELETE FROM tags t
        USING normalized n, canonical c
        WHERE t.id = n.id AND n.norm_name = c.norm_name AND n.id <> c.keep_id
        """
    )
    # normalize the surviving rows' text in place
    op.execute("UPDATE tags SET name = TRIM(LOWER(name))")

    # plain unique constraint -> case-insensitive functional unique index
    op.drop_constraint("tags_name_key", "tags", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX idx_tags_name_lower_unique ON tags (LOWER(name))"
    )

    # --- 2. tags.id type mismatch (Integer -> BigInteger, matches meme_tags.tag_id) --
    op.alter_column("tags", "id", type_=sa.BigInteger)

    # --- 3. missing indexes for moderation queue / user history queries --------
    op.create_index("idx_memes_status_id", "memes", ["status", "id"])
    op.create_index("idx_memes_submitted_by", "memes", ["submitted_by"])

    # --- 4. our own copy of media bytes (file_id is not permanent) -------------
    op.add_column("memes", sa.Column("storage_path", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("memes", "storage_path")
    op.drop_index("idx_memes_submitted_by", table_name="memes")
    op.drop_index("idx_memes_status_id", table_name="memes")
    op.alter_column("tags", "id", type_=sa.Integer)
    op.drop_index("idx_tags_name_lower_unique", table_name="tags")
    op.create_unique_constraint("tags_name_key", "tags", ["name"])
