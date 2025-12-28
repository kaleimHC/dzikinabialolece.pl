# DEBUG MODE - Infrastructure for comprehensive debugging

import time
import uuid
from typing import Any, Dict, Optional, List

DEBUG_MODE = True


class DebugLogger:
    """Logger that tracks every step of computation with values."""

    def __init__(self, run_id: str = None, mode: str = "UNKNOWN", module: str = "UNKNOWN"):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.mode = mode.upper()
        self.module = module.upper()
        self.steps: List[Dict] = []
        self.start_time = time.time()

    def start(self, step: str, msg: str = "", values: dict = None) -> float:
        t = time.time()
        self.steps.append({"step": step, "status": "START", "msg": msg})
        return t

    def success(self, step: str, msg: str = "", values: dict = None, start_time: float = None):
        self.steps.append({"step": step, "status": "SUCCESS", "msg": msg})

    def error(self, step: str, msg: str = "", values: dict = None):
        self.steps.append({"step": step, "status": "ERROR", "msg": msg})

    def info(self, step: str, msg: str = "", values: dict = None):
        self.steps.append({"step": step, "status": "INFO", "msg": msg})

    def summary(self) -> dict:
        return {"run_id": self.run_id, "steps": len(self.steps)}
