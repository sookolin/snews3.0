"""Media service — downloading remote media and applying watermarks/spoilers."""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.enums import MediaType
from shared.logging import get_logger
from shared.models.media import MediaAsset
from shared.models.watermark import WatermarkProfile
from shared.services.watermark import WatermarkService

log = get_logger("media")

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


class MediaService:
    """Download, store and process media assets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _abs(self, rel_path: str) -> str:
        return os.path.join(settings.media_root, rel_path)

    async def download(self, url: str, subdir: str = "downloads") -> tuple[str, str | None, int]:
        """Download ``url`` into MEDIA_ROOT. Returns (rel_path, mime, size)."""
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or ".bin"
        rel_dir = os.path.join(subdir)
        os.makedirs(self._abs(rel_dir), exist_ok=True)
        rel_path = os.path.join(rel_dir, f"{uuid.uuid4().hex}{ext}")
        abs_path = self._abs(rel_path)

        async with (
            httpx.AsyncClient(follow_redirects=True, timeout=60) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            mime = response.headers.get("content-type")
            size = 0
            with open(abs_path, "wb") as fh:
                async for chunk in response.aiter_bytes(65536):
                    fh.write(chunk)
                    size += len(chunk)
        log.debug("media_downloaded", url=url, path=rel_path, size=size)
        return rel_path, mime, size

    async def _default_watermark(self) -> WatermarkProfile | None:
        return await self.session.scalar(
            select(WatermarkProfile)
            .where(WatermarkProfile.is_default.is_(True), WatermarkProfile.is_active.is_(True))
            .limit(1)
        )

    async def process_asset(self, asset: MediaAsset, apply_watermark: bool = True) -> None:
        """Watermark an image/video asset in place (sets ``processed_path``)."""
        source_rel = asset.file_path
        if not source_rel:
            return
        src_abs = self._abs(source_rel)
        if not os.path.exists(src_abs):
            log.warning("media_missing", asset=asset.id, path=source_rel)
            return

        if not apply_watermark or asset.type not in (
            MediaType.PHOTO,
            MediaType.VIDEO,
            MediaType.ANIMATION,
        ):
            asset.processed_path = source_rel
            return

        profile = await self._default_watermark()
        if profile is None:
            asset.processed_path = source_rel
            return

        base, ext = os.path.splitext(source_rel)
        processed_rel = f"{base}_wm{ext}"
        service = WatermarkService(profile)
        try:
            if asset.type == MediaType.PHOTO:
                await service.apply_image(src_abs, self._abs(processed_rel))
            else:
                await service.apply_video(src_abs, self._abs(processed_rel))
            asset.processed_path = processed_rel
        except Exception as exc:  # noqa: BLE001
            log.error("watermark_failed", asset=asset.id, error=str(exc))
            asset.processed_path = source_rel

    @staticmethod
    def guess_type(mime: str | None, url: str) -> MediaType:
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if mime:
            if mime.startswith("image/gif") or ext == ".gif":
                return MediaType.ANIMATION
            if mime.startswith("image"):
                return MediaType.PHOTO
            if mime.startswith("video"):
                return MediaType.VIDEO
            if mime.startswith("audio"):
                return MediaType.AUDIO
        if ext in _IMAGE_EXT:
            return MediaType.ANIMATION if ext == ".gif" else MediaType.PHOTO
        if ext in _VIDEO_EXT:
            return MediaType.VIDEO
        return MediaType.DOCUMENT
