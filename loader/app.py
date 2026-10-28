"""Local deployment control plane. Inference stays in existing backends."""
import argparse, atexit, json, os, re, secrets, socket, subprocess, sys, threading, time, urllib.request, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE=Path(__file__).resolve().parent
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def path(value):return Path(str(value)).expanduser().absolute()
def dump(file,value):
    tmp=file.with_name(file.name+'.'+secrets.token_hex(4)+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    # Sync clients / antivirus can briefly hold a Windows file during replacement.
    for attempt in range(10):
        try:os.replace(tmp,file);return
        except PermissionError:
            if attempt==9:raise
            time.sleep(.1*(attempt+1))

def discover(root):
    root=path(root);win=os.name=='nt';exe='llama-server.exe' if win else 'llama-server'
    runtime_candidates=[root/'runtimes/vulkan'/exe,root/'runtimes/cuda'/exe,root/'runtimes/linux-vulkan/llama-b11669'/exe,root/'runtime/llama-b11669'/exe,root/'work/q4-tools/vulkan'/exe]
    runtime_candidates += [root/'release'/p for p in ['runtimes/linux-vulkan/llama-b11669/'+exe,'runtimes/vulkan/'+exe]]
    runtimes=[p for p in runtime_candidates if p.is_file()]
    folders=[root,root/'gguf',root/'models',root/'work/q4-models',root/'releases/v1-q4/gguf',root/'cache/v1-q4-build']
    models=sorted({p.resolve() for folder in folders if folder.is_dir() for p in folder.glob('*.gguf')})
    py='Scripts/python.exe' if win else 'bin/python'
    ovpython=next((p for p in [root/'.venv-npu'/py,root/'release/.venv-npu'/py,root/'.venv-openvino'/py] if p.is_file()),Path(sys.executable))
    profiles=[]
    for model in models:
        for runtime in runtimes or [Path('missing-llama-server')]:
            device='CUDA0' if 'cuda' in str(runtime).lower() else 'Vulkan0'
            profiles.append(dict(name=model.stem+' · '+device,kind='gguf',model=str(model),runtime=str(runtime),device=device,python='',adapter='',note='GPU发行版' if 'Q4_K_M' in model.name else '自定义GGUF，成绩以对应版本为准'))
    ovfolders=[root/'openvino-int4-g128',root/'release/openvino-int4-g128',root/'models/openvino-int4-gptq',root/'work/q4-models/openvino-int4-gptq']
    seen=set()
    for folder in ovfolders:
        if (folder/'openvino_model.xml').is_file() and folder.resolve() not in seen:
            seen.add(folder.resolve());profiles.append(dict(name='v1 INT4 · Intel NPU（预览）',kind='openvino',model=str(folder.resolve()),python=str(ovpython),runtime='',device='NPU',adapter='',note='预览：短中文整句93.5%，未达到全部95%'))
    for folder in [root,root/'v1',root/'releases/v1']:
        if (folder/'models/Qwen2.5-Coder-3B/config.json').is_file() and (folder/'adapter/adapter_config.json').is_file():
            python=next((p for p in [root/'.venv-v1'/py,root/'.venv-train'/py] if p.is_file()),Path(sys.executable))
            profiles.append(dict(name='v1 原始 · NF4/BF16',kind='v1',model=str(folder),python=str(python),runtime='',device='0',adapter='',note='已保存v1，使用独立推理代码；需要NVIDIA CUDA'))
    for i,p in enumerate(profiles):p['id']='model-'+secrets.token_hex(6)
    return profiles

class Manager:
    def __init__(self,state,root,port):
        self.state=path(state);self.state.mkdir(parents=True,exist_ok=True)
        self.file=self.state/'models.json';self.port=port;self.root=str(path(root));self.lock=threading.RLock()
        self.profiles=json.loads(self.file.read_text(encoding='utf-8')) if self.file.exists() else discover(root)
        if not self.file.exists():dump(self.file,self.profiles)
        self.proc=None;self.active=None;self.phase='idle';self.error='';self.log=None;self.epoch=0
    def status(self):
        with self.lock:
            if self.proc and self.proc.poll() is not None and self.phase in ('loading','running'):
                self.phase='error';self.error='推理服务已退出，请查看日志';self.proc=None;self.active=None
            return dict(phase=self.phase,error=self.error,active=self.active,profiles=self.profiles,root=self.root,endpoint=f'http://127.0.0.1:{self.port}',log=self.log.name if self.log else '')
    def command(self,p):
        model=path(p['model']);kind=p['kind'];device=p['device']
        if kind=='gguf':
            if not model.is_file():raise ValueError('找不到GGUF模型文件')
            runtime=path(p['runtime'])
            if not runtime.is_file():raise ValueError('找不到llama-server，请使用已有发行包中的运行时')
            if device!='CPU' and not re.fullmatch(r'(Vulkan|CUDA)\d+',device):raise ValueError('设备填写Vulkan0、CUDA0或CPU')
            if device!='CPU':
                inv=subprocess.run([str(runtime),'--list-devices'],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                if device+':' not in inv.stdout+inv.stderr:raise ValueError('所选设备不可用：'+device+'\n'+inv.stdout+inv.stderr)
            return [str(runtime),'-m',str(model),'--host','127.0.0.1','--port',str(self.port),'-c','2048','--parallel','1','-b','512','-ub','512','-t','8','--flash-attn','off','--no-context-shift','--no-warmup','-ngl','0' if device=='CPU' else '99','--device','none' if device=='CPU' else device]
        python=path(p['python'])
        if not python.is_file():raise ValueError('找不到推理环境Python；请选择已安装该后端的环境')
        if kind=='openvino':
            if not (model/'openvino_model.xml').is_file() or not (model/'openvino_model.bin').is_file():raise ValueError('模型目录须包含OpenVINO XML和BIN')
            if device not in ('NPU','GPU','CPU'):raise ValueError('OpenVINO设备填写NPU、GPU或CPU')
            return [str(python),'-u',str(HERE/'openvino_server.py'),'--model',str(model),'--device',device,'--port',str(self.port)]
        if kind=='v1':
            if not (model/'models/Qwen2.5-Coder-3B/config.json').is_file():raise ValueError('请选择v1推理目录（含models和adapter）')
            if not re.fullmatch(r'\d+|GPU-[a-fA-F0-9-]+',device):raise ValueError('原始v1的设备填写CUDA编号，例如0')
            adapter=path(p['adapter']) if p.get('adapter') else model/'adapter'
            if not (adapter/'adapter_config.json').is_file():raise ValueError('找不到LoRA适配器目录')
            return [str(python),'-B','-u',str(HERE/'v1_server.py'),'--model',str(model),'--adapter',str(adapter),'--device',device,'--port',str(self.port)]
        raise ValueError('不支持的模型格式')
    def start(self,id):
        with self.lock:
            if self.phase in ('loading','running','stopping') or (self.proc and self.proc.poll() is None):raise ValueError('请先停止当前模型')
            p=next((dict(p) for p in self.profiles if p['id']==id),None)
            if not p:raise ValueError('请选择模型')
            with socket.socket() as s:
                if os.name!='nt':s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                try:s.bind(('127.0.0.1',self.port))
                except OSError:raise ValueError(f'端口{self.port}已被其他服务使用；加载器不会停止它')
            self.phase='loading';self.active=id;self.error='';self.epoch+=1;epoch=self.epoch
            self.log=self.state/(time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.log')
        threading.Thread(target=self._start,args=(p,epoch),daemon=True).start()
    def _start(self,p,epoch):
        try:
            cmd=self.command(p)
            with self.lock:
                if epoch!=self.epoch:return
                with self.log.open('w',encoding='utf-8') as log:
                    log.write(json.dumps({'model':p['name'],'backend':p['kind'],'device':p['device']},ensure_ascii=False)+'\n');log.flush()
                    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false')
                    self.proc=subprocess.Popen([sys.executable,'-u',str(HERE/'supervisor.py'),*cmd],stdin=subprocess.PIPE,stdout=log,stderr=log,cwd=HERE,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    proc=self.proc
            deadline=time.monotonic()+900
            while time.monotonic()<deadline:
                with self.lock:
                    if epoch!=self.epoch:return
                if proc.poll() is not None:raise RuntimeError('后端启动失败，请查看日志')
                try:
                    with HTTP.open(f'http://127.0.0.1:{self.port}/health',timeout=2) as response:healthy=json.load(response).get('status')=='ok'
                    if healthy:
                        time.sleep(.3)
                        with self.lock:
                            if epoch==self.epoch and proc.poll() is None:self.phase='running';return
                except (OSError,ValueError):pass
                time.sleep(.4)
            raise RuntimeError('模型启动超时（15分钟）')
        except Exception as e:
            with self.lock:
                if epoch!=self.epoch:return
                self.error=str(e)
            self.stop(keep_error=True)
    def stop(self,keep_error=False):
        with self.lock:
            if self.phase=='stopping':return
            self.epoch+=1;self.phase='stopping';proc=self.proc
        try:
            if proc and proc.poll() is None:
                proc.stdin.close();proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            with self.lock:self.phase='error';self.error='停止超时；请查看日志，端口释放前不要重启'
            return
        with self.lock:
            self.proc=None;self.active=None;self.phase='error' if keep_error else 'idle'
            if not keep_error:self.error=''
    def save(self,p):
        fields=['name','kind','model','runtime','python','device','adapter','note']
        p={k:str(p.get(k,'')).strip() for k in fields}|{'id':str(p.get('id') or 'model-'+secrets.token_hex(6))}
        if not p['name'] or p['kind'] not in ('gguf','openvino','v1'):raise ValueError('请输入模型名称与格式')
        if any(len(v)>4096 for v in p.values()):raise ValueError('配置过长')
        with self.lock:
            if p['id']==self.active:raise ValueError('请停止模型后再修改配置')
            self.profiles=[q for q in self.profiles if q['id']!=p['id']]+[p];dump(self.file,self.profiles)
        return p['id']
    def logs(self):
        with self.lock:file=self.log
        if not file or not file.exists():return ''
        with file.open('rb') as f:f.seek(max(0,file.stat().st_size-20000));return f.read().decode('utf-8',errors='replace')

def make_handler(manager,token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def valid_host(self):
            try:return urllib.parse.urlsplit('http://'+self.headers.get('Host','')).hostname in ('127.0.0.1','localhost')
            except ValueError:return False
        def auth(self):
            origin=self.headers.get('Origin')
            return self.valid_host() and secrets.compare_digest(self.headers.get('X-Loader-Token',''),token) and (not origin or origin=='http://'+self.headers.get('Host',''))
        def send(self,code,value,kind='application/json'):
            body=(json.dumps(value,ensure_ascii=False) if kind=='application/json' else value).encode()
            self.send_response(code);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if not self.valid_host():self.send(403,{'error':'Local access only'});return
            if self.path=='/':self.send(200,(HERE/'index.html').read_text(encoding='utf-8').replace('__TOKEN__',token),'text/html');return
            if not self.auth():self.send(403,{'error':'Invalid control token'});return
            if self.path=='/api/status':self.send(200,manager.status())
            elif self.path=='/api/logs':self.send(200,{'text':manager.logs()})
            elif self.path=='/api/continue':
                content=(HERE/'continue.yaml').read_text(encoding='utf-8').replace('18031',str(manager.port));self.send(200,{'text':content})
            else:self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.auth():self.send(403,{'error':'Invalid control token or origin'});return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=1048576:raise ValueError('Invalid body size')
                req=json.loads(self.rfile.read(n))
                if not isinstance(req,dict):raise ValueError('JSON object required')
                if self.path=='/api/start':manager.start(req['id']);result={'ok':True}
                elif self.path=='/api/stop':manager.stop();result={'ok':True}
                elif self.path=='/api/save':result={'id':manager.save(req)}
                elif self.path=='/api/scan':
                    added=0
                    with manager.lock:
                        known={(p['kind'],p['model'],p['runtime'],p['device']) for p in manager.profiles}
                        for p in discover(req['root']):
                            key=(p['kind'],p['model'],p['runtime'],p['device'])
                            if key not in known:manager.profiles.append(p);known.add(key);added+=1
                        dump(manager.file,manager.profiles)
                    result={'added':added}
                elif self.path=='/api/test':
                    if manager.status()['phase']!='running':raise ValueError('请先启动模型')
                    prefix=req.get('prefix','');suffix=req.get('suffix','')
                    if not isinstance(prefix,str) or not isinstance(suffix,str):raise ValueError('代码须为文本')
                    prompt='<|fim_prefix|>'+prefix+'<|fim_suffix|>'+suffix+'<|fim_middle|>'
                    body={'prompt':prompt,'n_predict':12 if req.get('mode')=='api' else 128,'temperature':0,'repeat_penalty':1,'cache_prompt':False,'stream':False,'stop':[suffix.strip()] if suffix.strip() and req.get('mode')!='api' else []}
                    request=urllib.request.Request(f'http://127.0.0.1:{manager.port}/tokenize',data=json.dumps({'content':prompt,'add_special':False,'parse_special':True}).encode(),headers={'Content-Type':'application/json'})
                    with HTTP.open(request,timeout=30) as response:count=len(json.load(response)['tokens'])
                    if count>1253:raise ValueError('上下文超过1250 tokens预算')
                    t=time.perf_counter();request=urllib.request.Request(f'http://127.0.0.1:{manager.port}/completion',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    with HTTP.open(request,timeout=180) as response:result=json.load(response)
                    result['seconds']=time.perf_counter()-t
                elif self.path=='/api/quit':
                    manager.stop();self.send(200,{'ok':True});self.wfile.flush()
                    threading.Thread(target=self.server.shutdown,daemon=True).start();return
                else:self.send(404,{'error':'Not found'});return
                self.send(200,result)
            except Exception as e:self.send(400,{'error':str(e)})
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(HERE.parent));p.add_argument('--state',default=str(HERE/'state'));p.add_argument('--port',type=int,default=18030);p.add_argument('--service-port',type=int,default=18031);p.add_argument('--no-browser',action='store_true');p.add_argument('--discover',action='store_true');a=p.parse_args()
    if a.discover:print(json.dumps(discover(a.root),ensure_ascii=False,indent=2));return
    if a.port==a.service_port:raise ValueError('界面与推理端口须不同')
    manager=Manager(a.state,a.root,a.service_port);token=secrets.token_urlsafe(32)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(manager,token))
    atexit.register(manager.stop);url=f'http://127.0.0.1:{a.port}'
    print('CAD_MODEL_LOADER '+url,flush=True)
    if not a.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:manager.stop();server.server_close()

if __name__=='__main__':main()
