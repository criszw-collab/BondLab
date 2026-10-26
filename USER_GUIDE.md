# How to use BondLab

**Crispen Chachengwa — Applied AI and ML Specialist**  
[cris2214zw@gmail.com](mailto:cris2214zw@gmail.com)

BondLab calculates bond values and cash flows, measures interest-rate exposure and evaluates a historical carry rule. It does not place trades. Start it using [QUICKSTART.md](QUICKSTART.md).

## 1. Bond valuation

Use this screen to value a regular fixed-rate bullet bond.

| Input | Meaning |
|---|---|
| Face principal owned | Amount of principal you own, such as $10,000. |
| Coupon | Annual contractual coupon rate, entered as a percentage. |
| Original dated date | Original interest-accrual start date; do not substitute a reopening settlement date. |
| Maturity date | Contractual final repayment date. |
| Settlement date | Actual date at which the purchase settles. |
| Payments/year | Annual, semiannual or quarterly coupon frequency. |
| Day count | The security's applicable accrual/yield convention. |
| Yield convention | Periodic compound YTM, or the separate regular-period U.S. Treasury auction formula. |
| Calculate from | Use a yield to determine price, or use a clean quote to solve for yield. |
| Yield shock | Change in percentage points. `-1` means a one-percentage-point decrease, or -100 basis points. |

In **Yield → price** mode, yield is authoritative and the clean-price input is ignored. In **Clean price → yield** mode, clean price is authoritative and the yield input is ignored.

Prices are quoted per $100 principal. A clean quote of 98 costs $980 for $1,000 principal before accrued interest. The settlement amount adds accrued interest.

### Read the output

- **Clean quote:** price excluding accrued interest.
- **Dirty quote:** clean quote plus accrued interest, per $100 principal.
- **Settlement amount:** dirty quote multiplied by your principal divided by 100.
- **YTM:** the nominal yield under the selected convention, based on promised cash flows; it is not a guaranteed realized return.
- **Modified duration:** approximate percentage sensitivity to a one-percentage-point yield move.
- **DV01:** approximate dollar sensitivity to a one-basis-point yield move.
- **Convexity:** curvature used to improve the duration approximation.
- **Yield-shock table:** exact immediate repricing of the same remaining cash flows under specified yield changes.
- **Dated cash flows:** contractual coupon and principal payments after settlement.

Try changing principal from $1,000 to $10,000. Dollar values scale by ten; quoted price and yield do not.

Use **Export full analysis JSON** to retain inputs, results and a run ID. Use **Export cash flows CSV** for dated payment rows.

## 2. Portfolio

1. Value a bond on the valuation screen.
2. Click **Add bond to portfolio**.
3. Repeat for other positions, using the same settlement date.
4. Click **Value portfolio**.

The app aggregates dirty market value, accrued interest, dollar DV01 and scheduled receipts. Duration and convexity are market-value weighted. Scenario P&L sums the positions' responses to equal changes in their own yields. No portfolio-average YTM is presented.

The portfolio input is a JSON array of bond terms, so you can save and edit it. Analysis results are saved in local history. The editable portfolio form itself resets when the page is reloaded; export its full analysis JSON to retain your position inputs.

## 3. Treasury bills

Enter face amount, settlement and maturity. Choose either a bank-discount rate or a quoted price as the input.

The app reports purchase cost, interest at maturity, holding-period return and annualized rate measures. Bank-discount yield uses face value and Actual/360. Simple investment yield uses purchase price and Actual/365. For bills longer than 182 days, that simple yield is not Treasury's coupon-equivalent investment rate.

The default historical 28-day example gives a quote of 99.648833 per $100 at a 4.515% bank-discount rate.

## 4. Carry explorer

Enter continuously compounded zero yields in percent. For example, enter `4.5` for 4.5%.

Select a one-, three- or six-month horizon. The explorer estimates what zero-coupon bonds would return if the entire yield curve stayed unchanged as they aged. It separates constant-yield aging from the additional roll-down contribution.

This is a scenario, not a forecast. Do not substitute par yields or coupon rates for zero yields.

## 5. Strategy research

For a reproducible first run, use the bundled real Fed snapshot, 2010–2025, highest raw carry, a ten-year maturity cap and five-basis-point monthly round-trip cost.

The rule uses each current curve to rank eligible maturities, buys the highest-ranked hypothetical zero-coupon bond, and values it on the following curve. It repeats monthly and deducts trading costs. It compares this portfolio with equally weighted maturities and a cash proxy.

| Output | Interpretation |
|---|---|
| Growth of $10,000 | Compounded modeled portfolio path. |
| CAGR | Annualized compounded return over the sample. |
| Volatility | Annualized variation in normalized monthly returns. |
| Maximum drawdown | Largest decline from a previous peak. |
| Excess Sharpe | Mean excess return relative to variability, using the app's cash proxy. |
| Cost sensitivity | Results at several fixed monthly round-trip cost levels. |
| Yearly results | Holding-period returns grouped by their ending calendar year. |

The included fixed-rule run returned approximately 3.25% annually with a 24.94% maximum drawdown. See `VALIDATION.md` for the exact sample, assumptions and benchmark results. This retrospective result does not establish future profitability.

Use fitted-curve backtests for research: these are not executable quotes. The cash proxy is not a realized Treasury-bill series, and data vintages can be revised. Different maturity choices have different interest-rate risk.

## 6. Validation and history

The validation screen displays the bundled/reproduced test report. Running `python validate.py` refreshes numerical and automated-test results on your own machine. Browser evidence is separately associated with source-file hashes.

History lists recent local analysis runs. Copy a run ID into the export field to download saved inputs and outputs. Records are stored in `data/bondlab.sqlite`; raw curve snapshots are in `data/snapshots/`. Keep these local rather than uploading personal analyses to GitHub.

## Supported scope

Regular fixed-rate noncallable bullet bonds with contractual unadjusted payment dates and explicit settlement. No odd coupons, ex-coupon treatment, holiday-adjusted payments, TIPS, FRNs, amortizers, embedded options, default valuation or tax model. See [README.md](README.md) for full conventions and limitations.

The developer's professional title describes the author. The current app's numerical pricing engine is deterministic and does not use a machine-learning prediction model.
