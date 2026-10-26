"""Reproduce tests and write numerical evidence; no profitability claims."""
import hashlib
import io
import json
import random
import sys
import unittest
from datetime import date,timedelta,datetime,timezone
from decimal import Decimal,localcontext
from pathlib import Path
import QuantLib as ql
from dated_bonds import value_bond,value_bill,VERSION
from data_service import analyze
from engine import parse_curves

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from reference_pricer import reference


def independent_cases():
    rng=random.Random(1703);worst=0;accrual_worst=0
    for k in range(1000):
        start=date(rng.randrange(1990,2020),rng.randrange(1,13),15)
        end=date(start.year+rng.randrange(1,41),start.month,15)
        settle=start+timedelta(days=rng.randrange((end-start).days))
        f=rng.choice([1,2,4]);kind=rng.choice(['actual_actual','30_360','actual_365']);convention='compound'
        if k%4==0:f,kind,convention=2,'actual_actual','treasury_auction'
        p=dict(dated_date=start.isoformat(),maturity_date=end.isoformat(),settlement_date=settle.isoformat(),
               coupon=rng.uniform(0,12),frequency=f,day_count=kind,convention=convention,**{'yield':rng.uniform(-2,18)})
        a=value_bond(p);b=reference(p,p['yield']/100)
        worst=max(worst,abs(a['clean_price']-b['clean_price']))
        accrual_worst=max(accrual_worst,abs(a['accrued_per_100']-b['accrued_per_100']))
    return dict(cases=1000,max_price_error=worst,max_accrual_error=accrual_worst,tolerance_per_100=1e-8,
                passed=worst<1e-8 and accrual_worst<1e-8,seed=1703)


def decimal_backtest_check(result):
    records,_=parse_curves((ROOT/'validation'/'gsw_validation_snapshot.csv').read_text(encoding='utf-8'))
    dates={r['date']:r['curve'] for r in records};worst=0
    with localcontext() as ctx:
        ctx.prec=50
        total=Decimal(1)
        for trade in result['trades']:
            curve=dates[trade['signal_date']];nxt=dates[trade['end_date']]
            t=Decimal(trade['maturity'])
            h=Decimal((date.fromisoformat(trade['end_date'])-date.fromisoformat(trade['signal_date'])).days)/Decimal('365.25')
            residual=t-h
            knots=sorted(nxt)
            left=max(k for k in knots if Decimal(str(k))<=residual)
            right=min(k for k in knots if Decimal(str(k))>=residual)
            weight=(residual-Decimal(str(left)))/(Decimal(str(right))-Decimal(str(left)))
            z1=Decimal(str(nxt[left]))*(1-weight)+Decimal(str(nxt[right]))*weight
            p0=(-Decimal(str(curve[float(t)]))*t).exp();p1=(-z1*residual).exp()
            ret=p1/p0-1-Decimal(str(trade['cost']))
            worst=max(worst,abs(float(ret)-trade['net_return']))
            total*=1+ret
        final_diff=abs(float(total)-result['equity'][-1]['strategy'])
    return dict(periods_checked=len(result['trades']),precision_digits=50,max_return_error=worst,
                final_wealth_error=final_diff,passed=worst<1e-12 and final_diff<1e-11)


