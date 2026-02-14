"""
Views for Analytics app — re-export shim.

All views live in sub-modules; this file re-exports them so existing
urls.py and urls_research.py imports continue to work unchanged.
"""

from .views_admin import *  # noqa: F401, F403
from .views_fast import *  # noqa: F401, F403
from .views_pub import *  # noqa: F401, F403
