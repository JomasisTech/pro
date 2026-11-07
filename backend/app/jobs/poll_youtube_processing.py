"""Cron entry point: refresh YouTube videos that were uploaded but are still processing.

Schedule every five minutes. Exits non-zero on an unexpected infrastructure error so the
scheduler can flag the run; per-video provider errors are counted in the summary instead.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.modules.posting.youtube_worker import poll_youtube_processing

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("youtube_processing_poll")


def main() -> int:
    summary: dict = {"job": "youtube_processing_poll", "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        with SessionLocal() as db:
            summary["result"] = poll_youtube_processing(db, limit=50)
    except Exception:  # noqa: BLE001 - report any infrastructure failure to the scheduler
        log.exception("YouTube processing poll failed")
        summary["ok"] = False
        print(json.dumps(summary))
        return 1
    summary["ok"] = True
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
