"""Operational tests: ownership, cancellation, occupied ports and control isolation."""
import json, os, socket, subprocess, sys, tempfile, threading, time, unittest, urllib.request, urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from app import Manager, make_handler

def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def wait_for(fn,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if fn():return
        time.sleep(.1)
    raise AssertionError('Timed out')

class FakeManager(Manager):
    def command(self,p):
        time.sleep(float(p.get('device','0')))
        return [sys.executable,str(Path(__file__).resolve()),'--fake',str(self.port)]

class Lifecycle(unittest.TestCase):
    def setUp(self):
        cache=Path(__file__).resolve().parent/'state/test-temporary';cache.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=cache);self.port=free_port()
        self.m=FakeManager(Path(self.tmp.name)/'state',self.tmp.name,self.port)
        self.id=self.m.save({'name':'fixture','kind':'gguf','device':'0'})
    def tearDown(self):self.m.stop();self.tmp.cleanup()
    def test_restart_and_release(self):
        for _ in range(2):
            self.m.start(self.id);wait_for(lambda:self.m.status()['phase']=='running')
            self.m.stop();self.assertEqual(self.m.status()['phase'],'idle')
            with socket.socket() as s:self.assertNotEqual(s.connect_ex(('127.0.0.1',self.port)),0)
    def test_cancel_during_preflight(self):
        self.m.profiles[0]['device']='.8';self.m.start(self.id);self.m.stop();time.sleep(1)
        self.assertIsNone(self.m.proc);self.assertEqual(self.m.status()['phase'],'idle')
    def test_foreign_port_preserved(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1',self.port));s.listen()
            with self.assertRaises(ValueError):self.m.start(self.id)
            self.assertEqual(s.getsockname()[1],self.port)
    def test_guardian_pipe_close(self):
        p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('supervisor.py')),sys.executable,str(Path(__file__).resolve()),'--fake',str(self.port)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            def live():
                with socket.socket() as s:return s.connect_ex(('127.0.0.1',self.port))==0
            wait_for(live);p.stdin.close();p.wait(timeout=12);self.assertFalse(live())
        finally:
            if p.poll() is None:p.kill();p.wait()
    def test_control_token_and_origin(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.m,'test-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}/api/stop'
        try:
            for headers in [{},{'X-Loader-Token':'test-token','Origin':'https://evil.example'},{'X-Loader-Token':'test-token','Host':'evil.example'}]:
                req=urllib.request.Request(url,data=b'{}',headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
                self.assertEqual(err.exception.code,403)
            req=urllib.request.Request(url,data=b'{}',headers={'X-Loader-Token':'test-token'})
            with urllib.request.urlopen(req) as r:self.assertTrue(json.load(r)['ok'])
        finally:server.shutdown();server.server_close()

if __name__=='__main__':
    if '--fake' in sys.argv:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                b=b'{"status":"ok"}';self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            def log_message(self,*_):pass
        ThreadingHTTPServer(('127.0.0.1',int(sys.argv[-1])),Handler).serve_forever()
    else:unittest.main()
