"""Small, privacy-safe diagnostic log for support reports."""
from __future__ import annotations

import logging
import platform
import sys

from paths import ROOT

APP_VERSION = "0.2.1"


def create_diagnostics_logger():
    """Return the shared file logger without recording capture or game-log data."""
    logger = logging.getLogger("StarwardBGM")
    if logger.handlers:
        return logger
    (ROOT / "logs").mkdir(exist_ok=True)
    handler = logging.FileHandler(ROOT / "logs" / "StarwardBGM.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info("startup version=%s os=%s python=%s", APP_VERSION, platform.platform(), sys.version.split()[0])
    return logger
