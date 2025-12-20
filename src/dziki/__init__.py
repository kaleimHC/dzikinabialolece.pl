"""
Dziki na Białołęce - Django Project

This module ensures Celery app is loaded when Django starts.
"""

# Import Celery app so it's available when Django starts
from .celery import app as celery_app

__all__ = ("celery_app",)
