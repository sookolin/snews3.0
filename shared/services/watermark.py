"""Watermark service — applies a logo/text watermark to images and videos.

Images are processed with Pillow; videos with FFmpeg (overlay filter). The
service is safe to import even when FFmpeg is missing (video calls will raise a
clear error only when actually used).
"""

from __future__ import annotations

import asyncio
import os
import subprocess

from shared.config import settings
from shared.exceptions import AppError
from shared.logging import get_logger
from shared.models.watermark import WatermarkProfile

log = get_logger("watermark")

_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}


class WatermarkService:
    """Apply configurable watermarks to media files."""

    def __init__(self, profile: WatermarkProfile) -> None:
        self.profile = profile

    # ── Public API ───────────────────────────────────────────────────────────
    async def apply_image(self, src_path: str, dst_path: str) -> str:
        """Watermark an image; returns ``dst_path``."""
        await asyncio.to_thread(self._apply_image_sync, src_path, dst_path)
        return dst_path

    async def apply_video(self, src_path: str, dst_path: str) -> str:
        """Watermark a video via FFmpeg; returns ``dst_path``."""
        await asyncio.to_thread(self._apply_video_sync, src_path, dst_path)
        return dst_path

    # ── Image (Pillow) ─────────────────────────────────────────────────────────
    def _apply_image_sync(self, src_path: str, dst_path: str) -> None:
        from PIL import Image, ImageDraw

        base = Image.open(src_path).convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

        if self.profile.logo_path and os.path.exists(self.profile.logo_path):
            logo = Image.open(self.profile.logo_path).convert("RGBA")
            target_w = max(1, int(base.width * self.profile.scale))
            ratio = target_w / logo.width
            logo = logo.resize((target_w, max(1, int(logo.height * ratio))))
            logo = self._apply_opacity(logo, self.profile.opacity)
            x, y = self._position(base.size, logo.size)
            overlay.paste(logo, (x, y), logo)
        elif self.profile.text:
            draw = ImageDraw.Draw(overlay)
            font = self._load_font(self.profile.font_size)
            bbox = draw.textbbox((0, 0), self.profile.text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = self._position(base.size, (tw, th))
            alpha = int(255 * self.profile.opacity)
            if self.profile.shadow:
                draw.text(
                    (x + 2, y + 2),
                    self.profile.text,
                    font=font,
                    fill=(*self._hex(self.profile.shadow_color), alpha),
                )
            draw.text(
                (x, y),
                self.profile.text,
                font=font,
                fill=(*self._hex(self.profile.color), alpha),
            )

        combined = Image.alpha_composite(base, overlay).convert("RGB")
        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        combined.save(dst_path, quality=92)
        log.debug("image_watermarked", dst=dst_path)

    @staticmethod
    def _apply_opacity(image, opacity: float):  # type: ignore[no-untyped-def]
        alpha = image.split()[3]
        alpha = alpha.point(lambda px: int(px * opacity))
        image.putalpha(alpha)
        return image

    def _position(self, base_size: tuple[int, int], obj_size: tuple[int, int]) -> tuple[int, int]:
        bw, bh = base_size
        ow, oh = obj_size
        mx, my = self.profile.margin_x, self.profile.margin_y
        pos = self.profile.position if self.profile.position in _POSITIONS else "bottom-right"
        mapping = {
            "top-left": (mx, my),
            "top-right": (bw - ow - mx, my),
            "bottom-left": (mx, bh - oh - my),
            "bottom-right": (bw - ow - mx, bh - oh - my),
            "center": ((bw - ow) // 2, (bh - oh) // 2),
        }
        return mapping[pos]

    @staticmethod
    def _load_font(size: int):  # type: ignore[no-untyped-def]
        from PIL import ImageFont

        for candidate in (
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arialbd.ttf",
        ):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _hex(color: str) -> tuple[int, int, int]:
        color = color.lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        try:
            return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
        except ValueError:
            return (255, 255, 255)

    # ── Video (FFmpeg) ──────────────────────────────────────────────────────────
    def _apply_video_sync(self, src_path: str, dst_path: str) -> None:
        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        ffmpeg = settings.ffmpeg_binary
        overlay_expr = self._ffmpeg_overlay_expr()

        if self.profile.logo_path and os.path.exists(self.profile.logo_path):
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                src_path,
                "-i",
                self.profile.logo_path,
                "-filter_complex",
                f"[1:v]format=rgba,colorchannelmixer=aa={self.profile.opacity}[wm];"
                f"[0:v][wm]overlay={overlay_expr}",
                "-codec:a",
                "copy",
                dst_path,
            ]
        else:
            text = (self.profile.text or "").replace(":", r"\:").replace("'", r"\'")
            color = self.profile.color
            draw = (
                f"drawtext=text='{text}':fontcolor={color}@{self.profile.opacity}:"
                f"fontsize={self.profile.font_size}:{self._ffmpeg_text_pos()}"
            )
            if self.profile.shadow:
                draw += f":shadowcolor={self.profile.shadow_color}:shadowx=2:shadowy=2"
            cmd = [ffmpeg, "-y", "-i", src_path, "-vf", draw, "-codec:a", "copy", dst_path]

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        except FileNotFoundError as exc:
            raise AppError("FFmpeg binary not found", code="ffmpeg_missing") from exc
        except subprocess.CalledProcessError as exc:
            raise AppError(
                f"FFmpeg failed: {exc.stderr.decode(errors='ignore')[:500]}",
                code="ffmpeg_error",
            ) from exc
        log.debug("video_watermarked", dst=dst_path)

    def _ffmpeg_overlay_expr(self) -> str:
        mx, my = self.profile.margin_x, self.profile.margin_y
        mapping = {
            "top-left": f"{mx}:{my}",
            "top-right": f"main_w-overlay_w-{mx}:{my}",
            "bottom-left": f"{mx}:main_h-overlay_h-{my}",
            "bottom-right": f"main_w-overlay_w-{mx}:main_h-overlay_h-{my}",
            "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
        }
        return mapping.get(self.profile.position, mapping["bottom-right"])

    def _ffmpeg_text_pos(self) -> str:
        mx, my = self.profile.margin_x, self.profile.margin_y
        mapping = {
            "top-left": f"x={mx}:y={my}",
            "top-right": f"x=w-tw-{mx}:y={my}",
            "bottom-left": f"x={mx}:y=h-th-{my}",
            "bottom-right": f"x=w-tw-{mx}:y=h-th-{my}",
            "center": "x=(w-tw)/2:y=(h-th)/2",
        }
        return mapping.get(self.profile.position, mapping["bottom-right"])
