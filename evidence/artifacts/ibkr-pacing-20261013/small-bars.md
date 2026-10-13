> This page is for TWS API.

> For clean Markdown of any page, append .md to the page URL.
> For a complete documentation index, see https://ibkrcampus.com/docs/llms.txt.

# Pacing Violations for Small Bars (30 secs or less)

Although Interactive Brokers offers our clients high quality market data, IB is not a specialised market data provider and as such it is forced to put in place restrictions to limit traffic which is not directly associated to trading. A Pacing Violation occurs whenever one or more of the following restrictions is not observed:

Important: these limitations apply to all our clients and it is not possible to overcome them. If your trading strategy's market data requirements are not met by our market data services please consider contacting a specialized provider.

* Making identical historical data requests within 15 seconds.
* Making six or more historical data requests for the same Contract, Exchange and Tick Type within two seconds.
* Making more than 60 requests within any ten minute period.
* Note that when BID\_ASK historical data is requested, each request is counted twice. In a nutshell, the information above can simply be put as "do not request too much data too quick".
