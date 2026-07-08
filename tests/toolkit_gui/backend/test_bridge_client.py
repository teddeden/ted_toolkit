'''Tests for toolkit_gui.backend.bridge_client.BridgeClient's request/response
framing against a minimal local TCP fake server - proves the id-matching,
newline-delimited JSON protocol logic without needing a real toolkit
session/bridge on the other end.
'''

import json
import socket
import threading

import pytest

from toolkit_gui.backend.bridge_client import BridgeClient
from toolkit_gui.backend.env_resolve import find_free_port


class _FakeBridgeServer:
    '''Accepts one connection and echoes back a canned/derived response per
    request, mirroring tedtoolkit.gui_bridge's newline-delimited JSON wire
    format closely enough to exercise BridgeClient's framing logic.'''

    def __init__(self, port, responder):
        self._port = port
        self._responder = responder
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(('127.0.0.1', port))
        self._sock.listen(1)
        self._thread = threading.Thread(target=self._serve_once, daemon=True)
        self._thread.start()

    def _serve_once(self):
        conn, _addr = self._sock.accept()
        buf = b''
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                req = json.loads(line.decode('utf-8'))
                resp = self._responder(req)
                conn.sendall((json.dumps(resp) + '\n').encode('utf-8'))
        conn.close()

    def close(self):
        self._sock.close()


@pytest.fixture
def fake_server():
    port = find_free_port()
    servers = []

    def _start(responder):
        server = _FakeBridgeServer(port, responder)
        servers.append(server)
        return port

    yield _start
    for server in servers:
        server.close()


def test_request_returns_matching_response(fake_server):
    port = fake_server(lambda req: {'id': req['id'], 'ok': True, 'result': req['cmd']})
    client = BridgeClient(port)
    client.connect()
    resp = client.request('list_vars')
    assert resp == {'id': 1, 'ok': True, 'result': 'list_vars'}
    client.close()


def test_sequential_requests_get_incrementing_ids(fake_server):
    port = fake_server(lambda req: {'id': req['id'], 'ok': True, 'result': None})
    client = BridgeClient(port)
    client.connect()
    resp1 = client.request('get_title')
    resp2 = client.request('get_title')
    assert resp1['id'] == 1
    assert resp2['id'] == 2
    client.close()


def test_convenience_methods_send_expected_params(fake_server):
    captured = []

    def responder(req):
        captured.append(req)
        return {'id': req['id'], 'ok': True, 'result': None}

    port = fake_server(responder)
    client = BridgeClient(port)
    client.connect()
    client.get_var_preview('my_table', max_rows=10, max_cols=20)
    client.close()
    assert captured[0]['cmd'] == 'get_var_preview'
    assert captured[0]['params'] == {'name': 'my_table', 'max_rows': 10, 'max_cols': 20}


def test_request_without_connect_raises():
    client = BridgeClient(0)
    with pytest.raises(ConnectionError):
        client.request('list_vars')
