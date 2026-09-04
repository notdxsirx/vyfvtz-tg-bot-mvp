from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.models import Meme

router = Router(name="moderate")


def _caption(meme: Meme) -> str:
    tags = ", ".join(t.name for t in meme.tags) or "-"
    return f"{meme.name or '-'}\n{meme.description or '-'}\nТеги: {tags}\nid={meme.id}"


def _kb(meme_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve", callback_data=f"mod:approve:{meme_id}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"mod:reject:{meme_id}"),
    ]])


SEND_BY_TYPE = {
    "photo": "send_photo",
    "animation": "send_animation",
    "video": "send_video",
    "sticker": "send_sticker",
}


async def _send_next_pending(bot: Bot, chat_id: int, session: AsyncSession) -> None:
    meme = await session.scalar(
        select(Meme)
        .options(selectinload(Meme.tags))
        .where(Meme.status == "pending")
        .order_by(Meme.id)
        .limit(1)
    )
    if not meme:
        await bot.send_message(chat_id, "Очередь модерации пуста.")
        return

    method_name = SEND_BY_TYPE.get(meme.media_type)
    if not method_name:
        await bot.send_message(chat_id, f"Неизвестный media_type={meme.media_type}, id={meme.id}")
        return

    send = getattr(bot, method_name)
    kwargs = {"chat_id": chat_id, "reply_markup": _kb(meme.id)}
    if meme.media_type == "sticker":
        await send(sticker=meme.file_id, **kwargs)
    else:
        await send(**{f"{meme.media_type}": meme.file_id}, caption=_caption(meme), **kwargs)


@router.message(Command("moderate"))
async def moderate_cmd(message: Message, bot: Bot, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids:
        return
    await _send_next_pending(bot, message.chat.id, session)


@router.callback_query(F.data.startswith("mod:"))
async def handle_moderation(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, action, meme_id = callback.data.split(":")
    meme = await session.scalar(select(Meme).where(Meme.id == int(meme_id)))
    if not meme:
        await callback.answer("Мем не найден.", show_alert=True)
        return

    meme.status = "approved" if action == "approve" else "rejected"
    await session.commit()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(f"Статус: {meme.status}")

    await _send_next_pending(bot, callback.message.chat.id, session)
