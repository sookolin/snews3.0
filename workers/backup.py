"""Backup and restore utilities for database and media."""

from __future__ import annotations

import os
import subprocess
import tarfile
from datetime import datetime, timezone

from shared.config import settings
from shared.logging import get_logger

log = get_logger("backup")


async def create_backup() -> dict:
    """Create a compressed backup of the database and media directory.

    Returns a dict with the created archive path and size.
    """
    os.makedirs(settings.backup_root, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_path = os.path.join(settings.backup_root, f"db_{ts}.sql")
    archive_path = os.path.join(settings.backup_root, f"backup_{ts}.tar.gz")

    # 1) pg_dump
    env = {**os.environ, "PGPASSWORD": settings.postgres_password}
    dump_cmd = [
        "pg_dump",
        "-h",
        settings.postgres_host,
        "-p",
        str(settings.postgres_port),
        "-U",
        settings.postgres_user,
        "-d",
        settings.postgres_db,
        "-f",
        dump_path,
        "--no-owner",
        "--clean",
        "--if-exists",
    ]
    try:
        subprocess.run(dump_cmd, check=True, env=env, capture_output=True, timeout=1800)
    except FileNotFoundError:
        log.error("pg_dump_not_found")
        return {"success": False, "error": "pg_dump not found"}
    except subprocess.CalledProcessError as exc:
        log.error("pg_dump_failed", error=exc.stderr.decode(errors="ignore")[:500])
        return {"success": False, "error": "pg_dump failed"}

    # 2) tar db dump + media
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(dump_path, arcname=os.path.basename(dump_path))
        if os.path.isdir(settings.media_root):
            tar.add(settings.media_root, arcname="media")

    os.remove(dump_path)
    size = os.path.getsize(archive_path)
    log.info("backup_created", path=archive_path, size=size)
    return {"success": True, "path": archive_path, "size": size}


async def restore_backup(archive_path: str) -> dict:
    """Restore the database and media from a backup archive."""
    if not os.path.exists(archive_path):
        return {"success": False, "error": "archive not found"}

    extract_dir = os.path.join(settings.backup_root, "restore_tmp")
    os.makedirs(extract_dir, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(extract_dir)  # noqa: S202 - trusted, admin-provided archive

    sql_files = [f for f in os.listdir(extract_dir) if f.endswith(".sql")]
    if not sql_files:
        return {"success": False, "error": "no sql dump in archive"}

    dump_path = os.path.join(extract_dir, sql_files[0])
    env = {**os.environ, "PGPASSWORD": settings.postgres_password}
    restore_cmd = [
        "psql",
        "-h",
        settings.postgres_host,
        "-p",
        str(settings.postgres_port),
        "-U",
        settings.postgres_user,
        "-d",
        settings.postgres_db,
        "-f",
        dump_path,
    ]
    try:
        subprocess.run(restore_cmd, check=True, env=env, capture_output=True, timeout=1800)
    except subprocess.CalledProcessError as exc:
        log.error("restore_failed", error=exc.stderr.decode(errors="ignore")[:500])
        return {"success": False, "error": "psql restore failed"}

    log.info("backup_restored", path=archive_path)
    return {"success": True}
