"""Browser test for Phonon Studio: load the page, generate speech, prove audio came out.

Chromium is driven over CDP directly (no Playwright dependency). The app is exercised the way
a user would: type text, pick a voice, click Generate, then wait for the player to have a blob.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

CHROME = '/opt/data/.pw-browsers/chromium-1243/chrome-linux64/chrome'
PORT = 9223
URL = 'http://127.0.0.1:5192/phonon-studio/'

# Chromium needs the browser library bundle (libcups and friends) that Playwright ships.
LIBPATH = (
    '/opt/data/.browserlibs/root/usr/lib/x86_64-linux-gnu:'
    '/opt/data/.libs/root/usr/lib/x86_64-linux-gnu:'
    '/opt/data/xvfb-libs/usr/lib/x86_64-linux-gnu:'
    '/opt/data/pwlibs/usr/lib/x86_64-linux-gnu:'
    '/opt/data/scratch/pw-libs/root/usr/lib/x86_64-linux-gnu:'
    '/usr/lib/x86_64-linux-gnu'
)


def cdp(ws_url, method, params=None, timeout=180):
    """Minimal CDP call over a websocket."""
    import websocket  # from the gateway venv; fall back to raw socket if absent
    return None


def main():
    # Use the gateway venv's python so `websocket-client` is available if installed there.
    import base64
    import hashlib
    import socket
    import struct

    # launch chromium with a remote debugging port
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = LIBPATH
    proc = subprocess.Popen(
        [CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
         '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
         '--disable-features=DBus',
         '--autoplay-policy=no-user-gesture-required',
         '--user-data-dir=/tmp/chrome-phonon-test', 'about:blank'],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # wait for the debugger
        for _ in range(60):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=2) as r:
                    json.load(r)
                break
            except Exception:
                time.sleep(0.5)

        # /json/new requires PUT in current Chrome
        req = urllib.request.Request(
            f'http://127.0.0.1:{PORT}/json/new?{URL}', method='PUT')
        with urllib.request.urlopen(req, timeout=15) as r:
            tab = json.load(r)
        ws = tab['webSocketDebuggerUrl']

        # ── tiny websocket client (no external deps) ───────────────────────
        from urllib.parse import urlparse
        u = urlparse(ws)
        sock = socket.create_connection((u.hostname, u.port or 80), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((
            f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
        ).encode())
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

        def recv_frame():
            def readn(n):
                out = b''
                while len(out) < n:
                    c = sock.recv(n - len(out))
                    if not c:
                        raise IOError('socket closed')
                    out += c
                return out
            h = readn(2)
            ln = h[1] & 0x7F
            if ln == 126:
                ln = struct.unpack('>H', readn(2))[0]
            elif ln == 127:
                ln = struct.unpack('>Q', readn(8))[0]
            return readn(ln)

        msg_id = [0]
        def call(method, params=None, timeout=240):
            msg_id[0] += 1
            mid = msg_id[0]
            send({'id': mid, 'method': method, 'params': params or {}})
            t0 = time.time()
            while time.time() - t0 < timeout:
                frame = json.loads(recv_frame())
                if frame.get('id') == mid:
                    return frame
            raise TimeoutError(method)

        call('Runtime.enable')
        call('Log.enable')
        call('Page.enable')

        def ev(expr, await_promise=False, timeout=240):
            r = call('Runtime.evaluate', {
                'expression': expr, 'awaitPromise': await_promise,
                'returnByValue': True, 'timeout': timeout * 1000,
            }, timeout=timeout + 10)
            return r.get('result', {}).get('result', {}).get('value')

        time.sleep(4)  # let the app boot and the first-run dialog appear

        print('page title:', ev('document.title'))
        print('voices in select:', ev("document.querySelectorAll('#voice option').length"))

        # dismiss the first-run dialog and start the download
        ev("(()=>{const d=document.getElementById('firstRun'); if(d&&d.open){document.getElementById('dlgOk').click(); return 'clicked';} return 'already open';})()")
        print('warm-up: open')

        # wait for the model to load (status flips to Ready / Generate enabled)
        ok = False
        for i in range(120):
            st = ev("document.getElementById('status').textContent")
            dis = ev("document.getElementById('go').disabled")
            if i % 10 == 0:
                print(f'  [{i*2}s] status={st!r} disabled={dis}')
            if dis is False and st and st.startswith('Ready'):
                ok = True
                break
            time.sleep(2)
        if not ok:
            print('MODEL DID NOT LOAD; last status:', ev("document.getElementById('status').textContent"))
            return 1
        print('model ready:', ev("document.getElementById('status').textContent"))

        # type the text and generate
        ev("""(()=>{
            const t=document.getElementById('text');
            t.value='Phonon Studio is working. This audio was generated entirely inside your browser, with no server involved.';
            t.dispatchEvent(new Event('input'));
            return t.value.length;
        })()""")
        ev("document.getElementById('go').click()")
        print('generate clicked')

        got = False
        for i in range(120):
            shown = ev("getComputedStyle(document.getElementById('player')).display")
            st = ev("document.getElementById('status').textContent")
            if i % 10 == 0:
                print(f'  [{i*2}s] player={shown} status={st!r}')
            if shown == 'block':
                got = True
                break
            time.sleep(2)

        if not got:
            print('NO AUDIO. status:', ev("document.getElementById('status').textContent"))
            return 1

        dur = ev("document.getElementById('player').duration")
        meta = ev("document.getElementById('meta').textContent")
        print('AUDIO OK — duration:', dur, '| meta:', meta)
        print('RESULT: PASS')
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == '__main__':
    sys.exit(main())
