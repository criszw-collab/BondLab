"""Immutable curve snapshots and reproducible strategy evaluation."""
import hashlib
import json
import os
import threading
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.request import Request, urlopen
from engine import parse_curves, demo_curves, backtest

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('BONDLAB_DATA_DIR',str(ROOT/'data')))
FED_URL='https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv'
LOCK=threading.RLock()


def snapshot(raw,source):
    digest=hashlib.sha256(raw).hexdigest()
    folder=DATA/'snapshots'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(digest+'.csv')
    with LOCK:
        if not path.exists():
            tmp=folder/(digest+'.tmp');tmp.write_bytes(raw);tmp.replace(path)
    return dict(sha256=digest,source=source,bytes=len(raw),retrieved_utc=datetime.now(timezone.utc).isoformat())


def analyze(payload):
    mode=payload.get('mode','snapshot')
    if mode=='demo':
        records=demo_curves();meta={'source':'SYNTHETIC demonstration — not market history'}
    else:
        if mode=='snapshot':
            provenance=json.loads((ROOT/'validation'/'snapshot_manifest.json').read_text(encoding='utf-8'))
            raw=(ROOT/'validation'/'gsw_validation_snapshot.csv').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=provenance['sha256']:
                raise ValueError('Bundled snapshot failed its SHA-256 integrity check.')
        elif mode=='fed':
            req=Request(FED_URL,headers={'User-Agent':'BondLab/2.0 fixed-income research'})
            with urlopen(req,timeout=35) as response:raw=response.read(20_000_001)
            if len(raw)>20_000_000:raise ValueError('Downloaded data exceeds 20 MB.')
            provenance=snapshot(raw,FED_URL)
        elif mode=='csv':
            raw=str(payload.get('csv','')).encode('utf-8')
            provenance=snapshot(raw,'User-uploaded continuously compounded zero yields (%)')
        else:raise ValueError('Unknown data source.')
        records,meta=parse_curves(raw.decode('utf-8-sig'));meta.update(provenance)
    records=[r for r in records if r['date']<=date.today().isoformat()]
    for key in ('start','end'):
        if payload.get(key):
            try:date.fromisoformat(payload[key])
            except (ValueError,TypeError):raise ValueError(f'{key} must be an ISO date.') from None
    if payload.get('start'):records=[r for r in records if r['date']>=payload['start']]
    if payload.get('end'):records=[r for r in records if r['date']<=payload['end']]
    args=(payload.get('cost_bps',5),payload.get('max_maturity',10),payload.get('score','carry'))
    result=backtest(records,*args)
    result.update(metadata=meta,start=records[0]['date'],end=records[-1]['date'])
    result['cost_sensitivity']=[dict(cost_bps=c,**backtest(records,c,args[1],args[2])['metrics']['strategy']) for c in (0,5,10,25)]
    result['yearly_returns']=[]
    for year in sorted({t['end_date'][:4] for t in result['trades']}):
        row={'year':year}
        for name,key in [('strategy','net_return'),('equal_weight','benchmark_return'),('cash_proxy','cash_proxy_return')]:
            wealth=1
            for t in result['trades']:
                if t['end_date'].startswith(year):wealth*=1+t[key]
            row[name]=wealth-1
        result['yearly_returns'].append(row)
    result['parameters']={'cost_bps':float(args[0]),'max_maturity':float(args[1]),'score':args[2]}
    return result
