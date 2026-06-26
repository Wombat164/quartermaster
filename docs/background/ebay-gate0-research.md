# Gate 0 -- eBay production Buy/Browse API access: research + verdict (2026-06)

Deep-research (multi-source, adversarially verified, 3-0 votes) into whether a personal,
human-approved Quartermaster can realistically get **production** eBay Browse/Buy API
access. Verdict drives the 2026-06-26 strategic pivot (see `DECISIONS.md`).

## Verdict

**Too uncertain to build on.** Production Buy/Browse API access is partner-only,
business-model-gated, and explicitly "no guarantee" -- with no surfaced precedent of a
granted personal/hobbyist single-user app. Quartermaster's *design* is fully compliant;
the risk is **commercial/business-case rejection**, not legality. -> Drop the eBay API
dependency; build search+compare on compliant sources; defer bid/buy.

## Findings (confidence + source)

1. **[high]** Production Buy/Browse is partner-only via eBay Partner Network (EPN),
   acceptance based on the proposed business model, **"no guarantee"** of approval.
   (developer.ebay.com/api-docs/buy/static/buy-requirements.html)
2. **[high]** Full pipeline: EPN Buy API Application -> reply to the confirmation email
   with **mocks + data flows** -> ~10-business-day decision -> Developer Support ticket
   -> compliance review -> **signed eBay contracts (possibly an MNDA)** before a
   production keyset works. (buy-requirements.html)
3. **[high]** A mandatory, human-reviewed **Application Growth Check** is the final gate
   before a production keyset can call restricted APIs (Browse, Buy Feed, Marketplace
   Insights). (developer.ebay.com/api-docs/static/gs_use-the-application-growth.html)
4. **[medium]** Personal/hobbyist approval odds are **weak-to-uncertain**: "meeting
   standard eligibility is not a guarantee"; **no granted-personal-app precedent**
   surfaced; community threads show restricted-API **denials**.
   (buy-requirements.html; api-insights.html)
5. **[high]** Our **human one-click approval** keeps us on the permitted side of the
   **Feb-20-2026 User Agreement** ban on "buy-for-me agents, LLM-driven bots, or any
   end-to-end flow that places orders without human review".
   (valueaddedresource.net/ebay-bans-ai-agents...; ebay.com user-agreement id=4259)
6. **[high]** Our **deterministic, no-LLM** processing avoids the API License (Jun-24-2025)
   bans on training AI on eBay Content and ingesting Restricted-API data into generative
   AI without written consent. (developer.ebay.com/join/api-license-agreement)
7. **[high]** Our **<6h raw-content purge** meets/exceeds the freshness cap.
   (api-license-agreement)
8. **[high]** Executing via **Gixen** (not eBay APIs) is correct + necessary: eBay's
   bidding/PlaceOffer API is closed to general developers.
   (jbidwatcher.com/why_not_api; placeoffer reference)
9. **[high]** **Sniping is officially permitted** by eBay (bids valid up to close;
   bidding software allowed). (ebay.com/help bid-sniping id=4224)
10. **[high]** **Marketplace Insights** (90-day sold comps) is the legit sold-price
    fallback but is Limited Release, beta, **even more tightly gated / closed to new
    users**. (developer.ebay.com/api-docs/buy/static/api-insights.html)

## Recommendation (applied)

- **Drop the eBay API dependency.** eBay = manual browse only (+ manual Gixen later).
- **Search+compare on compliant sources:** classifieds saved-search alert EMAILS
  (discovery) + **SerpApi** Google Shopping (compare baseline -- retail + Amazon + eBay
  listings AS PRICE COMPS, no scraping) + a bootstrap EUR/GB table.
- **Key nuance:** dropping the API does NOT lose the eBay *price* signal -- SerpApi
  surfaces eBay listings via Google Shopping; we lose only API-driven eBay *sniping*
  (deferred to Phase 2 anyway).
- **If we ever apply:** frame compliance-forward (mandatory human approval, no autonomous
  ordering, no AI, deterministic, <6h purge), Browse-only -- but architect so the product
  works if DENIED.
