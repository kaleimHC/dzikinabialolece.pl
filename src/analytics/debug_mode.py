# DEBUG MODE - Infrastructure for comprehensive debugging
# KONIEC PING-PONGA! Każdy krok logowany automatycznie.

import json
import time
import uuid
from functools import wraps
from typing import Any, Dict, Optional, List
from django.db import connection

# Global flag - set to False to disable all debug output
DEBUG_MODE = True

# DebugLogger - Main class for step-by-step logging


class DebugLogger:
    """
    Logger that tracks every step of computation with values.

    Usage:
        debug = DebugLogger('run-123', 'FAST', 'RF')

        t = debug.start('load_data', 'Loading grid cells')
        cells = GridCell.objects.all()
        debug.success('load_data', 'Loaded cells', values={'count': len(cells)}, start_time=t)

        debug.inspect('sighting_count', [c.sighting_count for c in cells])

        debug.summary()
    """

    ICONS = {
        "START": "\U0001f7e1",  # 🟡
        "SUCCESS": "\u2705",  # ✅
        "ERROR": "\u274c",  # ❌
        "WARNING": "\u26a0\ufe0f",  # ⚠️
        "INFO": "\u2139\ufe0f",  # ℹ️
    }

    def __init__(
        self, run_id: str = None, mode: str = "UNKNOWN", module: str = "UNKNOWN"
    ):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.mode = mode.upper()
        self.module = module.upper()
        self.steps: List[Dict] = []
        self.start_time = time.time()
        self._step_times: Dict[str, float] = {}

    def _format_prefix(self) -> str:
        return f"[{self.mode}:{self.module}]"

    def _log(
        self,
        step: str,
        status: str,
        message: str = "",
        values: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
    ):
        """Internal logging method - prints and saves to DB"""

        if not DEBUG_MODE:
            return

        icon = self.ICONS.get(status, "\u2139\ufe0f")
        prefix = self._format_prefix()

        # Console output
        print(f"[DEBUG] {icon} {prefix} {step} | {status} | {message}")
        if values:
            values_str = json.dumps(values, default=str, ensure_ascii=False)
            if len(values_str) > 200:
                values_str = values_str[:200] + "..."
            print(f"        \u2514\u2500 Values: {values_str}")
        if duration_ms:
            print(f"        \u2514\u2500 Duration: {duration_ms}ms")

        # Save to database
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO analytics_debug_log
                    (run_id, mode, module, step, status, message, values_json, duration_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    [
                        self.run_id,
                        self.mode,
                        self.module,
                        step,
                        status,
                        message,
                        json.dumps(values, default=str) if values else None,
                        duration_ms,
                    ],
                )
        except Exception as e:
            print(f"        \u2514\u2500 DB Error: {e}")

        # Track step
        self.steps.append(
            {
                "step": step,
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
            }
        )

    # Public API

    def start(self, step: str, message: str = "") -> float:
        self._step_times[step] = time.time()
        self._log(step, "START", message)
        return self._step_times[step]

    def success(
        self,
        step: str,
        message: str = "",
        values: Optional[Dict] = None,
        start_time: Optional[float] = None,
    ):
        duration = None
        if start_time:
            duration = int((time.time() - start_time) * 1000)
        elif step in self._step_times:
            duration = int((time.time() - self._step_times[step]) * 1000)
        self._log(step, "SUCCESS", message, values, duration)

    def error(
        self,
        step: str,
        message: str,
        values: Optional[Dict] = None,
        start_time: Optional[float] = None,
    ):
        duration = None
        if start_time:
            duration = int((time.time() - start_time) * 1000)
        elif step in self._step_times:
            duration = int((time.time() - self._step_times[step]) * 1000)
        self._log(step, "ERROR", message, values, duration)

    def warning(self, step: str, message: str, values: Optional[Dict] = None):
        self._log(step, "WARNING", message, values)

    def info(self, step: str, message: str, values: Optional[Dict] = None):
        self._log(step, "INFO", message, values)

    # Data Inspection Helpers

    def inspect(self, name: str, data: Any, sample_size: int = 5):
        """Inspect data distribution - arrays, lists, querysets"""
        if hasattr(data, "__len__"):
            count = len(data)
        else:
            count = "N/A"

        stats = {"count": count}

        # For numeric data
        try:
            if hasattr(data, "__iter__"):
                numeric_data = [
                    x for x in data if x is not None and isinstance(x, (int, float))
                ]
                if numeric_data:
                    stats["min"] = min(numeric_data)
                    stats["max"] = max(numeric_data)
                    stats["avg"] = sum(numeric_data) / len(numeric_data)
                    stats["zeros"] = sum(1 for x in numeric_data if x == 0)
                    stats["sample"] = numeric_data[:sample_size]
        except Exception:
            pass

        self._log(f"inspect_{name}", "INFO", f"Data inspection: {name}", stats)

    def inspect_df(self, name: str, df):
        """Inspect pandas/geopandas DataFrame"""
        try:
            stats = {
                "shape": list(df.shape),
                "columns": list(df.columns)[:10],
                "null_counts": {
                    col: int(df[col].isna().sum()) for col in df.columns[:5]
                },
            }
            # Numeric summary
            numeric_cols = df.select_dtypes(include=["number"]).columns[:5]
            for col in numeric_cols:
                stats[f"{col}_range"] = [float(df[col].min()), float(df[col].max())]

            self._log(f"inspect_{name}", "INFO", f"DataFrame inspection: {name}", stats)
        except Exception as e:
            self._log(f"inspect_{name}", "ERROR", f"Failed to inspect: {e}")

    def inspect_queryset(self, name: str, queryset, fields: List[str] = None):
        """Inspect Django QuerySet"""
        try:
            count = queryset.count()
            stats = {"count": count}

            if fields and count > 0:
                for field in fields[:5]:
                    vals = list(queryset.values_list(field, flat=True)[:100])
                    numeric = [
                        v for v in vals if isinstance(v, (int, float)) and v is not None
                    ]
                    if numeric:
                        stats[f"{field}_min"] = min(numeric)
                        stats[f"{field}_max"] = max(numeric)
                        stats[f"{field}_distinct"] = len(set(numeric))

            self._log(f"inspect_{name}", "INFO", f"QuerySet inspection: {name}", stats)
        except Exception as e:
            self._log(f"inspect_{name}", "ERROR", f"Failed to inspect: {e}")

    # Summary

    def summary(self) -> Dict:
        if not DEBUG_MODE:
            return {}

        total_duration = int((time.time() - self.start_time) * 1000)

        success_count = sum(1 for s in self.steps if s["status"] == "SUCCESS")
        error_count = sum(1 for s in self.steps if s["status"] == "ERROR")
        warning_count = sum(1 for s in self.steps if s["status"] == "WARNING")

        print()
        print("=" * 70)
        print(f"[DEBUG] {self.mode}:{self.module} SUMMARY | run_id={self.run_id}")
        print("=" * 70)
        print(f"  Total steps: {len(self.steps)}")
        print(f"  \u2705 Success: {success_count}")
        print(f"  \u274c Errors: {error_count}")
        print(f"  \u26a0\ufe0f Warnings: {warning_count}")
        print(f"  Duration: {total_duration}ms")
        print()

        if error_count > 0:
            print("  ERRORS:")
            for s in self.steps:
                if s["status"] == "ERROR":
                    print(f"    - {s['step']}: {s['message']}")
            print()

        final_status = (
            "\U0001f389 COMPLETED SUCCESSFULLY!"
            if error_count == 0
            else "\u274c FAILED!"
        )
        print(f"  {final_status}")
        print("=" * 70)
        print()

        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "module": self.module,
            "steps": len(self.steps),
            "success": success_count,
            "errors": error_count,
            "warnings": warning_count,
            "duration_ms": total_duration,
        }


