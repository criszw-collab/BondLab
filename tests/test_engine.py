import unittest
import math
from engine import (bond_price, yield_to_maturity, calculator, curve_yield,
                    zero_return, carry_table, demo_curves, backtest, parse_curves, metrics)


class BondTests(unittest.TestCase):
    def test_par(self):
        self.assertAlmostEqual(bond_price(1000, .05, 10, .05), 1000)

    def test_published_example(self):
        self.assertAlmostEqual(bond_price(1000, .05, 2, .06, 1), 981.6660733357, places=7)

    def test_ytm_roundtrip(self):
        for y in [-.02, 0, .04, .17]:
            price = bond_price(1000, .03, 10, y)
            self.assertAlmostEqual(yield_to_maturity(1000, .03, 10, price), y, places=10)

    def test_zero_coupon(self):
        self.assertAlmostEqual(bond_price(1000, 0, 5, .04, 1), 1000/1.04**5)

    def test_duration_and_convexity_numerical(self):
        d = calculator({'years': 10, 'yield': 4})
        p, h = d['price'], 1e-5
        minus = bond_price(1000, .05, 10, .04-h)
        plus = bond_price(1000, .05, 10, .04+h)
        self.assertAlmostEqual(d['modified'], -(plus-minus)/(2*h*p), places=6)
        self.assertAlmostEqual(d['convexity'], (plus-2*p+minus)/(h*h*p), places=4)

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            bond_price(1000, .05, 1.25, .04, 2)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            calculator({'face': float('nan')})


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.flat = {.5: .04, 1: .04, 2: .04, 3: .04, 5: .04, 7: .04, 10: .04}

    def test_interpolation(self):
        self.assertAlmostEqual(curve_yield({1: .03, 3: .05}, 2), .04)

    def test_flat_carry(self):
        expected = math.expm1(.04/12)
        self.assertAlmostEqual(zero_return(self.flat, self.flat, 5, 1/12), expected)
        for r in carry_table(self.flat):
            self.assertAlmostEqual(r['roll_down'], 0)

    def test_upward_curve_roll(self):
        curve = {.5: .02, 1: .025, 2: .03, 3: .035, 5: .04, 7: .045, 10: .05}
        self.assertTrue(all(r['roll_down'] > 0 for r in carry_table(curve, maturities=[2, 5, 10])))

    def test_exact_rate_shock(self):
        next_curve = {t: z+.01 for t, z in self.flat.items()}
        self.assertAlmostEqual(zero_return(self.flat, next_curve, 5, 1/12),
                               math.expm1(.04*5-.05*(5-1/12)))

    def test_costs_lower_return(self):
        a, b = backtest(demo_curves(), 0), backtest(demo_curves(), 10)
        self.assertLess(b['metrics']['strategy']['cagr'], a['metrics']['strategy']['cagr'])
        self.assertAlmostEqual(a['trades'][0]['net_return']-b['trades'][0]['net_return'], .001)

    def test_future_changes_do_not_change_signal(self):
        rows = demo_curves()[:14]
        a = backtest(rows)
        changed = [dict(r) for r in rows]
        changed[1] = dict(changed[1], curve={t: z+.02 for t,z in changed[1]['curve'].items()})
        b = backtest(changed)
        self.assertEqual(a['trades'][0]['maturity'], b['trades'][0]['maturity'])
        self.assertEqual(a['trades'][0]['signal_carry'], b['trades'][0]['signal_carry'])
        self.assertNotEqual(a['trades'][0]['net_return'], b['trades'][0]['net_return'])

    def test_missing_month_rejected(self):
        rows = demo_curves()[:15]
        del rows[3]
        with self.assertRaises(ValueError):
            backtest(rows)

    def test_csv_units_and_month_end(self):
        text = 'Date,y1,y2,y10\n2020-01-10,4,5,6\n2020-01-31,5,6,7\n2020-02-28,NA,6,7\n'
        rows, meta = parse_curves(text)
        self.assertEqual(rows[0]['date'], '2020-01-31')
        self.assertAlmostEqual(rows[0]['curve'][1], .05)
        self.assertAlmostEqual(rows[0]['curve'][.5], .05)
        self.assertEqual(meta['dropped_rows'], 1)

    def test_fed_header(self):
        rows, meta = parse_curves('metadata\nDate,SVENY01,SVENY02,SVENY10\n2020-01-31,4,5,6\n')
        self.assertEqual(meta['source'], 'Federal Reserve GSW')
        self.assertAlmostEqual(rows[0]['curve'][10], .06)

    def test_drawdown_from_initial_wealth(self):
        m = metrics([-.1, .05], [0, 0], [1/12, 1/12])
        self.assertAlmostEqual(m['max_drawdown'], -.1)
        self.assertAlmostEqual(m['total_return'], -.055)


if __name__ == '__main__':
    unittest.main()
