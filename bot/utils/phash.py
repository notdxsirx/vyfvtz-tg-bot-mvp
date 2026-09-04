from io import BytesIO

import imagehash
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.models import Meme


def compute_phash(image_bytes: bytes) -> int:
    img = Image.open(BytesIO(image_bytes))
    unsigned = int(str(imagehash.phash(img)), 16)
    # BIGINT is signed 64-bit; imagehash gives unsigned 64-bit — wrap into signed range
    return unsigned - 2**64 if unsigned >= 2**63 else unsigned


async def find_duplicate(session: AsyncSession, phash: int) -> Meme | None:
    """Naive O(n) scan against approved memes. Fine for MVP-scale (<10k rows).
    Replace with a proper nearest-neighbor index (e.g. pgvector + BK-tree) if it grows."""
    result = await session.execute(
        select(Meme).where(Meme.status == "approved", Meme.phash.is_not(None))
    )
    for meme in result.scalars():
        distance = bin((meme.phash ^ phash) & 0xFFFFFFFFFFFFFFFF).count("1")
        if distance <= settings.phash_distance_threshold:
            return meme
    return None
