"""Explicit-date vanilla bond analytics. Prices quoted per 100 of principal.

QuantLib is used for conventional yield pricing. Treasury auction mode implements
31 CFR 356 Appendix B, III.D (simple first partial period). No global evaluation
date is mutated; each valuation supplies its settlement date explicitly.
"""
import math
import threading
from datetime import date
import QuantLib as ql
from engine import number

QL_LOCK = threading.RLock()
VERSION = '2.0.1'
FREQUENCIES = {1: ql.Annual, 2: ql.Semiannual, 4: ql.Quarterly}
DAYCOUNTS = ('actual_actual', '30_360', 'actual_365')
ALLOWED = {'label', 'face', 'coupon', 'dated_date', 'maturity_date', 'settlement_date',
           'frequency', 'day_count', 'end_of_month', 'convention', 'input_mode',
           'yield', 'clean_price', 'shock'}


def iso(value, name):
    try:
        d = date.fromisoformat(str(value))
        if not 1901 <= d.year <= 2199:
            raise ValueError()
        return d
    except (ValueError, TypeError):
        raise ValueError(f'{name} must be an ISO date in 1901–2199.') from None


def qdate(d):
    return ql.Date(d.day, d.month, d.year)


def datestr(d):
    return date(d.year(), d.month(), d.dayOfMonth()).isoformat()


