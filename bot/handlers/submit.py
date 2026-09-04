from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Meme, Tag
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
    if media_type == "photo":
        file = await bot.get_file(file_obj.file_id)
        buf = await bot.download_file(file.file_path)
        phash = compute_phash(buf.read())
        dup = await find_duplicate(session, phash)
        if dup:
            await message.reply(f"Похоже на уже существующий мем (id={dup.id}).")
            return

    tags = []
    for tag_name in tag_names:
        tag = await session.scalar(select(Tag).where(Tag.name == tag_name))
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
        tags.append(tag)

    meme = Meme(
        file_id=file_obj.file_id,
        file_unique_id=file_obj.file_unique_id,
        media_type=media_type,
        phash=phash,
        name=name,
        description=description,
        submitted_by=message.from_user.id,
        status="pending",
        tags=tags,  # set at construction time — avoids a lazy-load on a persistent object later
    )
    session.add(meme)

    await session.commit()
    await message.reply("Отправлено на модерацию.")
