import asyncio
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


def _scan_for_match(candidates: list[Meme], phash: int, threshold: int) -> Meme | None:
    """CPU-bound Hamming-distance scan. Call via asyncio.to_thread — never await this directly."""
    for meme in candidates:
        distance = bin((meme.phash ^ phash) & 0xFFFFFFFFFFFFFFFF).count("1")
        if distance <= threshold:
            return meme
    return None


async def find_duplicate(session: AsyncSession, phash: int) -> Meme | None:
    """Naive O(n) scan against approved memes. Fine for MVP-scale (<10k rows).
    Replace with a proper nearest-neighbor index (e.g. pgvector + BK-tree) if it grows.

    The DB fetch stays on the event loop (it's async I/O); the actual Hamming-distance
    loop is CPU-bound and synchronous, so it's shipped off to a thread to avoid blocking
    every other update while it runs.
    """
    result = await session.execute(
        select(Meme).where(Meme.status == "approved", Meme.phash.is_not(None))
    )
    candidates = list(result.scalars())
    return await asyncio.to_thread(
        _scan_for_match, candidates, phash, settings.phash_distance_threshold
    )
