from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultCachedMpeg4Gif,
    InlineQueryResultCachedPhoto,
    InlineQueryResultCachedSticker,
    InlineQueryResultCachedVideo,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Meme, Tag

router = Router(name="search")

RESULT_BY_TYPE = {
    "photo": lambda m: InlineQueryResultCachedPhoto(id=str(m.id), photo_file_id=m.file_id),
    "animation": lambda m: InlineQueryResultCachedMpeg4Gif(id=str(m.id), mpeg4_file_id=m.file_id),
    "video": lambda m: InlineQueryResultCachedVideo(
        id=str(m.id), video_file_id=m.file_id, title=m.name or "meme"
    ),
    "sticker": lambda m: InlineQueryResultCachedSticker(id=str(m.id), sticker_file_id=m.file_id),
}


@router.inline_query()
async def inline_search(query: InlineQuery, session: AsyncSession):
    text = query.query.strip()

    stmt = select(Meme).where(Meme.status == "approved").limit(50)
    if text:
        stmt = stmt.outerjoin(Meme.tags).where(
            or_(
                Meme.name.ilike(f"%{text}%"),
                Meme.description.ilike(f"%{text}%"),
                Tag.name.ilike(f"%{text}%"),
            )
        ).distinct()

    result = await session.execute(stmt)
    memes = result.scalars().unique().all()

    await query.answer(
        [RESULT_BY_TYPE[m.media_type](m) for m in memes if m.media_type in RESULT_BY_TYPE],
        cache_time=30,
        is_personal=False,
    )
