"""Own one inference process; release it when the loader exits or closes its pipe."""
import os, signal, subprocess, sys, threading, time

def main():
    stop = threading.Event()
    threading.Thread(target=lambda: (os.read(sys.stdin.fileno(),1), stop.set()), daemon=True).start()
    if os.name != 'nt':
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
    p = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                         start_new_session=os.name != 'nt')
    try:
        while p.poll() is None and not stop.wait(.2):
            pass
    finally:
        if p.poll() is None:
            if os.name == 'nt': p.terminate()
            else: os.killpg(p.pid, signal.SIGTERM)
            try: p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if os.name == 'nt': p.kill()
                else: os.killpg(p.pid, signal.SIGKILL)
                p.wait(timeout=8)
    return p.returncode if not stop.is_set() else 0

if __name__ == '__main__':
    sys.exit(main())