# Decorator for Celery tasks


def debug_task(mode: str, module: str):
    """
    Decorator that wraps a Celery task with debug logging.

    Usage:
        @shared_task
        @debug_task('FAST', 'RF')
        def compute_rf(self, grid_type='voronoi', debug=None):
            debug.start('load_data', 'Loading cells')
            ...
            debug.success('load_data', 'Done', values={'count': 100})
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create debug logger
            run_id = kwargs.pop("run_id", None) or str(uuid.uuid4())[:12]
            debug = DebugLogger(run_id, mode, module)

            # Inject debug into kwargs
            kwargs["debug"] = debug

            try:
                debug.start("task_start", f"Starting {func.__name__}")
                result = func(*args, **kwargs)
                debug.success("task_end", f"Completed {func.__name__}")
            except Exception as e:
                debug.error("task_end", f"Failed: {str(e)}")
                debug.summary()
                raise

            debug.summary()
            return result

        return wrapper

    return decorator


# Quick debug functions for one-off use


def quick_debug(mode: str, module: str, step: str, values: Dict):
    debug = DebugLogger(str(uuid.uuid4())[:8], mode, module)
    debug.info(step, "Quick debug", values)


def get_debug_logs(
    run_id: str = None, module: str = None, status: str = None, limit: int = 100
) -> List[Dict]:
    query = "SELECT * FROM analytics_debug_log WHERE 1=1"
    params = []

    if run_id:
        query += " AND run_id = %s"
        params.append(run_id)
    if module:
        query += " AND module = %s"
        params.append(module)
    if status:
        query += " AND status = %s"
        params.append(status)

    query += " ORDER BY timestamp DESC LIMIT %s"
    params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def clear_debug_logs(older_than_hours: int = 24):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM analytics_debug_log
            WHERE timestamp < NOW() - INTERVAL '%s hours'
        """,
            [older_than_hours],
        )
        return cursor.rowcount