def main():
    report_dir=ROOT/'validation';report_dir.mkdir(exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    log=io.StringIO();run=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (report_dir/'test_output.txt').write_text(log.getvalue(), encoding='utf-8')
    independent=independent_cases();cases=json.loads((ROOT/'tests'/'treasury_fixtures.json').read_text(encoding='utf-8'));official=[]
    for case in cases:
        r=value_bond(case['input']) if case['type']=='bond' else value_bill(case['input'])
        expected=case.get('expected_clean',case.get('expected_price'))
        calculated=r['clean_price'] if case['type']=='bond' else r['price']
        row=dict(id=case['id'],source=case['source'],expected_price=expected,calculated_price=calculated,
                 absolute_error=abs(calculated-expected),passed=abs(calculated-expected)<=.00000051)
        if case['type']=='bond':
            row.update(expected_accrued_1000=case['expected_accrued_1000'],calculated_accrued_1000=r['accrued_value'],
                       accrual_absolute_error=abs(r['accrued_value']-case['expected_accrued_1000']))
            row['passed'] &= row['accrual_absolute_error']<=.0000051
        official.append(row)
    result=analyze(dict(mode='snapshot',start='2010-01-01',end='2025-12-31',cost_bps=5,max_maturity=10,score='carry'))
    decimal_check=decimal_backtest_check(result)
    (report_dir/'real_backtest_results.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding='utf-8')
    samples={label:analyze(dict(mode='snapshot',start=start,end=end,cost_bps=5))['metrics'] for label,start,end in
             [('2010–2019','2010-01-01','2019-12-31'),('2020–2025','2020-01-01','2025-12-31')]}
    browser='Not verified for these source files.'
    browser_path=report_dir/'browser_checks.json'
    if browser_path.exists():
        b=json.loads(browser_path.read_text(encoding='utf-8'))
        match=all(b.get(key)==hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for key,name in
                  [('ui_source_sha256','index.html'),('app_source_sha256','app.py'),('engine_source_sha256','dated_bonds.py')])
        if b.get('status')=='PASS' and match:
            browser=f"PASS: {len(b['checks'])} Chromium {b['browser']} workflow checks, including exports and mobile viewport; desktop and mobile screenshots visually inspected."
    passed=run.wasSuccessful() and independent['passed'] and all(x['passed'] for x in official) and decimal_check['passed']
    output=dict(status='PASS' if passed else 'FAIL',engine_version=VERSION,quantlib_version=ql.__version__,
                python_version=sys.version,generated_utc=datetime.now(timezone.utc).isoformat(),
                tests_run=run.testsRun,failures=len(run.failures),errors=len(run.errors),independent=independent,
                yield_roundtrips=300,treasury=official,decimal_backtest_validation=decimal_check,
                real_data={'start':result['start'],'end':result['end'],'periods':result['periods'],
                           'metrics':result['metrics'],'subperiods':samples,'metadata':result['metadata']},
                browser_validation=browser)
    (report_dir/'results.json').write_text(json.dumps(output,indent=2,allow_nan=False), encoding='utf-8')
    lines=['# BondLab 2.0 validation report','',f"Status: **{output['status']}**. Generated {output['generated_utc']}.",'',
           f"Engine {VERSION}; QuantLib {ql.__version__}; Python {sys.version.split()[0]}.",'',
           f"{run.testsRun} test methods passed." if run.wasSuccessful() else 'Automated tests failed.',
           '', '## Independent numerical checks','',
           f"- 1,000 seeded independent Python-oracle comparisons; maximum clean-price difference **{independent['max_price_error']:.12g} per $100** (tolerance 1e-8).",
           f"- Maximum accrued-interest difference: {independent['max_accrual_error']:.12g} per $100.",
           '- 300 price/yield round trips; yield tolerance 1e-9 (decimal yield), price residual tolerance 1e-7 per $100.',
           '- Analytical duration and convexity checked with finite differences for both yield conventions.',
           '- Month-end, leap-day, invalid-input, concurrent-call, portfolio-scaling and API/audit checks.',
           '', '## Official Treasury evidence','',
           '| Auction | Published price | Calculated price | Absolute difference |','|---|---:|---:|---:|']
    for row in official:lines.append(f"| {row['id']} | {row['expected_price']:.6f} | {row['calculated_price']:.9f} | {row['absolute_error']:.3g} |")
    lines+=['','All prices are per $100 face. Tolerance 0.00000051 reflects six-decimal publication rounding. Accrued interest on the two reopenings is checked separately to 0.0000051 dollars per $1,000. Source URLs and SHA-256 manifests are included. Official PDFs can be downloaded locally with `python prepare_validation_data.py`; they are not distributed in this repository.','',
            '### Convention finding','',
            'The December 2024 reopening produces 100.114149683 under the Treasury auction formula, versus approximately 100.117266263 under conventional fractional-period compound discounting. These are distinct conventions. The app labels them separately and reproduces the auction with its designated mode.','',
            '## Real-data strategy evaluation','',
            f"Federal Reserve GSW month-end snapshot: {result['start']} to {result['end']}; {result['periods']} holding periods. Fixed parameters: highest raw one-month carry, 2/3/5/7/10-year choices, 5 bps monthly round-trip cost. No parameter optimization was performed.",'',
            '| Portfolio | CAGR | Annual volatility | Maximum drawdown | Excess Sharpe |','|---|---:|---:|---:|---:|']
    for name,m in result['metrics'].items():
        sharpe='N/A' if m['sharpe'] is None else f"{m['sharpe']:.3f}"
        lines.append(f"| {name} | {m['cagr']:.3%} | {m['volatility']:.3%} | {m['max_drawdown']:.3%} | {sharpe} |")
    lines+=['',f"Every strategy holding-period return was independently recomputed with 50-digit Decimal discount factors. Maximum return difference: {decimal_check['max_return_error']:.3g}; final wealth difference: {decimal_check['final_wealth_error']:.3g}.",'',
            'Subperiod results and cost sensitivity are in real_backtest_results.json / results.json. These are retrospective checks, not a preregistered experiment or evidence of future profits.','',
            '## Scope and unresolved production work','',
            'Verified scope: regular fixed-rate bullet bonds, contractual unadjusted dates, three day counts, periodic compound yield, regular-period U.S. Treasury auction pricing, and Treasury bill bank-discount pricing. Irregular schedules are rejected.','',
            'Not covered: holiday-adjusted payments, settlement-lag automation, odd coupons, ex-coupon markets, credit/default valuation, callable/putable bonds, amortizers, TIPS, FRNs, taxes, broker execution, or live market quote validation. Long-bill simple investment yield is explicitly not labeled Treasury coupon-equivalent investment yield.','',
            'The strategy uses fitted zero curves rather than executable quotes; fixed costs, no trading latency, a one-year-yield cash proxy, and current-vintage revised data. Different maturities carry different duration risk.','',
            output['browser_validation'],'',
            'The server is designed for local single-user use. Public commercial hosting requires separately validated account isolation, operations, security, backups and data rights. These tests are not independent external certification.','',
            '## Reproduce','', 'Install requirements-dev.txt, then run `python validate.py`. Refreshing data is a separate explicit command: `python prepare_validation_data.py`; this changes the data vintage.','']
    (ROOT/'VALIDATION.md').write_text('\n'.join(lines), encoding='utf-8')
    diagnostics=[{'test':str(test),'traceback':trace} for test,trace in run.failures+run.errors]
    print(json.dumps({'status':output['status'],'tests':run.testsRun,
                      'failures':len(run.failures),'errors':len(run.errors),
                      'test_diagnostics':diagnostics,'independent':independent,
                      'decimal_check':decimal_check,'real_metrics':result['metrics']},indent=2))
    return 0 if passed else 1


if __name__=='__main__':sys.exit(main())
