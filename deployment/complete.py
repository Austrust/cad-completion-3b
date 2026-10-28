"""JSONL CAD completion client. Python 3.10+, standard library only."""
import argparse, ast, json, re, sys, time, urllib.request

VERSIONS = {'cadquery': 'CadQuery 2.7.0', 'build123d': 'build123d 0.13.0'}

def prepare(req):
    lib, prefix, suffix = req['library'], req['prefix'], req.get('suffix', '')
    mode = req.get('mode', 'code')
    if lib not in VERSIONS or mode not in ('api', 'code'):
        raise ValueError('library must be cadquery/build123d; mode must be api/code')
    if not isinstance(prefix, str) or not isinstance(suffix, str):
        raise ValueError('prefix/suffix must be strings')
    header = '# Library: ' + VERSIONS[lib]
    if prefix.startswith('# Library: ') and prefix.splitlines()[0] != header:
        raise ValueError('library header mismatch')
    if not prefix.startswith('# Library: '):
        prefix = header + '\n' + prefix
    prompt = '<|fim_prefix|>' + prefix + '<|fim_suffix|>' + suffix + '<|fim_middle|>'
    return prefix, suffix, mode, prompt

def finish(req, prefix, suffix, mode, raw, seconds, limited=False):
    text = raw
    if mode == 'api':
        match = re.match(r'\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)', text)
        if match: text = match.group(1)
    else:
        if text.startswith('```'): text = text.split('\n', 1)[-1].split('```', 1)[0]
        if suffix.strip() and suffix.strip() in text: text = text.split(suffix.strip(), 1)[0]
    try:
        ast.parse(prefix + text + suffix)
        syntax = True
    except SyntaxError:
        syntax = False
    return {'id': req.get('id'), 'completion': text, 'raw': raw, 'mode': mode,
            'seconds': seconds, 'syntax_ok': syntax, 'geometry_verified': False,
            'hit_token_limit': limited}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:18031')
    p.add_argument('--input', help='UTF-8 JSONL file; otherwise read stdin')
    a = p.parse_args()
    # Never send source through an inherited HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def post(path, body):
        request = urllib.request.Request(a.url.rstrip('/') + path,
            json.dumps(body, ensure_ascii=False).encode('utf-8'), {'Content-Type': 'application/json'})
        with opener.open(request, timeout=180) as response: return json.load(response)
    source = open(a.input, encoding='utf-8-sig') if a.input else sys.stdin
    try:
        for line in source:
            req = {}
            try:
                req = json.loads(line)
                if not isinstance(req, dict): raise ValueError('Each JSONL row must be an object')
                prefix, suffix, mode, prompt = prepare(req)
                count = len(post('/tokenize', {'content': prompt, 'add_special': False, 'parse_special': True})['tokens'])
                if count > 1253: raise ValueError('Context exceeds 1250 tokens plus 3 FIM markers; shorten context explicitly')
                body = {'prompt': prompt, 'n_predict': 12 if mode == 'api' else 128,
                        'temperature': 0, 'repeat_penalty': 1, 'seed': 20261028,
                        'cache_prompt': False, 'stream': False,
                        'stop': [suffix.strip()] if mode != 'api' and suffix.strip() else []}
                start = time.perf_counter()
                r = post('/completion', body)
                if r.get('truncated'): raise RuntimeError('Server truncated context')
                out = finish(req, prefix, suffix, mode, r['content'], time.perf_counter()-start, r.get('stop_type') == 'limit')
            except Exception as exc:
                out = {'id': req.get('id') if isinstance(req, dict) else None, 'error': str(exc)}
            print(json.dumps(out, ensure_ascii=False), flush=True)
    finally:
        if a.input: source.close()

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    main()
