"""
WSGI config for Dziki na Białołęce project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dziki.settings")

application = get_wsgi_application()
