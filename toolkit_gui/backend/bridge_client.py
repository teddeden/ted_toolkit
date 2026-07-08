'''toolkit_gui.backend.bridge_client - GUI-side TCP JSON-lines client for one
tab's tedtoolkit.gui_bridge server. See that module for the wire protocol.
'''

import json
import socket
import time

from toolkit_gui import config


class BridgeClient:
    '''One persistent connection to a single session's gui_bridge server.
    Not thread-safe - callers should serialize access per instance (e.g. one
    BridgeClient per tab, driven only by the main Qt thread's poll timer).'''

    def __init__(self, port, host='127.0.0.1'):
        self._port = port
        self._host = host
        self._sock = None
        self._next_id = 1
        self._recv_buf = b''

    def connect(self, retries=None, retry_delay=None):
        '''Block, briefly retrying, since the child process needs a moment
        after spawn before its bridge thread starts listening.'''
        retries = config.BRIDGE_CONNECT_RETRIES if retries is None else retries
        retry_delay = config.BRIDGE_CONNECT_RETRY_DELAY_SECONDS if retry_delay is None else retry_delay
        last_exc = None
        for _ in range(retries):
            try:
                self._sock = socket.create_connection((self._host, self._port), timeout=2)
                return
            except OSError as exc:
                last_exc = exc
                time.sleep(retry_delay)
        raise ConnectionError(f'Could not connect to bridge on port {self._port}') from last_exc

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def request(self, cmd, params=None, timeout=5):
        '''Send one request and block for its matching response.'''
        if self._sock is None:
            raise ConnectionError('not connected')
        req_id = self._next_id
        self._next_id += 1
        payload = json.dumps({'id': req_id, 'cmd': cmd, 'params': params or {}}) + '\n'
        self._sock.settimeout(timeout)
        self._sock.sendall(payload.encode('utf-8'))
        while b'\n' not in self._recv_buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ConnectionError('bridge connection closed')
            self._recv_buf += chunk
        line, self._recv_buf = self._recv_buf.split(b'\n', 1)
        resp = json.loads(line.decode('utf-8'))
        if resp.get('id') != req_id:
            raise ConnectionError(f'bridge response id mismatch: expected {req_id}, got {resp.get("id")}')
        return resp

    def list_vars(self):
        return self.request('list_vars')

    def get_var_preview(self, name, max_rows=None, max_cols=None):
        params = {'name': name}
        if max_rows is not None:
            params['max_rows'] = max_rows
        if max_cols is not None:
            params['max_cols'] = max_cols
        return self.request('get_var_preview', params)

    def get_title(self):
        return self.request('get_title')

    def save_session(self):
        return self.request('save_session', timeout=30)

    def restore_session(self, history, variables_pickle_b64):
        return self.request(
            'restore_session',
            {'history': history, 'variables_pickle_b64': variables_pickle_b64},
            timeout=30)
