"""Local raw-FIM HTTP bridge for OpenVINO GenAI. Never selects a fallback device."""
import argparse, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import openvino as ov
import openvino_genai as genai

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', default=str(Path(__file__).parent/'openvino-int4-g128'))
    p.add_argument('--device', choices=['NPU', 'GPU', 'CPU'], default='NPU')
    p.add_argument('--port', type=int, default=18031)
    p.add_argument('--check-device', action='store_true')
    a = p.parse_args()
    devices = ov.Core().available_devices
    if a.device not in devices: raise RuntimeError(f'{a.device} unavailable; detected {devices}. No fallback selected.')
    if a.check_device:
        print(json.dumps({'device': a.device, 'available': devices})); return
    cfg = {'INFERENCE_NUM_THREADS': 8} if a.device == 'CPU' else {}
    if a.device == 'NPU':
        cfg = {'MAX_PROMPT_LEN': 1536, 'MIN_RESPONSE_LEN': 128, 'GENERATE_HINT': 'FAST_COMPILE',
               'CACHE_DIR': str(Path(__file__).parent/'npu-cache')}
    pipe = genai.LLMPipeline(a.model, a.device, **cfg)
    tokenizer = pipe.get_tokenizer()
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, obj):
            body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
            self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path == '/health': self.reply(200, {'status': 'ok', 'device': a.device})
            elif self.path == '/props': self.reply(200, {'model_path': a.model, 'total_slots': 1})
            elif self.path == '/v1/models': self.reply(200, {'object': 'list', 'data': [{'id': 'cad-v1-int4', 'object': 'model'}]})
            else: self.reply(404, {'error': 'Unknown endpoint'})
        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 1048576: raise ValueError('Request body must be 1 byte to 1 MiB')
                req = json.loads(self.rfile.read(size))
                if self.path == '/tokenize':
                    with lock: tokens = tokenizer.encode(req['content'], add_special_tokens=False).input_ids.data[0].tolist()
                    self.reply(200, {'tokens': tokens}); return
                if self.path != '/completion': self.reply(404, {'error': 'Use /completion for raw FIM'}); return
                prompt = req['prompt']
                if not isinstance(prompt, str) or not prompt.startswith('<|fim_prefix|>') or not prompt.endswith('<|fim_middle|>'):
                    raise ValueError('Expected raw Qwen FIM prompt; chat templates are not supported')
                limit = min(max(int(req.get('n_predict', 128)), 1), 128)
                stops = req.get('stop', [])
                if not isinstance(stops, list) or any(not isinstance(s, str) for s in stops): raise ValueError('stop must be a string array')
                with lock:
                    count = tokenizer.encode(prompt, add_special_tokens=False).input_ids.data.shape[1]
                    if count > 1253: raise ValueError('Prompt exceeds the evaluated 1250-token context plus FIM markers')
                    cfg = {'max_new_tokens': limit, 'do_sample': False, 'apply_chat_template': False, 'repetition_penalty': 1.0}
                    if stops: cfg['stop_strings'] = set(s for s in stops if s)
                    start = time.perf_counter()
                    content = str(pipe.generate(prompt, **cfg))
                result = {'content': content, 'stop': True, 'truncated': False,
                          'timings': {'elapsed_ms': (time.perf_counter()-start)*1000}, 'device': a.device}
                if req.get('stream'):
                    # One completed SSE chunk; this bridge does not expose token-by-token streaming.
                    body = ('data: '+json.dumps(result, ensure_ascii=False)+'\n\n').encode('utf-8')
                    self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
                else: self.reply(200, result)
            except (BrokenPipeError, ConnectionResetError): pass
            except Exception as exc: self.reply(400, {'error': str(exc)})
    server = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print(json.dumps({'ready': True, 'url': f'http://127.0.0.1:{a.port}', 'device': a.device, 'available_devices': devices}), flush=True)
    try: server.serve_forever()
    finally: server.server_close()

if __name__ == '__main__': main()
