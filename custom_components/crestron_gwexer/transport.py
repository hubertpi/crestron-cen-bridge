"""Transparent TCP relay. Capture does not control forwarding or emit packets."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic

from .decoder import decode_cip_updates
from .cove import COVE_ON, COVE_OFF, cove_feedback


def now():
    return datetime.now(timezone.utc).isoformat()


class Capture:
    """Bounded raw reads plus candidate CIP frames; TCP reads are not frames."""

    def __init__(self, max_bytes=2_000_000, max_events=4000, duration=300):
        self.max_bytes, self.max_events, self.duration = max_bytes, max_events, duration
        self.active = False
        self.data = {"status": "not_started", "events": []}

    def start(self):
        self.deadline = monotonic() + self.duration
        self.active = True
        self.data = {"status": "recording", "started_at": now(), "bytes": 0,
                     "events": [], "max_bytes": self.max_bytes,
                     "max_events": self.max_events, "duration_seconds": self.duration}

    def stop(self, reason="stopped_by_user"):
        if self.active:
            self.active = False
            self.data.update(status=reason, stopped_at=now())

    def record(self, direction, session, data, frames):
        if not self.active:
            return
        if monotonic() >= self.deadline:
            self.stop("time_limit")
            return
        if self.data["bytes"] + len(data) > self.max_bytes:
            self.stop("byte_limit")
            return
        self.data["bytes"] += len(data)
        self.data["events"].append({
            "at": now(), "sequence": len(self.data["events"]) + 1,
            "direction": direction, "session": session, "raw_chunk_hex": data.hex(),
            "candidate_frames": [
                {"frame_hex": f.hex(), "decoded_joins": decode_cip_updates(f)} for f in frames
            ],
        })
        if len(self.data["events"]) >= self.max_events:
            self.stop("event_limit")

    def snapshot(self):
        if self.active and monotonic() >= self.deadline:
            self.stop("time_limit")
        return deepcopy(self.data)


class CandidateFrames:
    """Try legacy type/u16-length framing, never discard raw capture bytes.

    No scanning for join-like bytes inside unknown/encrypted traffic. If this
    framing hypothesis is wrong, only candidate decoding is affected.
    """

    def __init__(self):
        self.pending = bytearray()

    def feed(self, data):
        self.pending.extend(data)
        frames = []
        while len(self.pending) >= 3:
            size = 3 + int.from_bytes(self.pending[1:3], "big")
            if len(self.pending) < size:
                break
            frames.append(bytes(self.pending[:size]))
            del self.pending[:size]
        return frames


class GatewayRelay:
    def __init__(self, host, port, listen_host, listen_port, gateway_host, notify=lambda: None):
        self.host, self.port = host, port
        self.listen_host, self.listen_port = listen_host, listen_port
        self.gateway_host = gateway_host
        self.notify = notify
        self.capture = Capture()
        self.server = None
        self.tasks = set()
        self.busy = False
        self.stopping = False
        self.connected = False
        self.cove_is_on = None
        self.cove_feedback_at = None
        self._gateway_writer = None
        self._gateway_write_lock = asyncio.Lock()
        self._frame_boundary = asyncio.Event()
        self.sessions = 0
        self.rejected = 0
        self.last_error = None
        self.last_activity = None
        self.received_bytes = {"gateway_to_av3": 0, "av3_to_gateway": 0}

    async def start(self):
        self.server = await asyncio.start_server(self._accept, self.listen_host, self.listen_port)

    async def stop(self):
        self.stopping = True
        if self.server:
            self.server.close()
        for task in tuple(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.server:
            await self.server.wait_closed()
        self.capture.stop("integration_unloaded")

    async def _accept(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        upstream = None
        pumps = []
        accepted = False
        try:
            peer = writer.get_extra_info("peername")
            if self.stopping or self.busy or not peer or peer[0] != self.gateway_host:
                self.rejected += 1
                self.notify()
                return
            self.busy = accepted = True
            remote, upstream = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 10)
            self.sessions += 1
            self.connected = True
            self._gateway_writer = writer
            self._frame_boundary.clear()
            self.cove_is_on = None
            self.cove_feedback_at = None
            self.last_error = None
            self.notify()
            pumps = [asyncio.create_task(self._pump(reader, upstream, "gateway_to_av3")),
                     asyncio.create_task(self._pump(remote, writer, "av3_to_gateway"))]
            done, _ = await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                completed.result()
        except (OSError, asyncio.TimeoutError) as err:
            self.last_error = type(err).__name__
        finally:
            for pump in pumps:
                pump.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            for stream in (writer, upstream):
                if stream:
                    stream.close()
            await asyncio.gather(*(s.wait_closed() for s in (writer, upstream) if s), return_exceptions=True)
            if accepted:
                self.connected = self.busy = False
                self._gateway_writer = None
                self._frame_boundary.clear()
                self.cove_is_on = None
                self.cove_feedback_at = None
            self.tasks.discard(task)
            self.notify()

    async def _pump(self, reader, writer, direction):
        parser = CandidateFrames()
        while data := await reader.read(8192):
            self.received_bytes[direction] += len(data)
            self.last_activity = now()
            # Serialize downstream writes so replay never splits a relayed frame.
            if direction == "av3_to_gateway":
                async with self._gateway_write_lock:
                    writer.write(data)
                    await writer.drain()
                    frames = parser.feed(data)
                    if parser.pending:
                        self._frame_boundary.clear()
                    else:
                        self._frame_boundary.set()
            else:
                writer.write(data)
                await writer.drain()
                frames = parser.feed(data)
            try:
                if direction == "gateway_to_av3":
                    for frame in frames:
                        value = cove_feedback(frame)
                        if value is not None:
                            changed = self.cove_is_on != value
                            self.cove_is_on = value
                            self.cove_feedback_at = now()
                            if changed:
                                self.notify()
                self.capture.record(direction, self.sessions, data, frames)
            except Exception:
                # Observation must never terminate an otherwise healthy relay.
                self.last_error = "capture_decode_error"

    async def set_cove(self, on):
        """Replay only the two captured commands, to the current gateway socket."""
        writer = self._gateway_writer
        session = self.sessions
        if not self.connected or writer is None or writer.is_closing():
            raise RuntimeError("Gateway is disconnected")
        frame = COVE_ON if on else COVE_OFF
        async with asyncio.timeout(3):
            while True:
                await self._frame_boundary.wait()
                async with self._gateway_write_lock:
                    if (writer is not self._gateway_writer or session != self.sessions
                            or not self.connected or writer.is_closing()):
                        raise RuntimeError("Gateway session changed; command was not replayed")
                    if not self._frame_boundary.is_set():
                        continue
                    writer.write(frame)
                    await writer.drain()
                    self.capture.record("ha_to_gateway", session, frame, [frame])
                    return

    def snapshot(self):
        return {"connected": self.connected, "sessions": self.sessions,
                "rejected_connections": self.rejected, "last_error": self.last_error,
                "last_activity": self.last_activity, "received_bytes": dict(self.received_bytes),
                "cove": {"is_on": self.cove_is_on, "feedback_at": self.cove_feedback_at},
                "capture": self.capture.snapshot()}
