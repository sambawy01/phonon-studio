"""Capture the browser console + page errors while loading the app without isolation headers."""
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

CHROME = '/opt/data/.pw-browsers/chromium-1243/chrome-linux64/chrome'
PORT = 9224
URL = 'http://127.0.0.1:5192/phonon-studio/'
LIBPATH = (
    '/opt/data/.browserlibs/root/usr/lib/x86_64-linux-gnu:'
    '/opt/data/.libs/root/usr/lib/x86_64-linux-gnu:'
    '/opt/data/xvfb-libs/usr/lib/x86_64-linux-gnu:'
    '/opt/data/pwlibs/usr/lib/x86_64-linux-gnu:'
    '/opt/data/scratch/pw-libs/root/usr/lib/x86_64-linux-gnu:'
    '/usr/lib/x86_64-linux-gnu'
)

env = dict(os.environ)
env['LD_LIBRARY_PATH'] = LIBPATH
proc = subprocess.Popen(
    [CHROME, '--headless=new', f'--remote-debugging-port={PORT}', '--no-sandbox',
     '--disable-gpu', '--disable-dev-shm-usage', '--disable-features=DBus',
     '--user-data-dir=/tmp/chrome-phonon-diag', 'about:blank'],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=2).read()
            break
        except Exception:
            time.sleep(0.5)

    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/json/new?{URL}', method='PUT')
    tab = json.load(urllib.request.urlopen(req, timeout=15))
    u = urlparse(tab['webSocketDebuggerUrl'])

    sock = socket.create_connection((u.hostname, u.port or 80), timeout=30)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n'
                  f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                  f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
    buf = b''
    while b'\r\n\r\n' not in buf:
        buf += sock.recv(4096)

    def send(obj):
        data = json.dumps(obj).encode()
        hdr = bytearray([0x81])
        n = len(data)
        mask = os.urandom(4)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack('>H', n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack('>Q', n)
        hdr += mask
        sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def readn(n):
        out = b''
        while len(out) < n:
            c = sock.recv(n - len(out))
            if not c:
                raise IOError('closed')
            out += c
        return out

    def recv_frame():
        h = readn(2)
        ln = h[1] & 0x7F
        if ln == 126:
            ln = struct.unpack('>H', readn(2))[0]
        elif ln == 127:
            ln = struct.unpack('>Q', readn(8))[0]
        return readn(ln)

    # enable domains, then reload the page so we catch everything from the start
    for m in ('Runtime.enable', 'Log.enable', 'Page.enable', 'Network.enable'):
        send({'id': 1, 'method': m, 'params': {}})
        time.sleep(0.15)
        while True:
            try:
                sock.settimeout(0.4)
                f = json.loads(recv_frame())
            except Exception:
                break
            sock.settimeout(30)

    send({'id': 99, 'method': 'Page.navigate', 'params': {'url': URL}})

    deadline = time.time() + 40
    sock.settimeout(2)
    while time.time() < deadline:
        try:
            f = json.loads(recv_frame())
        except Exception:
            continue
        m = f.get('method')
        if m == 'Runtime.consoleAPICalled':
            args = ' '.join(str(a.get('value', a.get('description', ''))) for a in f['params']['args'])
            print('CONSOLE', f['params']['type'], ':', args[:300])
        elif m == 'Runtime.exceptionThrown':
            d = f['params']['exceptionDetails']
            print('EXCEPTION:', d.get('text'), '|', (d.get('exception') or {}).get('description', '')[:400])
        elif m == 'Log.entryAdded':
            e = f['params']['entry']
            if e.get('level') in ('error', 'warning'):
                print('LOG', e['level'], ':', e.get('text', '')[:300])
        elif m == 'Network.loadingFailed':
            print('NET FAIL:', f['params'].get('errorText'), f['params'].get('type'))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
