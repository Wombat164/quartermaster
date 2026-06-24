# Price-comparison via API / MCP — options (June 2026)

The EU price-aggregators (Geizhals, Idealo, Tweakers) **block automated fetching** and have **no open public API** (affiliate/partner only). Google also killed its free Shopping API in 2013. So programmatic multi-retailer price data is a paid space. Two categories:

## A. Structured price-data APIs (return prices; no scraping)
| Service | Coverage | Price | Best for |
|---|---|---|---|
| **SerpApi** (serpapi.com) | Google Shopping + Amazon/eBay/Walmart/Bing (incl. EU) | Free 250/mo, **$25/mo** 1k searches | Cleanest "compare across the web" + price-monitoring product |
| **PriceAPI** (priceapi.com) | Google Shopping, Amazon, eBay | Paid | Dedicated product-price lookups |
| **metoda Price API** | Amazon + **idealo** + Google + eBay (EU) | Enterprise | DACH/EU pricing |
| **DataForSEO** Google Shopping | Google Shopping | cheap per-request | Budget bulk |
| **Keepa** | **Amazon only** price *history* | cheap | Amazon tracking (camelcamelcamel engine) |

## B. Scraping MCPs that bypass bot-blocks (would unblock Geizhals/Idealo)
| MCP server | Strength | Price | Notes |
|---|---|---|---|
| **Bright Data MCP** | Beats sites that actively block scrapers (400M+ residential IPs) | Free 5k req/mo, then $499+/mo | The one that reliably cracks Geizhals/Idealo 403s |
| **Apify MCP** | 30k+ ready Actors incl. dedicated **Idealo** + **Billiger.de** scrapers | $29/mo pay-per-use | Best EU price-comparison fit |
| **Firecrawl MCP** | Fast clean structured extraction | Free 500, $16/mo | Lighter anti-bot muscle |

## Recommendation
- **One-off purchases:** skip all of this — just check Geizhals / Tweakers Pricewatch in a browser.
- **Recurring capability wired into Claude Code:** start with **SerpApi** (easiest, generous free tier, multi-retailer via Google Shopping). If you specifically need to pull Idealo/Geizhals EU listings that block everyone, use **Apify** (ready-made Idealo scraper) or **Bright Data** (heaviest anti-bot).
- Claude can add any of these as an MCP server once you have an API key.