def instrument(p):
    if not isinstance(p, dict):
        raise ValueError('Bond inputs must be a JSON object.')
    unknown = set(p)-ALLOWED
    if unknown:
        raise ValueError('Unknown bond input: '+', '.join(sorted(unknown)))
    face = number(p.get('face', 1000), 1, 1e9, 'Face value')
    coupon = number(p.get('coupon', 4.25), 0, 30, 'Coupon (%)')/100
    freq = number(p.get('frequency', 2), 1, 4, 'Frequency')
    if freq not in FREQUENCIES:
        raise ValueError('Frequency must be 1, 2 or 4.')
    freq = int(freq)
    dated = iso(p.get('dated_date', '2024-11-15'), 'Dated date')
    maturity = iso(p.get('maturity_date', '2034-11-15'), 'Maturity')
    settle = iso(p.get('settlement_date', date.today().isoformat()), 'Settlement')
    if not dated <= settle < maturity:
        raise ValueError('Require dated date ≤ settlement date < maturity date.')
    if (maturity-dated).days > 366*60:
        raise ValueError('Maximum original term is 60 years.')
    convention = p.get('convention', 'compound')
    if convention not in ('compound', 'treasury_auction'):
        raise ValueError('Unknown yield convention.')
    kind = p.get('day_count', 'actual_actual')
    if kind not in DAYCOUNTS:
        raise ValueError('Unsupported day-count convention.')
    eom = p.get('end_of_month', False)
    if not isinstance(eom, bool):
        raise ValueError('end_of_month must be true or false.')
    if convention == 'treasury_auction' and (freq != 2 or kind != 'actual_actual'):
        raise ValueError('Treasury auction mode requires semiannual Actual/Actual.')
    schedule = ql.Schedule(qdate(dated), qdate(maturity), ql.Period(12//freq, ql.Months),
                           ql.NullCalendar(), ql.Unadjusted, ql.Unadjusted,
                           ql.DateGeneration.Backward, eom)
    if any(not schedule.isRegular(i) for i in range(1, len(schedule))):
        raise ValueError('Irregular coupon periods are not supported. Supply the original regular dated date.')
    dc = (ql.ActualActual(ql.ActualActual.Bond, schedule) if kind == 'actual_actual' else
          ql.Thirty360(ql.Thirty360.BondBasis) if kind == '30_360' else ql.Actual365Fixed())
    bond = ql.FixedRateBond(0, 100.0, schedule, [coupon], dc, ql.Unadjusted, 100.0, qdate(dated))
    return dict(face=face, coupon=coupon, freq=freq, dated=dated, maturity=maturity,
                settle=settle, convention=convention, kind=kind, schedule=schedule,
                dc=dc, bond=bond, settlement=qdate(settle))


def components(i, y):
    """Clean, dirty, accrued quote and first two derivatives of dirty price."""
    bond, dc, sd, f = i['bond'], i['dc'], i['settlement'], i['freq']
    accrued = bond.accruedAmount(sd)
    if i['convention'] == 'compound':
        clean = ql.BondFunctions.cleanPrice(bond, y, dc, ql.Compounded, FREQUENCIES[f], sd)
        dirty = clean+accrued
        duration = ql.BondFunctions.duration(bond, y, dc, ql.Compounded, FREQUENCIES[f], ql.Duration.Modified, sd)
        convexity = ql.BondFunctions.convexity(bond, y, dc, ql.Compounded, FREQUENCIES[f], sd)
        return clean, dirty, accrued, -dirty*duration, dirty*convexity
    # Contractual regular semiannual schedule; no ex-coupon period or stubs.
    future = [d for d in i['schedule'] if d > sd]
    previous = max(d for d in i['schedule'] if d <= sd)
    frac = (future[0]-sd)/(future[0]-previous)
    c, b, a = 100*i['coupon']/2, 1+y/2, frac/2
    u = 1+y*a
    if b <= 0 or u <= 0:
        raise ValueError('Yield produces invalid discount factors.')
    pv = d1 = d2 = 0.0
    for k in range(len(future)):
        cash = c+(100 if k == len(future)-1 else 0)
        term = cash*b**(-k)/u
        logd = -k/(2*b)-a/u
        logdd = k/(4*b*b)+a*a/(u*u)
        pv += term
        d1 += term*logd
        d2 += term*(logd*logd+logdd)
    return pv-accrued, pv, accrued, d1, d2


def solve_yield(i, clean):
    if i['convention'] == 'compound':
        y = i['bond'].bondYield(ql.BondPrice(clean, ql.BondPrice.Clean), i['dc'],
                                ql.Compounded, FREQUENCIES[i['freq']], i['settlement'],
                                1e-12, 1000, 0.04)
    else:
        lo, hi = -0.20, 1.0
        if not components(i, hi)[0] <= clean <= components(i, lo)[0]:
            raise ValueError('Price implies yield outside supported range −20% to 100%.')
        for _ in range(100):
            mid = (lo+hi)/2
            if components(i, mid)[0] > clean:
                lo = mid
            else:
                hi = mid
        y = (lo+hi)/2
    if not -.20 <= y <= 1:
        raise ValueError('Price implies yield outside supported range −20% to 100%.')
    residual = components(i, y)[0]-clean
    if abs(residual)>1e-7:
        raise ValueError('Yield solver failed the price-residual tolerance.')
    return y, residual


def value_bond(p):
    with QL_LOCK:
        i = instrument(p)
        mode = p.get('input_mode', 'yield')
        if mode not in ('yield', 'price'):
            raise ValueError('Input mode must be yield or price.')
        residual = 0.0
        if mode == 'yield':
            y = number(p.get('yield', 4.347), -20, 100, 'Yield (%)')/100
        else:
            clean_input = number(p.get('clean_price', 100), 0.01, 10000, 'Clean price per 100')
            y, residual = solve_yield(i, clean_input)
        clean, dirty, accrued, first, second = components(i, y)
        if min(clean, dirty) <= 0 or not all(math.isfinite(x) for x in (clean, dirty, first, second)):
            raise ValueError('Inputs produce an invalid valuation.')
        scale = i['face']/100
        duration, convexity = -first/dirty, second/dirty
        rows = []
        for cf in i['bond'].cashflows():
            if cf.date() > i['settlement']:
                rows.append({'date': datestr(cf.date()), 'amount': cf.amount()*scale,
                             'kind': 'principal' if cf == i['bond'].cashflows()[-1] else 'coupon'})
        # SWIG wrappers do not preserve identity; final redemption is always last.
        if rows:
            rows[-1]['kind'] = 'principal'
        scenarios = []
        for bps in [-200, -100, -50, -1, 0, 1, 50, 100, 200]:
            c, d, *_ = components(i, y+bps/10000)
            scenarios.append(dict(shock_bps=bps, clean_price=c, dirty_price=d,
                                  market_value=d*scale, pnl=(d-dirty)*scale,
                                  price_return=d/dirty-1))
        shock = number(p.get('shock', -1), -10, 10, 'Shock (percentage points)')/100
        _, shocked, *_ = components(i, y+shock)
        # Current yield convention uses quoted clean price. Dollar coupons can
        # vary under Actual/365, so the full schedule remains authoritative.
        return dict(engine_version=VERSION, quantlib_version=ql.__version__,
                    label=str(p.get('label', 'Bond'))[:120], input=p,
                    clean_price=clean, dirty_price=dirty, accrued_per_100=accrued,
                    clean_value=clean*scale, accrued_value=accrued*scale,
                    settlement_value=dirty*scale, ytm=y, annual_coupon=i['face']*i['coupon'],
                    current_yield=100*i['coupon']/clean, modified_duration=duration,
                    macaulay_duration=duration*(1+y/i['freq']) if i['convention']=='compound' else None,
                    convexity=convexity, dv01=-first*scale*.0001,
                    exact_dv01=(components(i,y-.0001)[1]-components(i,y+.0001)[1])*scale/2,
                    shocked_value=shocked*scale, shock_pnl=(shocked-dirty)*scale,
                    shock_return=shocked/dirty-1,
                    duration_estimate=-duration*shock,
                    convexity_estimate=-duration*shock+.5*convexity*shock*shock,
                    yield_solver_residual_per_100=residual,
                    settlement_date=i['settle'].isoformat(), maturity_date=i['maturity'].isoformat(),
                    next_coupon=next((r['date'] for r in rows if r['kind']=='coupon'), None),
                    scenarios=scenarios, cashflows=rows,
                    assumptions=['Contractual coupon dates; no business-day payment adjustment.',
                                 'Regular fixed-rate bullet bond; no calls, puts, default, tax or ex-coupon treatment.',
                                 'Settlement is explicitly supplied; no automatic T+1 or holiday settlement calculation.',
                                 'Treasury auction mode uses simple first-period discounting; compound mode uses nominal periodic YTM.'])


def value_portfolio(p):
    bonds = p.get('bonds')
    if not isinstance(bonds, list) or not 1 <= len(bonds) <= 100:
        raise ValueError('Portfolio must contain 1–100 bonds.')
    results = [value_bond(b) for b in bonds]
    dates = {r['settlement_date'] for r in results}
    if len(dates)!=1:
        raise ValueError('All portfolio positions must use the same settlement date.')
    total = sum(r['settlement_value'] for r in results)
    cash = {}
    for r in results:
        for cf in r['cashflows']:
            m = cf['date'][:7]
            cash[m] = cash.get(m, 0)+cf['amount']
    return dict(positions=results, settlement_value=total,
                clean_value=sum(r['clean_value'] for r in results),
                accrued_value=sum(r['accrued_value'] for r in results),
                dv01=sum(r['dv01'] for r in results),
                weighted_duration=sum(r['modified_duration']*r['settlement_value'] for r in results)/total,
                weighted_convexity=sum(r['convexity']*r['settlement_value'] for r in results)/total,
                annual_coupon=sum(r['annual_coupon'] for r in results),
                scenarios=[dict(shock_bps=s['shock_bps'], pnl=sum(r['scenarios'][j]['pnl'] for r in results))
                           for j,s in enumerate(results[0]['scenarios'])],
                cashflows=[{'month': m, 'amount': cash[m]} for m in sorted(cash)])


def value_bill(p):
    if not isinstance(p, dict):
        raise ValueError('Bill inputs must be an object.')
    allowed={'face','settlement_date','maturity_date','input_mode','discount_rate','price'}
    if set(p)-allowed:
        raise ValueError('Unknown bill input: '+', '.join(sorted(set(p)-allowed)))
    face = number(p.get('face', 1000), 1, 1e9, 'Face value')
    settle = iso(p.get('settlement_date'), 'Settlement')
    maturity = iso(p.get('maturity_date'), 'Maturity')
    days = (maturity-settle).days
    if not 1 <= days <= 366:
        raise ValueError('Bill term must be 1–366 days.')
    mode = p.get('input_mode', 'discount')
    if mode == 'discount':
        discount = number(p.get('discount_rate', 4.515), -20, 50, 'Bank discount rate (%)')/100
        price = 100*(1-discount*days/360)
    elif mode == 'price':
        price = number(p.get('price', 99), .01, 120, 'Price per 100')
        discount = (1-price/100)*360/days
    else:
        raise ValueError('Bill input mode must be discount or price.')
    annual_log=math.log(100/price)*365/days
    if annual_log>700:
        raise ValueError('Annualized yield exceeds the supported numerical range.')
    return dict(days=days, price=price, cost=face*price/100,
                interest=face*(1-price/100), holding_return=100/price-1,
                discount_rate=discount, simple_investment_yield=(100/price-1)*365/days,
                effective_annual_yield=math.expm1(annual_log),
                note='Simple investment yield uses Actual/365. For bills over 182 days it is not Treasury’s coupon-equivalent investment rate.')
