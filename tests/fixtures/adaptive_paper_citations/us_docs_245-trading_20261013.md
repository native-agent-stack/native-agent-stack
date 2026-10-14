---
updatedAt: 2026-10-12T06:43:44.000Z
agentTools:
  siteIndex: https://docs.alpaca.markets/llms.txt
  projectIndex: https://docs.alpaca.markets/us/llms.txt
---

# 24/5 Trading

### What is 24/5 Trading (Overnight Trading)?

Overnight Trading extends market hours to provide a 24-hour, 5-day-a-week trading experience for all NMS securities. The overnight session operates from 8:00 PM ET Sunday to 4:00 AM ET Friday, bridging the gap between one day's post-market session and the next day's pre-market session.

***

### How does the overnight trading session work?

Overnight trade executions and market data are facilitated by the Blue Ocean Alternative Trading System (BOATS). As an Alternative Trading System (ATS), BOATS operates an independent overnight trading session outside of traditional stock exchanges.

***

### What are the hours for the 24/5 trading sessions?

The trading sessions are structured as follows, from Sunday evening to Friday evening:

* **Overnight Session:** 8:00 PM - 4:00 AM ET (technically occurs on the evening before the trade date)
* **Pre-Market Session:** 4:00 AM – 9:30 AM ET
* **Regular Market Session:** 9:30 AM - 4:00 PM ET
* **After-Hours Session:** 4:00 PM - 8:00 PM ET

The overnight session follows the NYSE holiday calendar. If US markets are fully closed for a holiday, the overnight trading session immediately preceding that holiday will not run. ***For example, the overnight session will be closed on the Wednesday evening before US Thanksgiving (8:00 PM ET) and will resume on Thursday evening at 8:00 PM ET.*** On US market half-days, the overnight trading session runs as normal for the full eight hours (8:00 PM ET – 4:00 AM ET), even if regular or after-hours trading closes early. ***For example, on the Friday after US Thanksgiving, the overnight session runs as usual, but the after-hours session does not.***

***

### How can I enable overnight trading?

Please contact your Customer Success Manager for details on pricing and the steps required to enable overnight trading for your account.

***

### How can I access market data for the overnight session?

We offer a high-accuracy indicative data feed through our partnership with Blue Ocean, available for a monthly fee. Please contact our sales team for pricing details.

***

### What is included in the overnight market data feed?

The market data feed provides access to:

* **Indicative Real-time Quotes:** Real-time bid and ask prices that are indicative of the market.
* **Indicative Trades:** Trade data that is delayed by 15 minutes and adjusted to fit within the real-time bid-ask spread.

***

### What securities are available for overnight trading?

All National Market System (NMS) securities are available for trading during the overnight session. Assets tradable in the overnight session can be identified via the `overnight_tradable` attribute in the Assets API.  The list may be limited due to compliance or risk procedures, and the best way to validate the available securities is by using our Assets API as outlined above. OTC securities are not part of the NMS and are therefore not available.

***

### What order types and time-in-force (TIF) options are supported?

* **Order Type:** Only `limit` orders are supported during the overnight session.
* **Time-in-Force (TIF):** The supported TIF options are `day` and `gtc`.
  * `day`**:** Orders placed during the overnight session will remain active through the regular and after-hours sessions of the upcoming trading day. If unfilled, the order is canceled at 8:00 PM ET.
  * `gtc`**:** Good-Til-Canceled orders remain active across trading sessions until they are either filled or explicitly canceled. The table below summarizes the supported `gtc` configurations and their default corporate action handling.

| Order Type     | `extended_hours` / Overnight | TIF   | Default Corporate Action Handling |
| -------------- | ---------------------------- | ----- | --------------------------------- |
| Fractional     | `true`                       | `gtc` | Cancelled at 8 PM ET              |
| Fractional     | `false`                      | `gtc` | Not supported                     |
| Non-Fractional | `true`                       | `gtc` | Cancelled at 8 PM ET              |
| Non-Fractional | `false`                      | `gtc` | Cancelled at 8 PM ET              |

In order to get GTC support, please reach out to your Customer Success Manager to enable it.

<Callout icon="📘" theme="info">
  ### **Note**

  Fractional `gtc` orders without `extended_hours` / overnight enabled are not currently supported.
</Callout>

***

### Is fractional share trading supported?

Yes, fractional share trading is supported during the overnight session and functions the same way as it does during other extended-hours sessions.

***

### Are there restrictions on margin or buying power during the overnight session?

Yes. Day Trading Buying Power (DTBP) does not apply to the overnight session. This means 2x multiplier is the max margin buying power for overnight session trades. If an account uses DTBP for an order during the post market session, the order might be rejected (at 8 PM ET) due to insufficient buying power (if reg\_t or non-DT buying power is insufficient).

***

### What happens to an order that is not filled during the overnight session?

