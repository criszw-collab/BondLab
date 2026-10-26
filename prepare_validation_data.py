"""Download official evidence and freeze a compact reproducible month-end sample.

Run manually when replacing a validation data vintage; ordinary app use does not
refresh this snapshot. This is distinct from the app's latest-data download.
"""
import csv
import hashlib
import io
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from engine import parse_curves
from data_service import FED_URL

ROOT=Path(__file__).resolve().parent


def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'BondLab research validation'}),timeout=45) as r:
        return r.read(20_000_000)


def main():
    dest=ROOT/'validation';dest.mkdir(exist_ok=True)
    raw=fetch(FED_URL)
    records,quality=parse_curves(raw.decode('utf-8-sig'))
    records=[r for r in records if '2010-01-01'<=r['date']<='2025-12-31']
    if len(records)!=192:raise ValueError(f'Expected 192 monthly observations; got {len(records)}.')
    buf=io.StringIO(newline='')
    writer=csv.writer(buf);writer.writerow(['Date']+[f'y{i}' for i in range(1,11)])
    for r in records:writer.writerow([r['date']]+[format(r['curve'][float(i)]*100,'.15g') for i in range(1,11)])
    snapshot=buf.getvalue().encode()
    (dest/'gsw_validation_snapshot.csv').write_bytes(snapshot)
    manifest=dict(source=FED_URL,source_description='Federal Reserve GSW, month-end zero-yield subset',
                  retrieved_utc=datetime.now(timezone.utc).isoformat(),
                  raw_source_sha256=hashlib.sha256(raw).hexdigest(),
                  sha256=hashlib.sha256(snapshot).hexdigest(),monthly_rows=len(records),
                  start=records[0]['date'],end=records[-1]['date'],
                  transformation='Last complete observation per month, 2010–2025, SVENY01–SVENY10; unchanged percent continuously compounded units.',
                  source_quality=quality)
    (dest/'snapshot_manifest.json').write_text(json.dumps(manifest,indent=2), encoding='utf-8')
    evidence=[]
    for case in json.loads((ROOT/'tests'/'treasury_fixtures.json').read_text(encoding='utf-8')):
        pdf=fetch(case['source'])
        if not pdf.startswith(b'%PDF'):raise ValueError('Official evidence response is not a PDF.')
        filename=case['id']+'.pdf';(dest/filename).write_bytes(pdf)
        evidence.append(dict(id=case['id'],source=case['source'],filename=filename,sha256=hashlib.sha256(pdf).hexdigest()))
    (dest/'treasury_source_manifest.json').write_text(json.dumps(evidence,indent=2), encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
