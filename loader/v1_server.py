"""Inference-only HTTP server for the v1 base + LoRA. No training source imports."""
import argparse,json,os,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--adapter');p.add_argument('--device',default='0');p.add_argument('--port',type=int,default=18031);a=p.parse_args()
    root=Path(a.model).resolve();base=root/'models/Qwen2.5-Coder-3B'
    os.environ['CUDA_VISIBLE_DEVICES']=a.device
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig,StoppingCriteria,StoppingCriteriaList
    from peft import PeftModel,prepare_model_for_kbit_training
    torch.set_num_threads(8);torch.cuda.set_per_process_memory_fraction(.8)
    tok=AutoTokenizer.from_pretrained(base,local_files_only=True)
    tok.padding_side='left';tok.pad_token=tok.eos_token
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    model=AutoModelForCausalLM.from_pretrained(base,local_files_only=True,quantization_config=quant,torch_dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
    # Match v1's dtype preparation and frozen parameters. This does not train.
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=False,gradient_checkpointing_kwargs={'use_reentrant':False})
    model=PeftModel.from_pretrained(model,Path(a.adapter) if a.adapter else root/'adapter',is_trainable=False);model.eval()
    lock=threading.Lock()
    class SuffixStop(StoppingCriteria):
        def __init__(self,start,suffix):self.start=start;self.suffix=suffix.strip()
        def __call__(self,input_ids,scores,**kwargs):
            texts=tok.batch_decode(input_ids[:,self.start:],skip_special_tokens=True);s=self.suffix
            return torch.tensor([bool(s) and (t.startswith(s) or '\n'+s in t) for t in texts],device=input_ids.device)
    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,value,stream=False):
            body=(('data: '+json.dumps(value,ensure_ascii=False)+'\n\n') if stream else json.dumps(value,ensure_ascii=False)).encode()
            self.send_response(code);self.send_header('Content-Type','text/event-stream' if stream else 'application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path=='/health':self.reply(200,{'status':'ok','device':'CUDA','runtime':'NF4/BF16'})
            elif self.path=='/props':self.reply(200,{'model_path':str(root),'total_slots':1})
            else:self.reply(404,{'error':'Use raw FIM /completion'})
        def do_POST(self):
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=1048576:raise ValueError('Invalid body size')
                req=json.loads(self.rfile.read(n))
                with lock:
                    if self.path=='/tokenize':self.reply(200,{'tokens':tok.encode(req['content'],add_special_tokens=False)});return
                    if self.path!='/completion':raise ValueError('Use /completion')
                    prompt=req['prompt']
                    if not isinstance(prompt,str) or not prompt.startswith('<|fim_prefix|>') or not prompt.endswith('<|fim_middle|>'):raise ValueError('Expected raw FIM')
                    prefix,suffix=prompt[len('<|fim_prefix|>'):-len('<|fim_middle|>')].split('<|fim_suffix|>',1)
                    if len(tok.encode(prefix+suffix,add_special_tokens=False))>1250:raise ValueError('Context exceeds evaluated budget')
                    limit=12 if int(req.get('n_predict',128))<=12 else 128
                    inputs=tok([prompt],padding=True,add_special_tokens=False,return_tensors='pt').to('cuda');start=inputs['input_ids'].shape[1]
                    stops=StoppingCriteriaList([] if limit==12 else [SuffixStop(start,suffix)]);t=time.perf_counter()
                    with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
                        ids=model.generate(**inputs,max_new_tokens=limit,do_sample=False,pad_token_id=tok.eos_token_id,eos_token_id=tok.eos_token_id,use_cache=True,stopping_criteria=stops)
                    torch.cuda.synchronize();seq=ids[0];raw=tok.decode(seq[start:],skip_special_tokens=True)
                    hit=len(seq)-start>=limit and int(seq[-1])!=tok.eos_token_id
                self.reply(200,{'content':raw,'stop':True,'truncated':False,'stop_type':'limit' if hit else 'eos','timings':{'elapsed_ms':(time.perf_counter()-t)*1000}},bool(req.get('stream')))
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as e:self.reply(400,{'error':str(e)})
    print('V1_READY',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