If your `day` order is not filled during the overnight session, it will automatically carry over into the pre-market, regular, and after-hours sessions for that trade date. It remains an active order until it is executed or the market closes at 8:00 PM ET.

***

### How does trade settlement work for overnight trades?

The overnight session marks the beginning of a new trading day. Trades are assigned a date based on their execution time and settle on a T+1 basis from that date.

* **Example:** A trade executed at 9:00 PM ET on a Monday is assigned a trade date of Tuesday and will settle on Wednesday (T+1).

***

### How do corporate actions affect overnight trading?

A security may be halted from trading during the overnight session while a pending corporate action is being processed. Furthermore, due to the way trade dates are assigned, purchasing a stock during the overnight session on its ex-dividend date will not entitle you to that stock's dividend.

***

### What happens when a security is halted during the overnight session?

If an asset is halted overnight (e.g., due to a corporate action or pending news), the halt typically persists for the entire session. Orders submitted for a halted security will be accepted by the system with a status of `accepted` but will be held in a pending state. This ensures your order can be executed as soon as the halt is lifted and trading resumes in the next session.

***

### What API changes are required to support overnight trading?

Integration requires awareness of two new boolean attributes in the `Assets` API endpoint:

* `overnight_tradable`: Indicates if the asset is eligible for trading in the overnight session.
* `overnight_halted`: Indicates if an `overnight_tradable` asset is currently halted.

Additionally, a new `overnight` feed name has been introduced for the Market Data API.

***

### How can I identify which assets are tradable overnight via the API?

You can identify eligible assets by calling the `v1/assets` endpoint and filtering for assets where the `overnight_tradable` attribute is `true`.

***

### When is the best time to sync the list of overnight-tradable assets?

We begin syncing our list of tradable assets at 7:05 PM ET and run updates every 10 minutes until 7:45 PM ET. For the most up-to-date list, we recommend syncing your asset list between 7:45 PM and 8:00 PM ET, with 7:55 PM ET being the ideal time.

***

### Can I access delayed historical overnight requests with an overnight subscription?

Yes, you can access delayed historical overnight requests with an overnight subscription, provided that the end parameter in your request is at least 15 minutes old.

**To access delayed historical overnight data, make sure to include the parameter&#x20;**`feed=boats`**&#x20;in your request,&#x20;**`feed=overnight`**&#x20;will give error.**

Example: If you have an overnight subscription and want to request overnight/BOATS data ending at 10:00 PM EST , you can do so any time after 10:15 PM by specifying`feed=boats` in your request.

***

### What Is 23/5 Trading?

23/5 describes a structural shift in U.S. equity markets toward near-continuous trading five days per week, with a daily one-hour maintenance window (markets are not open 24/7).

At an industry level, the change spans three layers:

Exchange trading — Key venues add or expand an overnight session (for example, NYSE Arca overnight 9:00 p.m. – 4:00 a.m. Eastern Time), in addition to existing pre, core, and post sessions.
Trade reporting — FINRA/Nasdaq Trade Reporting Facilities (TRFs) extend hours so eligible executions can be reported in near real time across the extended window.
Clearing and market data — Depository Trust & Clearing Corporation (DTCC) infrastructure and Securities Information Processors (SIPs) align so trades can clear and tape can disseminate outside traditional daytime hours.

SIFMA recommends a consistent market structure built around:

Element<br />Timing (Eastern Time)<br />Weekly trading window<br />Sunday 9:00 p.m. through Friday 8:00 p.m.<br />Daily maintenance pause<br />8:00 p.m. – 9:00 p.m. Monday through Thursday<br />Trade date end<br />8:00 p.m. (executions after 8:00 p.m. roll to the next trade date under FINRA definitions effective December 6, 2026)

***

### When Is This Happening?

The target industry go-live date is December 6, 2026, subject to Securities and Exchange Commission (SEC) approvals, SIP readiness, exchange testing, and related infrastructure.

Reference milestones:

DTCC NSCC has extended clearing toward a 24×5 operating model ahead of full alignment of tape and TRF hours (Nasdaq cites NSCC extended clearing from June 28, 2026).
NYSE Arca plans to launch extended overnight trading on December 6, 2026, contingent on SIP and DTCC readiness.
FINRA/Nasdaq TRFs plan to operate 9:00 p.m. Sunday through 8:00 p.m. Friday, with the same 8:00–9:00 p.m. pause Monday through Thursday.
SIPs have filed to extend operating hours; SIFMA cites a December 2026 target pending SEC approval.

Alpaca follows venue and post-trade utility readiness. Alpaca does not control regulatory or exchange implementation dates.

***

### How Is This Different From Overnight Trading Today?

Today: We route overnight equity flow to alternative trading systems (ATSs) that operate outside regular exchange hours.

