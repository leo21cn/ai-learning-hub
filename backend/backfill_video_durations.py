"""一次性 backfill 脚本：补齐存量 VIDEO 素材的 duration_or_pages。

用法（容器内执行）:
    docker exec learning-hub_backend.1 python /app/backfill_video_durations.py [--dry-run]

逻辑:
1. 查 material 表里 type='VIDEO' AND duration_or_pages IS NULL 的所有行
2. 对每个素材读 storage_path，调 ffprobe 探测时长
3. UPDATE duration_or_pages = 'MM:SS' 或 'HH:MM:SS'
4. 输出每个素材的探测结果

要求：容器已安装 ffmpeg（后端 Dockerfile 第 38 行）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# 让脚本能从 /app/app/* 导入
sys.path.insert(0, "/app")

from sqlalchemy import select, update  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.material import Material, MaterialType  # noqa: E402


def probe_duration(path: Path) -> str | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"  ffprobe failed: {e}")
        return None

    try:
        data = json.loads(out.decode("utf-8", errors="ignore") or "{}")
        dur = data.get("format", {}).get("duration")
        if not dur:
            return None
        sec = float(dur)
        if sec <= 0 or sec != sec:
            return None
    except (ValueError, TypeError) as e:
        print(f"  parse failed: {e}")
        return None

    total = int(round(sec))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    pad = lambda n: f"{n:02d}"
    return f"{pad(h)}:{pad(m)}:{pad(s)}" if h > 0 else f"{pad(m)}:{pad(s)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印,不写库")
    args = parser.parse_args()

    with SessionLocal() as db:
        rows = db.execute(
            select(Material)
            .where(Material.type == MaterialType.VIDEO.value)
            .where(Material.duration_or_pages.is_(None))
            .order_by(Material.id)
        ).scalars().all()

        print(f"Found {len(rows)} VIDEO materials without duration.")

        ok = 0
        skipped = 0
        failed = 0
        for m in rows:
            path = Path(m.storage_path)
            if not path.exists():
                print(f"  id={m.id} {m.name!r}  FILE MISSING: {path}")
                failed += 1
                continue
            print(f"  id={m.id} {m.name!r}  size={m.size_bytes}", end=" ")
            duration = probe_duration(path)
            if not duration:
                print("→ SKIP (ffprobe returned None)")
                skipped += 1
                continue
            print(f"→ {duration}")
            if not args.dry_run:
                db.execute(
                    update(Material)
                    .where(Material.id == m.id)
                    .values(duration_or_pages=duration)
                )
            ok += 1

        if not args.dry_run:
            db.commit()
            print(f"\nCommitted. ok={ok} skipped={skipped} failed={failed}")
        else:
            print(f"\n[dry-run] ok={ok} skipped={skipped} failed={failed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())