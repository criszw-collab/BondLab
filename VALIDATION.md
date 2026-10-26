# BondLab 2.0 validation report

Status: **PASS**. Generated 2026-10-26T19:32:49.360681+00:00.

Engine 2.0.1; QuantLib 1.44; Python 3.12.14.

45 test methods passed.

## Independent numerical checks

- 1,000 seeded independent Python-oracle comparisons; maximum clean-price difference **2.67164068646e-12 per $100** (tolerance 1e-8).
- Maximum accrued-interest difference: 1.15463194561e-14 per $100.
- 300 price/yield round trips; yield tolerance 1e-9 (decimal yield), price residual tolerance 1e-7 per $100.
- Analytical duration and convexity checked with finite differences for both yield conventions.
- Month-end, leap-day, invalid-input, concurrent-call, portfolio-scaling and API/audit checks.

## Official Treasury evidence

| Auction | Published price | Calculated price | Absolute difference |
|---|---:|---:|---:|
| 91282CLW9_original | 99.220075 | 99.220074833 | 1.67e-07 |
| 91282CLW9_reopening | 100.114150 | 100.114149683 | 3.17e-07 |
| 912810UE6_reopening | 93.557438 | 93.557437645 | 3.55e-07 |
| 912797MN4_bill | 99.648833 | 99.648833333 | 3.33e-07 |

All prices are per $100 face. Tolerance 0.00000051 reflects six-decimal publication rounding. Accrued interest on the two reopenings is checked separately to 0.0000051 dollars per $1,000. Source URLs and SHA-256 manifests are included. Official PDFs can be downloaded locally with `python prepare_validation_data.py`; they are not distributed in this repository.

### Convention finding

The December 2024 reopening produces 100.114149683 under the Treasury auction formula, versus approximately 100.117266263 under conventional fractional-period compound discounting. These are distinct conventions. The app labels them separately and reproduces the auction with its designated mode.

## Real-data strategy evaluation

Federal Reserve GSW month-end snapshot: 2010-01-29 to 2025-12-31; 191 holding periods. Fixed parameters: highest raw one-month carry, 2/3/5/7/10-year choices, 5 bps monthly round-trip cost. No parameter optimization was performed.

| Portfolio | CAGR | Annual volatility | Maximum drawdown | Excess Sharpe |
|---|---:|---:|---:|---:|
| strategy | 3.251% | 7.922% | -24.943% | 0.260 |
| equal_weight | 1.835% | 4.287% | -16.422% | 0.097 |
| cash_proxy | 1.549% | 0.497% | 0.000% | N/A |

Every strategy holding-period return was independently recomputed with 50-digit Decimal discount factors. Maximum return difference: 1.18e-16; final wealth difference: 2.66e-15.

Subperiod results and cost sensitivity are in real_backtest_results.json / results.json. These are retrospective checks, not a preregistered experiment or evidence of future profits.

## Scope and unresolved production work

Verified scope: regular fixed-rate bullet bonds, contractual unadjusted dates, three day counts, periodic compound yield, regular-period U.S. Treasury auction pricing, and Treasury bill bank-discount pricing. Irregular schedules are rejected.

Not covered: holiday-adjusted payments, settlement-lag automation, odd coupons, ex-coupon markets, credit/default valuation, callable/putable bonds, amortizers, TIPS, FRNs, taxes, broker execution, or live market quote validation. Long-bill simple investment yield is explicitly not labeled Treasury coupon-equivalent investment yield.

The strategy uses fitted zero curves rather than executable quotes; fixed costs, no trading latency, a one-year-yield cash proxy, and current-vintage revised data. Different maturities carry different duration risk.

PASS: 16 Chromium 153.0.8010.0 workflow checks, including exports and mobile viewport; desktop and mobile screenshots visually inspected.

The server is designed for local single-user use. Public commercial hosting requires separately validated account isolation, operations, security, backups and data rights. These tests are not independent external certification.

## Reproduce

Install requirements-dev.txt, then run `python validate.py`. Refreshing data is a separate explicit command: `python prepare_validation_data.py`; this changes the data vintage.
