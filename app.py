"""Local single-user analytics: explicit sessions, input checks and audited runs."""
import argparse
import hashlib
import json
import logging
import secrets
import sqlite3
import threading
import time
import uuid
import webbrowser
from collections import deque
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse,JSONResponse
import uvicorn
from dated_bonds import value_bond,value_bill,value_portfolio,VERSION
from engine import carry_table,number
from data_service import analyze,DATA

ROOT=Path(__file__).resolve().parent
TOKEN=secrets.token_urlsafe(32)
app=FastAPI(title='BondLab Analytics',version=VERSION,docs_url=None,redoc_url=None,openapi_url=None)
LOG=logging.getLogger('bondlab')
LOCK=threading.RLock()
HITS=deque()


@contextmanager
def connection():
    DATA.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(DATA/'bondlab.sqlite',timeout=20)
    try:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created_utc TEXT, kind TEXT, input_sha256 TEXT, output_sha256 TEXT, engine_version TEXT, input_json TEXT, output_json TEXT)')
        with con:
            yield con
    finally:
        # sqlite3's transaction context commits/rolls back, but does not close.
        # Explicit closure releases database and WAL handles before Windows cleanup.
        con.close()


def record(kind,p,result):
    ident=uuid.uuid4().hex
    inp=json.dumps(p,sort_keys=True,allow_nan=False);out=json.dumps(result,sort_keys=True,allow_nan=False)
    stamp=datetime.now(timezone.utc).isoformat()
    with LOCK,connection() as con:
        con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(ident,stamp,kind,
                     hashlib.sha256(inp.encode()).hexdigest(),hashlib.sha256(out.encode()).hexdigest(),VERSION,inp,out))
    return dict(result,run_id=ident,created_utc=stamp)


@app.middleware('http')
async def local_boundary(request:Request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('127.0.0.1','localhost'):
        return JSONResponse({'error':'Only local host access is supported.'},403)
    origin=request.headers.get('origin')
    if origin and origin not in ('http://'+request.headers.get('host',''),'https://'+request.headers.get('host','')):
        return JSONResponse({'error':'Cross-origin access is not allowed.'},403)
    if request.method=='POST':
        if not secrets.compare_digest(request.headers.get('x-bondlab-token',''),TOKEN):
            return JSONResponse({'error':'Session token missing or expired. Reload the page.'},403)
        if request.headers.get('content-type','').split(';')[0]!='application/json':
            return JSONResponse({'error':'Content-Type must be application/json.'},415)
        size=0;chunks=[]
        async for chunk in request.stream():
            size+=len(chunk)
            if size>25_000_000:return JSONResponse({'error':'Request exceeds 25 MB.'},413)
            chunks.append(chunk)
        request._body=b''.join(chunks)
        with LOCK:
            now=time.monotonic()
            while HITS and HITS[0]<now-60:HITS.popleft()
            if len(HITS)>=90:return JSONResponse({'error':'Too many requests; retry shortly.'},429)
            HITS.append(now)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store'
    return response


@app.get('/')
def home():
    nonce=secrets.token_urlsafe(20)
    html=(ROOT/'index.html').read_text(encoding='utf-8').replace('<script>','<script nonce="'+nonce+'">')
    response=HTMLResponse(html)
    response.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
    return response


@app.get('/api/session')
def session():return {'token':TOKEN,'engine_version':VERSION}


@app.get('/api/health')
def health():return {'status':'ok','engine_version':VERSION,'deployment':'local-single-user'}


@app.get('/api/validation')
def validation():
    path=ROOT/'validation'/'results.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'status':'not_run'}


@app.get('/api/runs')
def runs():
    with connection() as con:
        rows=con.execute('SELECT id,created_utc,kind,input_sha256,output_sha256,engine_version FROM runs ORDER BY created_utc DESC LIMIT 30').fetchall()
    return {'runs':[dict(zip(['run_id','created_utc','kind','input_sha256','output_sha256','engine_version'],r)) for r in rows]}


@app.get('/api/runs/{run_id}')
def saved_run(run_id:str):
    if len(run_id)!=32 or any(c not in '0123456789abcdef' for c in run_id):return JSONResponse({'error':'Run not found.'},404)
    with connection() as con:
        row=con.execute('SELECT input_json,output_json,created_utc,kind FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row:return JSONResponse({'error':'Run not found.'},404)
    return {'run_id':run_id,'input':json.loads(row[0]),'output':json.loads(row[1]),'created_utc':row[2],'kind':row[3]}


def dispatch(kind,p):
    if not isinstance(p,dict):raise ValueError('Request must be a JSON object.')
    if kind=='calculate':return value_bond(p)
    if kind=='bill':return value_bill(p)
    if kind=='portfolio':return value_portfolio(p)
    if kind=='backtest':return analyze(p)
    if kind=='carry':
        if not isinstance(p.get('curve'),dict):raise ValueError('Curve must be an object of tenor:yield pairs.')
        curve={number(k,.01,100,'Tenor (years)'):number(v,-20,50,'Zero yield (%)')/100 for k,v in p['curve'].items()}
        horizon=number(p.get('horizon_months',1),1,6,'Horizon months')/12
        return {'rows':carry_table(curve,horizon,[2,3,5,7,10])}
    raise ValueError('Unknown analysis type.')


@app.post('/api/{kind}')
async def calculate(kind:str,request:Request):
    try:
        p=await request.json()
        from starlette.concurrency import run_in_threadpool
        result=await run_in_threadpool(dispatch,kind,p)
        return await run_in_threadpool(record,kind,p,result)
    except (ValueError,KeyError,TypeError,RuntimeError) as e:
        return JSONResponse({'error':str(e)},422)
    except Exception:
        LOG.exception('Analysis failed')
        return JSONResponse({'error':'Analysis failed. Check data availability and the application log.'},503)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='BondLab local analytics')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not args.no_browser:
        timer=threading.Timer(1.5,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}'))
        timer.daemon=True;timer.start()
    uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='info')
