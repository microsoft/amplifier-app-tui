"""Bound pending event delivery by count and serialized payload size, not journal size."""

import asyncio
import json
from dataclasses import asdict


class EventDelivery(asyncio.Queue):
    def __init__(self, maxsize=4096, max_bytes=8 * 1024 * 1024):
        super().__init__(maxsize=maxsize)
        self.max_bytes = max_bytes
        self.pending_bytes = 0

    def put_nowait(self, event):
        size = len(json.dumps(asdict(event), ensure_ascii=False, default=str).encode())
        if self.pending_bytes + size > self.max_bytes:
            raise asyncio.QueueFull
        super().put_nowait((event, size))
        self.pending_bytes += size

    def get_nowait(self):
        event, size = super().get_nowait()
        self.pending_bytes -= size
        return event
