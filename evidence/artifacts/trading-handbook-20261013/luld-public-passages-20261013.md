# LULD public-source passages

Evidence class: `source_review`. These are bounded text excerpts from public
primary sources, parsed with MinerU 4.0.10, local flash. Images, navigation and
page bundles are omitted. The raw HTML, PDF and DOCX remain outside this public
artifact; their hashes below identify the captured public bytes, not this
extracted document. No trading execution is reported here.

## Official overview

Source URL: https://www.luldplan.com/

Retrieval window: 2026-10-13T15:33:14Z through 2026-10-13T15:35:26Z.
Version: unversioned official overview, as read in that window.
Raw source: `luld-home.html`, 30,771 bytes.
SHA256 of the capture of a public page, read in that window:
`b55070d97cbed50cab844c95dac70a825b31c06a5cb9820a2e941b53ab44f4c3`.
Parser locator: `doc:b55070d/tier:flash/page:1`.

### Overview — excerpt

The Plan is designed to prevent trades in NMS Stocks from occurring outside specified price bands, which are set at a percentage level above and below the average reference price of a security over the preceding five-minute period. The percentage level is determined by a security's designation as a Tier 1 or Tier 2 security. Tier 1 comprises all securities in the S&P 500, the Russell 1000 and select Exchange Traded Products (ETPs). Tier 2 comprises all other NMS securities, except for rights and warrants, which are specifically excluded from coverage. The Plan applies during regular trading hours of 9:30 am ET - 4:00 pm ET.

### Calculation of Price Bands — excerpts

The price bands, consisting of a Lower and Upper Price Band for each NMS Stock, are calculated by the two SIPs - CTA and Nasdaq UTP. The SIPs calculate upper and lower price bands by applying a formula to a Reference Price, which is the arithmetic mean price of Eligible Reported Transactions over the prior five minute period. The first Reference Price of the day is either the primary market's opening price or the primary market's previous day's closing price/last sale when opening on a quote. If no eligible trades have occurred in the prior five minutes, the previous Reference Price remains in effect. The Reference Price is updated after 30 seconds only if a new Reference price would be least 1% away from the current Reference Price.

The **Price Bands** are calculated by multiplying the current Reference Price by the applicable Percentage Parameter and then adding or subtracting that value from the Reference Price and rounded to the nearest penny.

Price Band = (Reference Price)+/- ((Reference Price)x (Percentage Parameter))

The source table is titled **Tier 1 Securities and Tier 2 Symbols below $3.00
(9:30am - 3:35pm)**. Its extracted cells are:

| PREVIOUS CLOSING PRICE | PERCENTAGE PARAMETER |
| --- | --- |
| Greater than $3.00 | 5% |
| $0.75 up to including $3.00 | 20% |
| Less than $0.75 | Lesser of $0.15 or 75% |

The second source table is titled **Tier 2 Securities (9:30am - 4:00pm)**:

| PREVIOUS CLOSING PRICE | PERCENTAGE PARAMETER |
| --- | --- |
| Greater than $3.00 | 10% |

Price Bands are doubled during last 25 minutes of the regular trading day for all Tier 1 Securities and for Tier 2 Securities below $3.00.

The table cells and doubling note above preserve the overview's wording; they
do not resolve an amendment's legal status or the exact-$3 timing boundary.

### Operation of Price Bands — excerpt

When the National Best Bid (Offer) is below (above) the Lower (Upper) Price Band, the SIPs disseminate the National Best Bid (Offer) with an indicator identifying it as unexecutable. Trading immediately enters a Limit State if the National Best Offer (Bid) equals but does not cross the Lower (Upper) Price Band. When a Limit State occurs, the SIPs indicate the National Best Bid (Offer) as a Limit State Quotation. Trading exits a Limit State if, within 15 seconds of entering the Limit State, all Limit State Quotations are executed or canceled in their entirety. If the market does not exit a Limit State within 15 seconds, the primary listing exchange declares a five-minute Trading Pause. The Trading Pause may be extended for another five minutes. Thereafter, all markets may resume trading. If a security is in a Trading Pause during the last 10 minutes of regular trading hours, the primary listing exchange will not reopen trading and will attempt to execute a closing transaction using its established closing procedures.

## Official document index — excerpts

Source URL: https://www.luldplan.com/plans

Retrieval window: 2026-10-13T15:33:14Z through 2026-10-13T15:35:26Z.
Version: unversioned official document index, as read in that window.
Section: **LULD Plans**.
Raw source: `luld-plans.html`, 14,927 bytes.
SHA256 of the capture of a public page, read in that window:
`bb82d87c12fab1f6d0d20babbf968f416e9ba642b56c72b3961896fdb31764fa`.

- [LULD Plan, specifies data points for inclusion in Overnight Trading (2026)](https://cdn.luldplan.com/plans/LULD-Plan-specifies-data-points-for-inclusion-in-Overnight-Trading-2026.docx)
- [LULD Plan through Amendment 20, which was approved by the SEC on April 21, 2020, specifies data points for inclusion in Quarterly Monitoring Reports.](https://cdn.luldplan.com/plans/LULD-Plan-Amendment-20.pdf)

These are source labels, not a new claim that the 2026 text is effective.

## 2026 document — cover excerpt

Source URL: https://cdn.luldplan.com/plans/LULD-Plan-specifies-data-points-for-inclusion-in-Overnight-Trading-2026.docx

Retrieval window: 2026-10-13T15:33:14Z through 2026-10-13T15:35:26Z.
Version: index-labelled 2026 text, effective amendment status unestablished.
Section: **Exhibit A**, cover page.
Raw source: `luld-plan-2026.docx`, 260,698 bytes.
SHA256 of the captured public document, read in that window:
`efe6c32d7ef2366c8ec01ef595d5bc62a2576887c7006c2e4942e6c84441c6d4`.
Parser locator: `doc:efe6c32/tier:flash/page:1`.

> Exhibit A
>
> Proposed new language is *italicized*; proposed deletions are in [brackets]
