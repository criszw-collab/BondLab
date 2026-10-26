"""BondLab mathematics. Rates are decimals unless a field explicitly says pct."""
import csv
import io
import math
import random
import statistics
from datetime import date

MATURITIES = [1, 2, 3, 5, 7, 10]


def number(value, low, high, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a number, not a boolean.')
    x = float(value)
    if not math.isfinite(x) or not low <= x <= high:
        raise ValueError(f'{name} must be between {low} and {high}.')
    return x


def bond_price(face, coupon, years, y, frequency=2):
    """Full price on a coupon date; regular periods only; nominal annual YTM."""
    if face <= 0 or frequency not in (1, 2, 4) or years <= 0 or y <= -frequency:
        raise ValueError('Invalid bond terms.')
    periods = years * frequency
    if abs(periods - round(periods)) > 1e-8:
        raise ValueError('Maturity must contain a whole number of coupon periods.')
    n = round(periods)
    c = face * coupon / frequency
    return sum((c + (face if k == n else 0)) / (1 + y / frequency)**k
               for k in range(1, n + 1))


def yield_to_maturity(face, coupon, years, price, frequency=2):
    if price <= 0 or coupon < 0:
        raise ValueError('Price must be positive and coupon nonnegative.')
    lo, hi = -0.9 * frequency, 1.0
    while bond_price(face, coupon, years, hi, frequency) > price:
        hi *= 2
        if hi > 1e6:
            raise ValueError('Cannot bracket yield for these inputs.')
    for _ in range(160):
        mid = (lo + hi) / 2
        if bond_price(face, coupon, years, mid, frequency) > price:
            lo = mid
        else:
            hi = mid
    result = (lo + hi) / 2
    if abs(bond_price(face, coupon, years, result, frequency) - price) > max(1e-5, price*1e-8):
        raise ValueError('Yield outside supported range.')
    return result


def calculator(p):
    face = number(p.get('face', 1000), 1, 1e9, 'Face value')
    coupon = number(p.get('coupon', 5), 0, 50, 'Coupon (%)') / 100
    years = number(p.get('years', 5), 0.25, 50, 'Years')
    f = number(p.get('frequency', 2), 1, 4, 'Frequency')
    if f not in (1, 2, 4):
        raise ValueError('Frequency must be 1, 2 or 4.')
    f = int(f)
    y = number(p.get('yield', 6), -20, 100, 'Yield (%)') / 100
    price = bond_price(face, coupon, years, y, f)
    market_price = number(p.get('market_price', price), 0.01, 1e10, 'Market price')
    ytm = yield_to_maturity(face, coupon, years, market_price, f)
    n = round(years*f)
    flows = [(k/f, face*coupon/f + (face if k == n else 0)) for k in range(1, n+1)]
    macaulay = sum(t*cf/(1+y/f)**(t*f) for t, cf in flows)/price
    modified = macaulay/(1+y/f)
    convexity = sum(cf*k*(k+1)/(f*f)/(1+y/f)**(k+2)
                    for k, (_, cf) in enumerate(flows, 1))/price
    shock = number(p.get('shock', -1), -10, 10, 'Yield shock (percentage points)')/100
    shocked = bond_price(face, coupon, years, y+shock, f)
    scenarios = []
    for bps in [-200, -100, -50, 0, 50, 100, 200]:
        value = bond_price(face, coupon, years, y+bps/10000, f)
        scenarios.append({'shock_bps': bps, 'price': value, 'change': value/price-1})
    return dict(price=price, ytm=ytm, annual_coupon=face*coupon,
                current_yield=face*coupon/market_price, macaulay=macaulay,
                modified=modified, convexity=convexity,
                dv01=price*modified*0.0001, shocked_price=shocked,
                shock_return=shocked/price-1,
                duration_estimate=-modified*shock,
                convexity_estimate=-modified*shock+0.5*convexity*shock*shock,
                scenarios=scenarios,
                cashflows=[{'year': t, 'cashflow': cf} for t, cf in flows])


def curve_yield(curve, maturity):
    """Linear interpolation of continuously compounded zero yields; no extrapolation."""
    knots = sorted(curve)
    if maturity < knots[0]-1e-9 or maturity > knots[-1]+1e-9:
        raise ValueError('Maturity is outside the supplied zero curve.')
    for t in knots:
        if abs(t-maturity) < 1e-9:
            return curve[t]
    for left, right in zip(knots, knots[1:]):
        if left < maturity < right:
            weight = (maturity-left)/(right-left)
            return curve[left]*(1-weight)+curve[right]*weight
    raise ValueError('Cannot interpolate maturity.')


def zero_return(curve_now, curve_next, maturity, horizon):
    if horizon <= 0 or horizon >= maturity:
        raise ValueError('Horizon must be positive and shorter than maturity.')
    return math.expm1(curve_yield(curve_now, maturity)*maturity
                     - curve_yield(curve_next, maturity-horizon)*(maturity-horizon))


def carry_table(curve, horizon=1/12, maturities=MATURITIES):
    rows = []
    for maturity in maturities:
        carry = zero_return(curve, curve, maturity, horizon)
        aging = math.expm1(curve_yield(curve, maturity)*horizon)
        rows.append(dict(maturity=maturity, zero_yield=curve_yield(curve, maturity),
                         horizon_return=carry, annualized_carry=math.expm1(math.log1p(carry)/horizon),
                         constant_yield_aging=aging, roll_down=carry-aging,
                         duration=maturity, carry_per_duration=carry/maturity))
    return rows


def parse_curves(text):
    """CSV Date,y0.5,y1,... with percent continuously compounded zero yields.

    Also accepts the Federal Reserve GSW CSV with metadata before its header.
    Invalid/incomplete rows are dropped and reported; latest observation per month wins.
    """
    if len(text) > 20_000_000:
        raise ValueError('CSV exceeds 20 MB.')
    lines = text.lstrip('\ufeff').splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.split(',')[0].strip().lower() == 'date'), None)
    if start is None:
        raise ValueError('CSV needs a Date column as its first column.')
    reader = csv.DictReader(io.StringIO('\n'.join(lines[start:])))
    fields = {k.strip(): k for k in reader.fieldnames}
    fed = 'SVENY01' in fields
    if fed:
        # Fed SVENY values are continuously compounded zero yields, in percent.
        mapping = {float(i): fields[f'SVENY{i:02}'] for i in range(1, 11)
                   if f'SVENY{i:02}' in fields}
    else:
        mapping = {}
        for key, original in fields.items():
            if key.startswith('y'):
                try:
                    t = float(key[1:])
                    if t > 0:
                        mapping[t] = original
                except ValueError:
                    pass
    if len(mapping) < 2 or min(mapping) > 1 or max(mapping) < 10:
        raise ValueError('Curve must span at least 1–10 years and contain two or more tenor columns.')
    records, dropped = {}, 0
    for row in reader:
        try:
            d = date.fromisoformat(row[fields.get('Date', reader.fieldnames[0])].strip())
            curve = {t: number(row[key], -20, 50, 'Zero yield (%)')/100 for t, key in mapping.items()}
            # Fed data starts at one year. Add an explicit flat short-end approximation.
            if min(curve) > 0.5:
                curve[0.5] = curve[min(curve)]
            if d in records:
                raise ValueError('Duplicate observation date in CSV.')
            records[d] = curve
        except (ValueError, TypeError, KeyError):
            dropped += 1
    monthly = {}
    for d in sorted(records):
        monthly[(d.year, d.month)] = {'date': d.isoformat(), 'curve': records[d]}
    result = [monthly[key] for key in sorted(monthly)]
    if not result:
        raise ValueError('No complete valid curve rows were found.')
    return result, dict(valid_daily_rows=len(records), monthly_rows=len(result), dropped_rows=dropped,
                        source='Federal Reserve GSW' if fed else 'Uploaded CSV',
                        short_end='Flat 0.5–1 year segment added when shortest tenor exceeds 0.5 year.')


