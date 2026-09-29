import asyncio
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.models import Meme, Tag, normalize_tag_name
from bot.utils.phash import compute_phash, find_duplicate

router = Router(name="submit")

MEDIA_TYPES = {
    "photo": lambda m: m.photo[-1] if m.photo else None,
    "animation": lambda m: m.animation,
    "video": lambda m: m.video,
    "sticker": lambda m: m.sticker,
}

CAPTION_HELP = (
    "Отправь медиа с подписью в формате:\n"
    "<code>Название | Описание | тег1,тег2,тег3</code>"
)


@router.message(Command("submit"))
async def submit_help(message: Message):
    await message.answer(CAPTION_HELP)


async def get_or_create_tag(session: AsyncSession, raw_name: str) -> Tag:
    """Race-safe get-or-create. Two concurrent /submit calls with the same new tag
    used to both try to INSERT and one would hit IntegrityError unhandled, killing
    the handler. ON CONFLICT DO NOTHING + re-select sidesteps that."""
    name = normalize_tag_name(raw_name)

    tag = await session.scalar(select(Tag).where(Tag.name == name))
    if tag:
        return tag

    stmt = (
        pg_insert(Tag)
        .values(name=name)
        # target the functional unique index on lower(name) directly, since that's the
        # actual constraint (plain-column uniqueness was dropped in favor of it)
        .on_conflict_do_nothing(index_elements=[func.lower(Tag.name)])
    )
    await session.execute(stmt)

    # Either our insert landed, or a concurrent one did — either way it's there now.
    tag = await session.scalar(select(Tag).where(Tag.name == name))
    assert tag is not None
    return tag


@router.message(F.photo | F.animation | F.video | F.sticker)
async def handle_submission(message: Message, bot: Bot, session: AsyncSession):
    media_type = next(k for k, get in MEDIA_TYPES.items() if get(message))
    file_obj = MEDIA_TYPES[media_type](message)

    if not message.caption or "|" not in message.caption:
        await message.reply(CAPTION_HELP)
        return

    parts = [p.strip() for p in message.caption.split("|")]
    name = parts[0] if len(parts) > 0 else None
    description = parts[1] if len(parts) > 1 else None
    tag_names = [t.strip() for t in parts[2].split(",")] if len(parts) > 2 and parts[2] else []

    existing = await session.scalar(
        select(Meme).where(Meme.file_unique_id == file_obj.file_unique_id)
    )
    if existing:
        await message.reply("Этот файл уже был отправлен раньше.")
        return

    phash = None
    storage_path = None
    if media_type == "photo":
        file = await bot.get_file(file_obj.file_id)
        buf = await bot.download_file(file.file_path)
        raw = buf.read()

        # CPU-bound (PIL decode + DCT) — keep it off the event loop or the whole bot
        # stalls for every other chat while one submission is being hashed.
        phash = await asyncio.to_thread(compute_phash, raw)
        dup = await find_duplicate(session, phash)
        if dup:
            await message.reply(f"Похоже на уже существующий мем (id={dup.id}).")
            return

        # file_id is not permanent (invalidated on Telegram-side server migrations,
        # bot recreation, etc.) — keep our own copy now, while we already have the bytes,
        # so old memes don't become unrecoverable later.
        ext = Path(file.file_path).suffix or ".jpg"
        storage_path = f"{file_obj.file_unique_id}{ext}"
        full_path = settings.media_root / storage_path
        await asyncio.to_thread(full_path.write_bytes, raw)

    tags = [await get_or_create_tag(session, tag_name) for tag_name in tag_names]

    meme = Meme(
        file_id=file_obj.file_id,
        file_unique_id=file_obj.file_unique_id,
        media_type=media_type,
        phash=phash,
        name=name,
        description=description,
        submitted_by=message.from_user.id,
        status="pending",
        storage_path=storage_path,
        tags=tags,  # set at construction time — avoids a lazy-load on a persistent object later
    )
    session.add(meme)

    await session.commit()
    await message.reply("Отправлено на модерацию.")
