"""
WebSocket URL routing for Django Channels.

Routes:
- /ws/research/run/<run_id>/ - Real-time pipeline progress updates
"""

from django.urls import re_path
from analytics.consumers import PipelineProgressConsumer

websocket_urlpatterns = [
    re_path(
        r'ws/research/run/(?P<run_id>[0-9a-f-]+)/$',
        PipelineProgressConsumer.as_asgi()
    ),
]