After exchange 23/5: Listed exchanges (beginning with NYSE Arca’s overnight session) can match overnight flow under exchange rules, including static overnight Limit Up/Limit Down (LULD) price bands (NYSE: 20% bands from 9:00 p.m. – 4:00 a.m.) and inclusion in consolidated volume.

Post-trade alignment: Extended TRF and SIP hours allow overnight exchange trades to be reported and disseminated during the session, not only queued until the next morning.

For Alpaca partners, the integration surface for placing overnight-eligible orders will not change. Session handling and routing remain on Alpaca’s broker-dealer and technology stack.

***

### Will Alpaca Support 23/5 From Day One?

Alpaca is building toward industry go-live on December 6, 2026 so partners using our APIs can use extended exchange overnight when venues and post-trade utilities are live.

Alpaca does not plan a separate partner-facing “Alpaca rollout”  for partners who already support overnight trading through Alpaca today.
Partners should continue to use the same order instructions, time-in-force (TIF), and lifecycle semantics they use for overnight-eligible flow now.
Final availability depends on regulatory approval, SIP go-live, and exchange testing. Alpaca will communicate if any dependency slips.

Partners who need a firm commitment for regulatory filings or client communications should align with their Alpaca Customer Success Manager as industry test windows approach (Nasdaq publishes TRF test dates in October through December 2026).

Trading Hours and the Daily Maintenance Pause
Industry weekly window (Eastern Time):

Open: Sunday 9:00 p.m.
Close: Friday 8:00 p.m.
Daily pause: 8:00 p.m. – 9:00 p.m. Monday through Thursday (processing, reconciliation, trade-date transition).

NYSE Arca sessions after go-live:

Session
Hours (ET)
Overnight
9:00 p.m. – 4:00 a.m.
Early
4:00 a.m. – 9:30 a.m.
Core
9:30 a.m. – 4:00 p.m.
Late
4:00 p.m. – 8:00 p.m.

The overnight session does not open with an auction. Continuous trading begins at 9:00 p.m. (NYSE Arca accepts orders for the overnight session from 8:59 p.m.).

Alpaca behavior during the 8:00–9:00 p.m. exchange pause: Orders that would route to exchanges for the overnight session are cancelled on the exchange path and re-routed to overnight ATSs where those venues are operational, so overnight intent can continue to be worked where ATS liquidity exists.

***

### How Does Alpaca Route Overnight Orders?

Alpaca already routes to overnight ATSs and already transitions orders between sessions (for example, pre-market, regular, post-market, and overnight) according to order instructions and symbol eligibility.<br />When exchange overnight is live, exchange-bound overnight orders follow the same overnight handling, except during the one-hour exchange maintenance window, when the ATS fallback behavior described above applies.<br />All overnight orders are treated in a single routing bucket. Partners do not select Blue Ocean, Nasdaq, or other overnight venues through the API. Alpaca smart order routing and operational rules apply.<br />Existing and new orders continue to route according to the instructions on the order (side, TIF, extended-hours eligibility, and related fields).

***

### Do Order Validity, TIF, or Order Lifecycle Change?

No changes are expected for standard Alpaca Broker API integrations:

The same time-in-force and extended hours semantics you use today for overnight-eligible flow.
The same order lifecycle from the partner’s perspective (submission, fill, cancel, reject).
No new FIX tags or custom fields are required on the partner integration for TRF-style overnight reporting; that processing occurs in clearing, broker, and TRF infrastructure.

Exchange and clearing session identifiers (for example, TradingSessionID) are handled between Alpaca, venues, and clearing utilities.

***

### Will the Overnight-Tradable Symbol Universe Expand?

A material expansion of the overnight symbol universe is unlikely solely because of exchange 23/5 sessions.

Symbols with sustained overnight demand generally already have ATS liquidity today. Exchange overnight may improve price discovery and reporting for those names, but partners should not expect an immediate shift to “all NMS stocks” overnight.

Partners should continue to:

Honor Alpaca’s /assets endpoint and asset restrictions.
Set end-user expectations on liquidity, spreads, and volatility outside the core session.

Trade Date and Settlement
Trade-date rules are industry-defined and depend on execution time within the extended window. Under FINRA rules effective December 6, 2026:

A trade date runs from 8:00 p.m. on one calendar day to 8:00 p.m. on the next calendar day.
Executions after 8:00 p.m. generally receive the next trade date.
Executions between midnight and 8:00 p.m. on a calendar day generally receive that same calendar day as trade date.

NYSE Arca overnight examples (from NYSE published FAQ):

Execution window
Trade date assignment (illustrative)
9:00 p.m. – 11:59 p.m.
Trade date = next calendar day; settlement follows regular-way from that trade date
12:00 a.m. – 4:00 a.m.
Trade date = same calendar day

Partner-facing guidance:

