from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Table, Column, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


meme_tags = Table(
    "meme_tags",
    Base.metadata,
    Column("meme_id", BigInteger, ForeignKey("memes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Meme(Base):
    __tablename__ = "memes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    file_id: Mapped[str]
    file_unique_id: Mapped[str] = mapped_column(unique=True)
    media_type: Mapped[str]  # photo/video/animation/sticker
    phash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str | None]
    description: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="pending")  # pending/approved/rejected
    submitted_by: Mapped[int] = mapped_column(BigInteger)
    storage_path: Mapped[str | None]  # relative path under MEDIA_ROOT; our own copy of the bytes
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tags: Mapped[list["Tag"]] = relationship(secondary=meme_tags, back_populates="memes")

    __table_args__ = (
        Index("idx_memes_status", "status"),
        Index("idx_memes_status_id", "status", "id"),
        Index("idx_memes_submitted_by", "submitted_by"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column()  # store already normalized (stripped + lowered); see normalize_tag_name()
    category: Mapped[str | None]

    memes: Mapped[list["Meme"]] = relationship(secondary=meme_tags, back_populates="tags")

    __table_args__ = (
        # Case-insensitive uniqueness. Values are normalized before insert (see normalize_tag_name),
        # but the functional index on lower(name) is the actual DB-level guarantee.
        Index("idx_tags_name_lower_unique", func.lower(name), unique=True),
    )


def normalize_tag_name(raw: str) -> str:
    return raw.strip().lower()
