import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/crestron_gwexer"
package = types.ModuleType("gwtest")
package.__path__ = [str(ROOT)]
sys.modules["gwtest"] = package
spec = importlib.util.spec_from_file_location("gwtest.transport", ROOT / "transport.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CaptureTests(unittest.TestCase):
    def test_split_and_unknown_frames(self):
        parser = module.CandidateFrames()
        self.assertEqual(parser.feed(b"\x05\x00"), [])
        self.assertEqual(parser.feed(b"\x02ab\xfe\x00\x01x"), [b"\x05\x00\x02ab", b"\xfe\x00\x01x"])

    def test_raw_and_bound(self):
        capture = module.Capture(max_bytes=3)
        capture.start()
        capture.record("gateway_to_av3", 1, b"abc", [])
        capture.record("gateway_to_av3", 1, b"d", [])
        self.assertEqual(capture.snapshot()["status"], "byte_limit")
        self.assertEqual(capture.snapshot()["events"][0]["raw_chunk_hex"], "616263")

    def test_deadline_and_event_limit(self):
        capture = module.Capture(max_events=1)
        capture.start()
        capture.record("av3_to_gateway", 1, b"x", [])
        self.assertEqual(capture.snapshot()["status"], "event_limit")
        capture.start()
        capture.deadline = 0
        self.assertEqual(capture.snapshot()["status"], "time_limit")


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.remote = asyncio.Queue()
        self.writers = []
        async def accept(reader, writer):
            self.writers.append(writer)
            await self.remote.put((reader, writer))
        self.server = await asyncio.start_server(accept, "127.0.0.1", 0)
        self.relay = module.GatewayRelay("127.0.0.1", self.server.sockets[0].getsockname()[1],
                                         "127.0.0.1", 0, "127.0.0.1")
        await self.relay.start()
        self.port = self.relay.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.relay.stop()
        for writer in self.writers:
            writer.close()
        await asyncio.gather(*(w.wait_closed() for w in self.writers), return_exceptions=True)
        self.server.close()
        await self.server.wait_closed()

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(writer)
        remote = await asyncio.wait_for(self.remote.get(), 1)
        return reader, writer, *remote

    async def test_unchanged_bidirectional_capture_and_disconnect(self):
        self.relay.capture.start()
        reader, writer, remote_reader, remote_writer = await self.connect()
        payload = bytes(range(256)) * 100
        writer.write(payload)
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(remote_reader.readexactly(len(payload)), 2), payload)
        remote_writer.write(b"reply\x00\xff")
        await remote_writer.drain()
        self.assertEqual(await asyncio.wait_for(reader.readexactly(7), 1), b"reply\x00\xff")
        remote_writer.close()
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        await self.relay.stop()
        events = self.relay.capture.snapshot()["events"]
        raw = b"".join(bytes.fromhex(e["raw_chunk_hex"]) for e in events if e["direction"] == "gateway_to_av3")
        self.assertEqual(raw, payload)
        self.assertFalse(self.relay.connected)

    async def test_extra_client_rejected_without_disturbing_session(self):
        reader, writer, remote_reader, remote_writer = await self.connect()
        extra_reader, extra_writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(extra_writer)
        self.assertEqual(await asyncio.wait_for(extra_reader.read(), 1), b"")
        writer.write(b"ok")
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(remote_reader.readexactly(2), 1), b"ok")
        self.assertEqual(self.relay.rejected, 1)

    async def test_shutdown_closes_both_sides(self):
        reader, writer, remote_reader, remote_writer = await self.connect()
        await self.relay.stop()
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        self.assertEqual(await asyncio.wait_for(remote_reader.read(), 1), b"")
        self.assertFalse(self.relay.tasks)

    async def test_source_filter(self):
        self.relay.gateway_host = "127.0.0.2"
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(writer)
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        self.assertEqual(self.relay.sessions, 0)

    async def test_cove_replay_goes_downstream_and_waits_for_feedback(self):
        reader, writer, remote_reader, remote_writer = await self.connect()
        remote_writer.write(bytes.fromhex("0e00020000"))
        await remote_writer.drain()
        await asyncio.wait_for(reader.readexactly(5), 1)
        self.relay.capture.start()
        await self.relay.set_cove(True)
        expected = bytes.fromhex("05000e00000b200308200105140000ffff")
        self.assertEqual(await asyncio.wait_for(reader.readexactly(len(expected)), 1), expected)
        self.assertIsNone(self.relay.cove_is_on)
        # A non-Cove nested signal must not become Cove state.
        other = bytes.fromhex("05000c000009200306200103001500")
        writer.write(other)
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(remote_reader.readexactly(len(other)), 1), other)
        self.assertIsNone(self.relay.cove_is_on)
        feedback = bytes.fromhex("05000c000009200306200103001400")
        writer.write(feedback[:7])
        await writer.drain()
        await remote_reader.readexactly(7)
        self.assertIsNone(self.relay.cove_is_on)
        writer.write(feedback[7:])
        await writer.drain()
        await remote_reader.readexactly(len(feedback)-7)
        self.assertTrue(self.relay.cove_is_on)
        await self.relay.set_cove(False)
        expected_off = bytes.fromhex("05000e00000b2003082001051400000000")
        self.assertEqual(await reader.readexactly(len(expected_off)), expected_off)
        self.assertTrue(self.relay.cove_is_on)
        off_feedback = bytes.fromhex("05000c000009200306200103001480")
        writer.write(off_feedback)
        await writer.drain()
        await remote_reader.readexactly(len(off_feedback))
        self.assertFalse(self.relay.cove_is_on)
        events = self.relay.capture.snapshot()["events"]
        self.assertEqual([e["raw_chunk_hex"] for e in events if e["direction"] == "ha_to_gateway"],
                         [expected.hex(), expected_off.hex()])
        await self.relay.stop()
        self.assertIsNone(self.relay.cove_is_on)
        with self.assertRaises(RuntimeError):
            await self.relay.set_cove(True)

    async def test_cove_cannot_split_relayed_frame(self):
        reader, writer, remote_reader, remote_writer = await self.connect()
        frame = bytes.fromhex("05000e00000b2003082001051400000000")
        remote_writer.write(frame[:5])
        await remote_writer.drain()
        self.assertEqual(await reader.readexactly(5), frame[:5])
        command = asyncio.create_task(self.relay.set_cove(True))
        await asyncio.sleep(0)
        self.assertFalse(command.done())
        remote_writer.write(frame[5:])
        await remote_writer.drain()
        expected = frame[5:] + bytes.fromhex("05000e00000b200308200105140000ffff")
        self.assertEqual(await asyncio.wait_for(reader.readexactly(len(expected)), 1), expected)
        await command


if __name__ == "__main__":
    unittest.main()
