# BondLab Analytics

**Created by Crispen Chachengwa — Applied AI and ML Specialist**  
Email: [cris2214zw@gmail.com](mailto:cris2214zw@gmail.com) · GitHub: [criszw-collab](https://github.com/criszw-collab)

[Quick start](QUICKSTART.md) · [How to use the app](USER_GUIDE.md) · [Validation evidence](VALIDATION.md)

A local Python application for dated bond valuation, portfolio risk, Treasury bills and reproducible carry research. The engine is substantially upgraded and numerically validated within the scope below. This release is not certified as a public multiuser commercial service.

## Get the code

On the repository page, choose **Code → Download ZIP** and extract it, or clone the repository with Git. Open the extracted repository folder containing `app.py`. This publishes source code; the Python application must still be started locally. Opening `index.html` directly or enabling GitHub Pages will not run the Python API.

## Windows setup

Requires 64-bit Python 3.10 or later and internet for the initial package installation.

1. Extract the ZIP. Open the `BondLab` folder.
2. Double-click `Setup_BondLab.bat` once. Wait for installation to finish successfully.
3. Double-click `Start_BondLab.bat`. The app opens at http://127.0.0.1:8000.
4. Keep the terminal open; stop with Ctrl+C.

Manual PowerShell alternative:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

For a different port: `.\.venv\Scripts\python.exe app.py --port 8001`.

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

An internet connection is unnecessary for valuation, portfolio calculations, or backtesting the included frozen real-data snapshot after installation. The live Federal Reserve download requires internet. No paid data key or brokerage account is required.

## New features

- **Dated bond engine:** explicit accrual start, maturity and settlement; clean/dirty prices; accrued interest; yield from price; dated cash flows; three day counts and 1/2/4 coupons per year.
- **Consistent risk:** modified duration, convexity, analytic dollar DV01, finite-shock DV01, exact yield-shock P&L and duration/convexity estimates all use the same yield and dirty-price basis.
- **Treasury auction mode:** separate regular-period auction convention, validated against published original and reopening auction prices. It is intentionally distinct from conventional compound YTM.
- **Portfolio:** up to 100 positions, aggregate settlement value and accrued interest, dollar DV01, value-weighted duration and convexity, parallel-yield scenarios and combined monthly cash receipts.
- **Treasury bills:** bank-discount pricing, holding return, simple investment yield, effective annual yield and maturity proceeds.
- **Research:** carry/roll-down, frozen real GSW data from 2010–2025, latest-data download, input hashes, cost sensitivity, yearly returns and full JSON/CSV exports.
- **Traceability:** SQLite input/output audit history, timestamps, engine versions, SHA-256 input/output hashes, retained raw curve snapshots and saved-run export.
- **Application hardening:** FastAPI/Uvicorn, loopback-only launcher, local-host/origin checks, random per-process request token, content-type and body-size checks, request rate limit, content-security policy, escaped display text and explicit error handling.
- **Validation screen:** actual test results, source-price comparisons and independent-engine error measures.

## Accuracy: what was validated

Read `VALIDATION.md` and `validation/results.json` for the exact measured results. Run `validate.py` to reproduce.

- 45 automated test methods at release, including 1,000 independent Python-oracle price/accrual comparisons and 300 price/yield round trips.
- 4 official Treasury auction fixtures: original 10-year note, reopened 10-year note, reopened 30-year bond and a 28-day bill. Source URLs and SHA-256 manifests are included. Run `python prepare_validation_data.py` to download the original official PDFs locally.
- Analytical risk measures checked against finite differences; month-end/leap dates, invalid terms, clean/dirty identities, parallel calls, portfolio scaling and API/audit paths tested.
- Every monthly carry-strategy return in the 191-period real-data backtest checked with a separate 50-digit Decimal calculation.

Tiny numerical differences demonstrate agreement under the selected conventions. They do not demonstrate that fitted curve prices are executable or that all security types are covered.

## Important pricing conventions

**Quote units:** clean price and dirty price are per $100 principal. Face value means the amount of principal owned. For $1,000 principal, a quote of 100.114150 means $1,001.14150 before accrued interest.

**Settlement:** enter the actual date; there is no automatic T+1/holiday calculation. Coupon-date settlement excludes the coupon payable on that date. Coupon payment dates remain contractual and unadjusted.

**Original dated date:** use the regular original accrual date, not a reopening's settlement/issue date. Irregular coupon schedules are rejected.

**Day counts:** Actual/Actual Bond (ICMA); 30/360 Bond Basis; Actual/365 Fixed. The engine uses the selected day count for coupon accrual and yield calculations. Actual/365 coupon amounts can vary with period length; inspect the dated cash flows rather than assuming every payment is the same.

**Compound mode:** QuantLib periodic-compound nominal annual YTM with the chosen coupon frequency and day count. Analytical risk comes from the same QuantLib price/yield convention.

**Treasury auction mode:** regular-period semiannual Actual/Actual, implementing 31 CFR 356 Appendix B III.D. The first partial period is discounted simply and later full periods periodically. This can differ from compound YTM at fractional-period settlement. Use this mode to reproduce auction prices; do not reuse a yield quoted under a different convention without conversion.

**Price-input mode:** clean price is authoritative and yield is solved numerically. All output risk then uses that solved yield. Yield-input mode uses the entered yield and ignores the price field.

**Bill rates:** bank discount uses Actual/360; displayed simple investment yield uses Actual/365. For bills longer than 182 days, this simple rate is not Treasury's coupon-equivalent investment rate; the interface labels the distinction.

## Instrument coverage limits

Regular noncallable fixed-rate bullet bonds only. No odd/stub coupons, ex-coupon entitlement, holiday-adjusted payments, embedded options, floating coupons, inflation indexation, amortization, defaults, taxes or transaction-cost-inclusive bond YTM. These features require security-specific conventions and separate validation before support can be claimed.

Portfolio duration/convexity are dirty-value weighted. Portfolio DV01 and scenario P&L are dollar sums. Each position must share a settlement date. No average portfolio YTM is presented. Portfolio coupon income is a nominal annual rate calculation, while the dated receipts schedule shows actual contractual amounts.

## Research basis and data

- Koijen, Moskowitz, Pedersen & Vrugt (2018), **Carry**, *Journal of Financial Economics*, 127(2), 197–225. https://doi.org/10.1016/j.jfineco.2017.11.002 . Summary: https://www.aqr.com/Insights/Research/Journal-Article/Carry
- Gürkaynak, Sack & Wright (2007), **The U.S. Treasury Yield Curve: 1961 to the Present**, *Journal of Monetary Economics*, 54, 2291–2304. https://www.federalreserve.gov/data/nominal-yield-curve.htm
- Treasury auction formulas: https://www.treasurydirect.gov/files/laws-and-regulations/auction-regulations-uoc/31-cfr-part-356.pdf
- QuantLib documentation: https://www.quantlib.org/docs.shtml

The strategy is an educational long-only maturity-selection adaptation of Carry, not a replication of the paper's global long/short portfolios. Carry-per-duration is an app extension. Cochrane–Piazzesi regression forecasting is not implemented.

**Curve units:** continuously compounded annual zero yields in percent. Example CSV:

```csv
Date,y1,y2,y3,y5,y7,y10
2024-01-31,4.6,4.3,4.2,4.1,4.2,4.3
2024-02-29,4.7,4.4,4.3,4.2,4.3,4.4
```

Supply at least 13 consecutive monthly observations with a curve spanning 1–10 years. These two example rows only illustrate the schema. Raw Fed GSW CSV is supported. Par yields or coupon rates cannot be substituted for zero yields. Invalid/incomplete rows are dropped and counted; first valid row wins for duplicate dates. Fed parsing requires SVENY01–SVENY10 only, avoiding unnecessary loss of valid observations missing longer tenors.

**Backtest:** last available complete observation each month; missing calendar months trigger an error. Rank eligible 2/3/5/7/10-year bonds from the current curve using one-month unchanged-curve carry. Hold to the following curve with elapsed time Actual/365.25. Close and reopen the full portfolio monthly; deduct the selected round-trip cost each period from strategy and equal-weight returns. There is no predictive model fitting or hidden parameter optimization.

**Limits:** hypothetical zeros and fitted observation-date execution, linear interpolation, no execution delay or liquidity model beyond fixed costs, no leverage/tax/default model. The cash proxy compounds the current one-year zero yield; it is not a realized bill return. Current-vintage source data can be revised. Maturity exposure changes interest-rate risk. Subperiod comparisons are retrospective, not a preregistered holdout experiment.

CAGR uses elapsed calendar years; volatility normalizes each observation to one month and annualizes by sqrt(12); excess Sharpe similarly normalizes simple excess return over the cash proxy. Maximum drawdown includes starting wealth. Annual return tables assign a holding interval to its ending calendar year.

## Reproduce validation

Install development requirements into the same virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe validate.py
```

For individual tests: `python -m unittest discover -s tests -v`.

Optional browser workflow verification: install Playwright with `npm install --no-save playwright`, then `npx playwright install chromium` and `node tests/browser_smoke.cjs`. Activate the Python virtual environment first, or set `BONDLAB_PYTHON` to its interpreter. Then run `python validate.py` to incorporate the browser evidence. Browser tests write temporary screenshots to the operating-system temp directory.

`prepare_validation_data.py` explicitly downloads a new source vintage and overwrites the bundled validation snapshot and official source PDFs. Ordinary app startup does not do this. After refreshing, rerun `validate.py`. A different vintage can produce different historical estimates.

## Storage, backup and operations

Local run records: `data/bondlab.sqlite`; raw inputs: `data/snapshots/`. Override the runtime folder with `BONDLAB_DATA_DIR`. Back up the data folder while the app is stopped. Export JSON for portable input/output records. SHA-256 detects differences but does not make the audit log tamper-proof or digitally signed. Restarting the server changes its request token; reload browser tabs afterward.

This is a **local single-user edition**. The launcher deliberately binds to 127.0.0.1. Public hosting is a separate engineering task: account isolation, service authentication, authorization, HTTPS, monitoring, restore drills, deployment-specific penetration/load testing and data rights. The local request token is not a multiuser authentication system. No trading, brokerage connection or investment advice automation is included.

## Main files

- `dated_bonds.py`: supported bond, bill and portfolio analytics.
- `engine.py`: carry/backtest and legacy simple-pricing regression helpers; the UI uses `dated_bonds.py` for bond valuation.
- `data_service.py`: immutable curve snapshots, provenance, strategy sensitivity/yearly results.
- `app.py`: API, local request checks and audit records.
- `index.html`: local interface; no external JavaScript/CDN required.
- `validate.py`, `tests/`, `validation/`: reproducible checks and evidence.

## 2.0.1 Windows compatibility fix

Database connections now close deterministically after successful and failed operations, preventing leaked SQLite/WAL handles during Windows test cleanup. Text files are read/written explicitly as UTF-8. Validation prints failed-test tracebacks directly. Two regression tests verify connection closure. This fixes a confirmed handle-management bug; the original Windows failure requires its test log for exact attribution.
