"""Real local TCP framing and lossless SNBT boundaries, isolated from game worlds."""
from contextlib import contextmanager
import socket
import struct
import threading
import time
import unittest

from mc_director.rcon import MinecraftRcon, RconError
from mc_director import snbt


def packet(request_id, body, kind=0):
    data = struct.pack('<ii', request_id, kind) + body + b'\0\0'
    return struct.pack('<i', len(data)) + data


def receive(sock):
    def exact(count):
        result = bytearray()
        while len(result) < count:
            chunk = sock.recv(count - len(result))
            if not chunk:
                raise EOFError
            result.extend(chunk)
        return bytes(result)
    size = struct.unpack('<i', exact(4))[0]
    body = exact(size)
    return struct.unpack('<ii', body[:8]), body[8:-2]


@contextmanager
def endpoint(handler):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    stopped = threading.Event()
    errors = []
    def serve():
        try:
            with listener.accept()[0] as sock:
                sock.settimeout(2)
                (identity, kind), _ = receive(sock)
                sock.sendall(packet(identity, b'', 2))
                (identity, _), command = receive(sock)
                handler(sock, identity, command, stopped)
        except (EOFError, BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            errors.append(error)
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield listener.getsockname()[1]
    finally:
        stopped.set()
        listener.close()
        worker.join(3)
        if worker.is_alive():
            raise RuntimeError('TCP fixture did not terminate')
        if errors:
            raise errors[0]


class RconTests(unittest.TestCase):
    def test_vanilla_single_frame_reader_never_receives_pipelined_barrier(self):
        def respond(sock, identity, command, stopped):
            sock.settimeout(0.1)
            try:
                receive(sock)
            except TimeoutError:
                pass
            else:
                return  # Vanilla closes when two request frames arrive together.
            sock.settimeout(2)
            sock.sendall(packet(identity, b'first response'))
            (barrier, _), _ = receive(sock)
            sock.sendall(packet(barrier, b'0 players'))
        with endpoint(respond) as port, MinecraftRcon('127.0.0.1', port, 'fixture-secret') as client:
            self.assertEqual(client.command('observe'), 'first response')

    def test_multipart_utf8_and_fragmented_frames_are_lossless(self):
        body = '{name:"community 😀",count:6}'.encode()
        split = body.index('😀'.encode()) + 2
        def respond(sock, identity, command, stopped):
            response = packet(identity, body[:split]) + packet(identity, body[split:])
            for start in range(0, len(response), 3):
                sock.sendall(response[start:start+3])
            (barrier, _), _ = receive(sock)
            response = packet(barrier, b'0 players')
            for start in range(0, len(response), 3):
                sock.sendall(response[start:start+3])
        with endpoint(respond) as port, MinecraftRcon('127.0.0.1', port, 'fixture-secret') as client:
            self.assertEqual(snbt.loads(client.command('observe')), {'name': 'community 😀', 'count': 6})

    def test_unknown_response_closes_without_replaying_consumption(self):
        inventory = {'remaining': 6}
        def respond(sock, identity, command, stopped):
            inventory['remaining'] -= 6
            sock.sendall(packet(identity + 100, b'consumed'))
            stopped.wait(1)
        with endpoint(respond) as port, MinecraftRcon('127.0.0.1', port, 'fixture-secret') as client:
            with self.assertRaises(RconError):
                client.command('consume')
            self.assertIsNone(client.sock)
            with self.assertRaises(RconError):
                client.command('consume')
            self.assertEqual(inventory['remaining'], 0)

    def test_slow_response_obeys_whole_command_deadline(self):
        inventory = {'remaining': 6}
        def respond(sock, identity, command, stopped):
            inventory['remaining'] -= 6
            for byte in packet(identity, b'consumed:6'):
                if stopped.wait(0.05):
                    return
                sock.sendall(bytes([byte]))
        with endpoint(respond) as port, MinecraftRcon('127.0.0.1', port, 'fixture-secret', timeout=0.3) as client:
            started = time.monotonic()
            with self.assertRaises(RconError):
                client.command('consume')
            self.assertLess(time.monotonic() - started, 0.9)
            self.assertIsNone(client.sock)
            self.assertEqual(inventory['remaining'], 0)


class SnbtTests(unittest.TestCase):
    def test_typed_inventory_and_unicode_round_trip(self):
        source = '{Items:[{Slot:1b,count:3,id:"minecraft:iron_ingot",components:{"minecraft:custom_data":{uuid:[I;-1,0,2147483647,-2147483648],flag:1b,long:9L,text:"a \\\"quote\\\" 😀"}}}],bytes:[B;-128b,127b],longs:[L;-9223372036854775808L,9223372036854775807L]}'
        value = snbt.loads(source)
        self.assertIsInstance(value['Items'][0]['Slot'], snbt.Byte)
        self.assertIsInstance(value['Items'][0]['components']['minecraft:custom_data']['uuid'], snbt.IntArray)
        self.assertEqual(snbt.loads(snbt.dumps(value)), value)

    def test_corrupt_or_ambiguous_evidence_is_rejected(self):
        for source in ('{count:3,count:4}', '[I;1b]', '2147483648', '128b', '1e999f', '{unterminated:"x}', '{deep:'*70+'0'+'}'*70):
            with self.subTest(source=source), self.assertRaises(snbt.SnbtError):
                snbt.loads(source)


if __name__ == '__main__':
    unittest.main()
