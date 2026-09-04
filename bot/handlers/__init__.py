from aiogram import Router

from bot.handlers.moderate import router as moderate_router
from bot.handlers.search import router as search_router
from bot.handlers.submit import router as submit_router


def get_root_router() -> Router:
    root = Router(name="root")
    root.include_router(submit_router)
    root.include_router(moderate_router)
    root.include_router(search_router)
    return root
