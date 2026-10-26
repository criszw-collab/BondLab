import copy
import json
import random
import unittest
from datetime import date,timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dated_bonds import value_bond,value_bill,value_portfolio
from reference_pricer import reference,shifted

FIXTURES=json.loads((Path(__file__).parent/'treasury_fixtures.json').read_text(encoding='utf-8'))
BASE=FIXTURES[1]['input']


class DatedBondTests(unittest.TestCase):
    def test_official_treasury_prices(self):
        for case in FIXTURES:
            with self.subTest(case=case['id']):
                if case['type']=='bond':
                    r=value_bond(case['input'])
                    self.assertLessEqual(abs(r['clean_price']-case['expected_clean']),.00000051)
                    self.assertLessEqual(abs(r['accrued_value']-case['expected_accrued_1000']),.0000051)
                else:
                    r=value_bill(case['input'])
                    self.assertLessEqual(abs(r['price']-case['expected_price']),.00000051)
                    self.assertLessEqual(abs(r['simple_investment_yield']*100-case['expected_investment_pct']),.00051)

    def test_1000_independent_price_checks(self):
        rng=random.Random(1703)
        for k in range(1000):
            start=date(rng.randrange(1990,2020),rng.randrange(1,13),15)
            years=rng.randrange(1,41)
            end=date(start.year+years,start.month,15)
            settle=start+timedelta(days=rng.randrange((end-start).days))
            freq=rng.choice([1,2,4])
            kind=rng.choice(['actual_actual','30_360','actual_365'])
            convention='compound'
            if k%4==0:
                freq,kind,convention=2,'actual_actual','treasury_auction'
            p=dict(dated_date=start.isoformat(),maturity_date=end.isoformat(),settlement_date=settle.isoformat(),
                   coupon=rng.uniform(0,12),frequency=freq,day_count=kind,convention=convention,
                   **{'yield':rng.uniform(-2,18)})
            a=value_bond(p);b=reference(p,p['yield']/100)
            self.assertLess(abs(a['clean_price']-b['clean_price']),1e-8,(k,p,a['clean_price'],b))
            self.assertLess(abs(a['accrued_per_100']-b['accrued_per_100']),1e-8)

    def test_end_of_month_and_leap_dates(self):
        for day in ['2024-02-29','2024-03-01','2024-08-30','2024-08-31']:
            p=dict(dated_date='2020-02-29',maturity_date='2030-02-28',settlement_date=day,
                   coupon=5,frequency=2,day_count='actual_actual',end_of_month=True,**{'yield':4})
            r=value_bond(p);b=reference(p,.04)
            self.assertAlmostEqual(r['clean_price'],b['clean_price'],places=9)

    def test_solver_300_roundtrips(self):
        rng=random.Random(123)
        for k in range(300):
            p=dict(BASE,convention='compound' if k%2 else 'treasury_auction',coupon=rng.uniform(0,12),
                   **{'yield':rng.uniform(-1,20)})
            a=value_bond(p)
            b=value_bond(dict(p,input_mode='price',clean_price=a['clean_price']))
            self.assertLess(abs(a['ytm']-b['ytm']),1e-9)
            self.assertLess(abs(b['yield_solver_residual_per_100']),1e-7)

    def test_risk_derivatives(self):
        for convention in ['compound','treasury_auction']:
            p=dict(BASE,convention=convention)
            a=value_bond(p)
            h=1e-5
            left=value_bond(dict(p,**{'yield':p['yield']-h*100}))['dirty_price']
            right=value_bond(dict(p,**{'yield':p['yield']+h*100}))['dirty_price']
            dirty=a['dirty_price']
            self.assertAlmostEqual(a['modified_duration'],-(right-left)/(2*h*dirty),places=6)
            self.assertAlmostEqual(a['convexity'],(right-2*dirty+left)/(h*h*dirty),places=4)

    def test_reopening_conventions_are_distinct(self):
        a=value_bond(BASE)
        b=value_bond(dict(BASE,convention='compound'))
        self.assertGreater(abs(a['clean_price']-b['clean_price']),.003)

    def test_clean_dirty_and_cashflow_identity(self):
        r=value_bond(BASE)
        self.assertAlmostEqual(r['dirty_price'],r['clean_price']+r['accrued_per_100'])
        self.assertAlmostEqual(sum(c['amount'] for c in r['cashflows']),1425)
        self.assertAlmostEqual(r['settlement_value'],r['dirty_price']*10)

    def test_zero_coupon(self):
        r=value_bond(dict(BASE,coupon=0,convention='compound'))
        self.assertEqual(r['accrued_value'],0)
        self.assertAlmostEqual(sum(c['amount'] for c in r['cashflows']),1000)

    def test_portfolio_scaling(self):
        a=value_bond(BASE)
        p=value_portfolio({'bonds':[BASE,dict(BASE,face=2000)]})
        self.assertAlmostEqual(p['settlement_value'],a['settlement_value']*3)
        self.assertAlmostEqual(p['dv01'],a['dv01']*3)
        self.assertAlmostEqual(p['weighted_duration'],a['modified_duration'])

    def test_invalid_inputs(self):
        for change in [dict(face=float('nan')),dict(coupon=-1),dict(frequency=3),
                       dict(settlement_date='2050-01-01'),dict(day_count='unknown'),
                       dict(dated_date='2024-11-16'),dict(end_of_month='yes'),
                       dict(convention='callable'),dict(unknown_field=1),dict(input_mode='other')]:
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):
                value_bond(dict(BASE,**change))

    def test_parallel_isolation(self):
        inputs=[dict(BASE,**{'yield':3+i/10}) for i in range(20)]
        expected=[value_bond(p)['clean_price'] for p in inputs]
        with ThreadPoolExecutor(max_workers=8) as ex:
            actual=[r['clean_price'] for r in ex.map(value_bond,inputs)]
        self.assertEqual(expected,actual)

    def test_bill_roundtrip(self):
        p=FIXTURES[-1]['input'];a=value_bill(p)
        b=value_bill(dict(p,input_mode='price',price=a['price']))
        self.assertAlmostEqual(a['discount_rate'],b['discount_rate'])

    def test_boolean_numeric_input_rejected(self):
        with self.assertRaises(ValueError):value_bond(dict(BASE,face=True))

    def test_bill_out_of_range_annualization(self):
        with self.assertRaises(ValueError):
            value_bill(dict(face=1000,settlement_date='2025-01-01',maturity_date='2025-01-02',input_mode='price',price=.01))


if __name__=='__main__':unittest.main()
