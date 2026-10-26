"""Independent Python discounted-cash-flow oracle; no QuantLib imports.

For validation of regular, unadjusted schedules only. Deliberately separate from
the application implementation and discount-factor functions.
"""
import calendar
from datetime import date


def shifted(anchor, months, eom=False):
    n = anchor.year*12+anchor.month-1+months
    year, month = divmod(n,12)
    month += 1
    last = calendar.monthrange(year,month)[1]
    day = last if eom and anchor.day==calendar.monthrange(anchor.year,anchor.month)[1] else min(anchor.day,last)
    return date(year,month,day)


def fraction(a,b,kind,prev=None,nxt=None,f=2):
    if kind=='actual_actual':
        return (b-a).days/(nxt-prev).days/f
    if kind=='actual_365':
        return (b-a).days/365
    d1 = min(a.day,30)
    d2 = 30 if b.day==31 and d1==30 else b.day
    return ((b.year-a.year)*360+(b.month-a.month)*30+d2-d1)/360


def reference(p,y):
    start=date.fromisoformat(p['dated_date']); end=date.fromisoformat(p['maturity_date'])
    s=date.fromisoformat(p['settlement_date']); f=int(p.get('frequency',2))
    c=float(p['coupon'])/100;kind=p.get('day_count','actual_actual')
    schedule=[end]
    k=1
    while schedule[-1]>start:
        schedule.append(shifted(end,-k*(12//f),p.get('end_of_month',False)));k+=1
    schedule=sorted(schedule)
    prev=max(d for d in schedule if d<=s);future=[d for d in schedule if d>s]
    nxt=future[0]
    accrued=100*c*fraction(prev,s,kind,prev,nxt,f)
    elapsed=0;dirty=0
    for k,pay in enumerate(future):
        prior=prev if k==0 else future[k-1]
        amount=100*c*fraction(prior,pay,kind,prior,pay,f)+(100 if pay==end else 0)
        if p.get('convention','compound')=='treasury_auction':
            frac=(nxt-s).days/(nxt-prev).days
            df=(1+y/2)**(-k)/(1+y*frac/2)
        else:
            # Coupon-period remainder, not a fresh 30/360 interval from settlement:
            # BondBasis is not additive across month-end dates such as the 31st.
            period=fraction(prior,pay,kind,prior,pay,f)
            elapsed+=period-fraction(prior,s,kind,prior,pay,f) if k==0 else period
            df=(1+y/f)**(-f*elapsed)
        dirty+=amount*df
    return dict(clean_price=dirty-accrued,dirty_price=dirty,accrued_per_100=accrued)