Display trade date and settlement date from Alpaca execution and account reports, not from clock time alone.
Overnight prints may use sale conditions that are not last-sale eligible (NYSE uses condition ‘T’ in overnight, early, and late sessions). Consolidated volume still includes eligible extended-hours trades, but “last sale” semantics differ from the core session.

Holidays and Early Closes
On many exchange holidays, the late session may end early on the preceding business day; overnight trading may resume at 9:00 p.m. on the holiday evening (see NYSE extended-hours FAQ for examples).

TRFs similarly cease at 8:00 p.m. on the last business day before a holiday and resume at 9:00 p.m. on the holiday evening, or on Sunday after a Friday holiday.

Partners should rely on market calendars rather than assuming markets are always open.

Liquidity, Execution Quality, and Risk
Industry stakeholders highlight that extended and overnight sessions often feature lower liquidity, wider spreads, and different volatility than the core session. Supervision, best execution, and surveillance frameworks continue to evolve for thin sessions.

NYSE overnight considerations include static 20% LULD bands and adjusted clearly erroneous execution (CEE) policies when correct bands are in place.

For end users, partners should:

Disclose that execution quality may differ from the 9:30 a.m. – 4:00 p.m. core session.
Encourage limit orders where appropriate for overnight flow.
Monitor corporate actions; listing venues are adopting uniform rules to halt certain complex actions during overnight sessions.

Alpaca continues to apply risk controls and routing checks. Partners remain responsible for client suitability, disclosures, and supervisory obligations in their jurisdictions.

***

### What Should Partners Do to Prepare?

Product and Compliance<br />Update help center content and risk disclosures for near-continuous U.S. equity trading.<br />Train support teams on trade date rolling at 8:00 p.m. and the daily 8:00–9:00 p.m. maintenance pause.<br />Avoid promising venue choice (for example, ATS versus a specific exchange); routing is Alpaca-managed.

Engineering
No API migration is expected for standard overnight trading through Alpaca.

***

#### Disclosures

The content of this article is for general information only and is believed to be accurate as of the posting date, but may be subject to change. Alpaca does not provide investment, tax, or legal advice. Please consult your own independent advisor as to any investment, tax, or legal statements made herein.

Orders placed outside regular trading hours (9:30 a.m. – 4:00 p.m. ET) may experience price fluctuations, partial executions, or delays due to lower liquidity and higher volatility. 

Orders not designated for extended hours execution will be queued for the next trading session.

Additionally, fractional trading may be limited during extended hours. For more details, please review [Alpaca Extended Hours & Overnight Trading Risk Disclosure](https://files.alpaca.markets/disclosures/library/ExtHrsOvernightRisk.pdf).

Fractional share trading allows a customer to buy and sell fractional share quantities and dollar amounts of certain securities. Fractional share trading presents unique risks and is subject to particular limitations that you should be aware of before engaging in such activity. See Alpaca Customer Agreement at [Alpaca - Disclosures and Agreements](https://alpaca.markets/disclosures) for more details.

Margin trading involves significant risk and is not suitable for all investors. Before considering a margin loan, it is crucial that you carefully consider how borrowing fits with your investment objectives and risk tolerance.

When trading on margin, you assume higher market risk, and potential losses can exceed the collateral value in your account. Alpaca may sell any securities in your account, without prior notice, to satisfy a margin call. Alpaca may also change its “house” maintenance margin requirements at any time without advance written notice. You are not entitled to an extension of time on a margin call. Please review the Firm’s [Margin Disclosure Statement](https://files.alpaca.markets/disclosures/library/MarginDiscStmt.pdf) before investing.

All investments involve risk, and the past performance of a security, or financial product does not guarantee future results or returns. There is no guarantee that any investment strategy will achieve its objectives. Please note that diversification does not ensure a profit, or protect against loss. There is always the potential of losing money when you invest in securities, or other financial products. Investors should consider their investment objectives and risks carefully before investing.

Securities brokerage services are provided by Alpaca Securities LLC ("Alpaca Securities"), member [FINRA](https://www.finra.org/)/[SIPC](https://www.sipc.org/), a wholly-owned subsidiary of AlpacaDB, Inc. Technology and services are offered by AlpacaDB, Inc.

Cryptocurrency services are made available by Alpaca Crypto LLC ("Alpaca Crypto"), a FinCEN registered money services business (NMLS # 2160858), and a wholly-owned subsidiary of AlpacaDB, Inc. Alpaca Crypto is not a member of SIPC or FINRA. Cryptocurrencies are not stocks and your cryptocurrency investments are not protected by either FDIC or SIPC. Please see the [Disclosure Library](https://alpaca.markets/disclosures) for more information.

This is not an offer, solicitation of an offer, or advice to buy or sell securities or cryptocurrencies or open a brokerage account or cryptocurrency account in any jurisdiction where Alpaca Securities or Alpaca Crypto, respectively, are not registered or licensed, as applicable.