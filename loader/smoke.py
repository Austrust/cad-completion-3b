"""Exercise the same control API as the UI against real model files."""
import argparse,json,re,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--kinds',default='gguf');p.add_argument('--examples',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    here=Path(__file__).resolve().parent;out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='smoke-',dir=out.parent));port=18034;service=18035
    proc=subprocess.Popen([sys.executable,'-u',str(here/'app.py'),'--root',a.root,'--state',str(tmp),'--port',str(port),'--service-port',str(service),'--no-browser'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    results=[];base=f'http://127.0.0.1:{port}'
    try:
        line=proc.stdout.readline();assert 'CAD_MODEL_LOADER' in line,line
        with HTTP.open(base) as r:token=re.search("const token='([^']+)'",r.read().decode())[1]
        def call(route,data=None):
            req=urllib.request.Request(base+'/api/'+route,data=None if data is None else json.dumps(data).encode(),headers={'X-Loader-Token':token,'Content-Type':'application/json'})
            with HTTP.open(req,timeout=240) as r:return json.load(r)
        profiles=[v for v in call('status')['profiles'] if v['kind'] in a.kinds.split(',')]
        assert profiles,'No matching profiles'
        examples=[json.loads(line) for line in Path(a.examples).read_text(encoding='utf-8').splitlines() if line]
        for profile in profiles:
            record={'name':profile['name'],'kind':profile['kind'],'device':profile['device'],'examples':[]};results.append(record)
            start=time.monotonic();call('start',{'id':profile['id']})
            for _ in range(1800):
                status=call('status')
                if status['phase'] in ('running','error'):break
                time.sleep(.5)
            if status['phase']!='running':
                record['error']=status['error'];record['log']=call('logs')['text'];raise RuntimeError(record['error'])
            record['load_seconds']=time.monotonic()-start
            for row in examples:
                result=call('test',row);assert result.get('content'),result
                record['examples'].append({'id':row['id'],'content':result['content'],'seconds':result['seconds']})
            call('stop',{});assert call('status')['phase']=='idle'
            with socket.socket() as s:assert s.connect_ex(('127.0.0.1',service))!=0,'Backend port still occupied'
            record['stopped_and_port_released']=True
            print(json.dumps({'name':record['name'],'examples':len(record['examples']),'load_seconds':record['load_seconds'],'stopped':True},ensure_ascii=False),flush=True)
        call('quit',{});proc.wait(timeout=30)
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=30)
        out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    return results
if __name__=='__main__':main()