def demo_curves():
    """Seeded artificial curves, deliberately not historical market data."""
    rng = random.Random(2026)
    rows = []
    level = 0.035
    for k in range(240):
        year, month = 2006+k//12, 1+k%12
        level = max(-0.005, min(0.10, level+0.08*(0.035-level)+rng.gauss(0, 0.0025)))
        slope = 0.01*math.sin(k/25)+0.003
        curve = {t: level+slope*(1-math.exp(-t/4))+0.002*math.sin(k/19)*math.exp(-t/6)
                 for t in [0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30]}
        rows.append({'date': date(year, month, 28).isoformat(), 'curve': curve})
    return rows


def metrics(returns, cash, intervals):
    wealth, peak, worst = 1.0, 1.0, 0.0
    for r in returns:
        wealth *= 1+r
        peak = max(peak, wealth)
        worst = min(worst, wealth/peak-1)
    years = sum(intervals)
    # Scale unequal monthly intervals to a common monthly basis for vol/Sharpe.
    normalized = [math.expm1(math.log1p(r)/(12*h)) for r, h in zip(returns, intervals)]
    excess = [r-c for r, c in zip(returns, cash)]
    excess_normalized = [x/(12*h) for x, h in zip(excess, intervals)]
    vol = statistics.stdev(normalized)*math.sqrt(12) if len(returns)>1 else 0
    sd = statistics.stdev(excess_normalized) if len(returns)>1 else 0
    return dict(total_return=wealth-1, cagr=wealth**(1/years)-1,
                volatility=vol, max_drawdown=worst,
                sharpe=statistics.mean(excess_normalized)/sd*math.sqrt(12) if sd>1e-12 else None)


