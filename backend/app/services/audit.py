"""审计日志:JSON Lines 格式,记录关键管理操作。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings


def _log_dir() -> Path:
    s = get_settings()
    root = Path(s.storage_path).parent
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def write(
    action: str,
    *,
    actor: str = "single-admin",
    resource: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """追加一条审计记录。失败不影响主流程。"""
    try:
        entry = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "resource": resource,
            "payload": payload or {},
        }
        path = _log_dir() / "audit.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + os.linesep)
    except Exception:
        # 审计失败不抛错
        pass


__all__ = ["write"]