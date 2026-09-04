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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tags: Mapped[list["Tag"]] = relationship(secondary=meme_tags, back_populates="memes")

    __table_args__ = (Index("idx_memes_status", "status"),)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    category: Mapped[str | None]

    memes: Mapped[list["Meme"]] = relationship(secondary=meme_tags, back_populates="tags")