def backtest(records, cost_bps=5, max_maturity=10, score='carry'):
    cost_bps = number(cost_bps, 0, 100, 'Round-trip cost (bps)')
    max_maturity = number(max_maturity, 2, 10, 'Maximum maturity')
    if score not in ('carry', 'duration_adjusted'):
        raise ValueError('Unknown ranking method.')
    maturities = [t for t in MATURITIES if 2 <= t <= max_maturity]
    if len(records) < 13:
        raise ValueError('At least 13 monthly curves are required.')
    strategy, equal, cash, intervals, trades = [], [], [], [], []
    wealth = {'strategy': 1.0, 'equal_weight': 1.0, 'cash_proxy': 1.0}
    equity = [dict(date=records[0]['date'], **wealth)]
    for current, following in zip(records, records[1:]):
        d0, d1 = date.fromisoformat(current['date']), date.fromisoformat(following['date'])
        if (d1.year-d0.year)*12+d1.month-d0.month != 1:
            raise ValueError('Missing calendar month in data. Supply consecutive monthly observations.')
        horizon = (d1-d0).days/365.25
        # Ranking uses only the current curve and a fixed one-month horizon.
        table = carry_table(current['curve'], 1/12, maturities)
        key = 'horizon_return' if score == 'carry' else 'carry_per_duration'
        selected = max(table, key=lambda row: row[key])
        realized = {t: zero_return(current['curve'], following['curve'], t, horizon) for t in maturities}
        cost = cost_bps/10000
        sr = realized[selected['maturity']]-cost
        er = statistics.mean(realized.values())-cost
        cr = math.expm1(curve_yield(current['curve'], 1)*horizon)
        strategy.append(sr)
        equal.append(er)
        cash.append(cr)
        intervals.append(horizon)
        for name, ret in [('strategy', sr), ('equal_weight', er), ('cash_proxy', cr)]:
            wealth[name] *= 1+ret
        equity.append(dict(date=following['date'], **wealth))
        trades.append(dict(signal_date=current['date'], end_date=following['date'],
                           maturity=selected['maturity'], signal_carry=selected['horizon_return'],
                           gross_return=realized[selected['maturity']], net_return=sr,
                           benchmark_return=er, cash_proxy_return=cr, cost=cost))
    return dict(metrics={name: metrics(rs, cash, intervals) for name, rs in
                         [('strategy', strategy), ('equal_weight', equal), ('cash_proxy', cash)]},
                equity=equity, trades=trades, periods=len(trades),
                latest_carry=carry_table(records[-1]['curve'], 1/12, maturities))
