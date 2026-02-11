"""
WebSocket consumers for real-time pipeline progress updates.

Consumer: PipelineProgressConsumer
- Connects to a channel group named 'research_{run_id}'
- Receives progress events from ResearchOrchestrator
- Broadcasts updates to connected clients

Events emitted:
- pipeline_start: Pipeline has started
- step_start: A step is starting
- step_complete: A step has finished (with status, duration, stdout)
- pipeline_complete: Pipeline has finished (success or failed)
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class PipelineProgressConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time pipeline progress.

    Clients connect to: ws://host/ws/research/run/<run_id>/
    They receive JSON messages with progress updates.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        # Reject unauthenticated connections — AuthMiddlewareStack populates scope['user']
        # but does NOT enforce auth — we must check explicitly.
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        self.run_id = self.scope["url_route"]["kwargs"]["run_id"]
        self.group_name = f"research_{self.run_id}"

        # Join the channel group for this run
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()
        logger.info(f"WebSocket connected: run_id={self.run_id}")

        # Send initial connection confirmation
        await self.send(
            text_data=json.dumps(
                {
                    "event": "connected",
                    "run_id": self.run_id,
                    "message": "Connected to pipeline progress stream",
                }
            )
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave the channel group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: run_id={self.run_id}, code={close_code}")

    async def receive(self, text_data):
        """
        Handle incoming messages from the client.

        Currently unused - clients only receive updates.
        Could be extended for ping/pong or cancellation requests.
        """
        try:
            data = json.loads(text_data)
            # Handle ping messages
            if data.get("type") == "ping":
                await self.send(
                    text_data=json.dumps(
                        {
                            "event": "pong",
                            "run_id": self.run_id,
                        }
                    )
                )
        except json.JSONDecodeError:
            pass

    # ─────────────────────────────────────────────────────────────
    # Channel layer message handlers
    # These are called when messages are sent to the group
    # ─────────────────────────────────────────────────────────────

    async def progress_update(self, event):
        """
        Handle progress update messages from the orchestrator.

        Expected event structure:
        {
            'type': 'progress.update',
            'data': {
                'event': 'step_start' | 'step_complete' | 'pipeline_start' | 'pipeline_complete',
                'timestamp': '2024-01-19T12:00:00Z',
                ... other fields depending on event type
            }
        }
        """
        # Send the data to the WebSocket client
        await self.send(text_data=json.dumps(event["data"]))
