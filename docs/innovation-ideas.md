# New feature ideas - September 2026 research pass (Nosy)

Requested directly by the user: "Nosy needs to activate and browse online
to give me new innovative ideas we can use." Research-and-ideation only -
nothing here has been implemented, and nothing here should be treated as
scoped/ready to build without a Bossy pass to turn it into real backlog
items first.

**Method:** skimmed `docs/backlog.md` in full first (all ~28 numbered
items plus the Open Questions / Confirmed Drops / Parked sections) so
nothing below repeats something already shipped, already scoped, or
already explicitly rejected. Then did real web research (see Sources at
the end of each idea and the consolidated list at the bottom) in four
directions per the brief: (1) what leading portals do that this platform
doesn't, (2) genuinely emerging proptech ideas, (3) ideas that lean into
this platform's actual differentiators (cross-portal aggregation +
dedup, investor/CRM focus), (4) Bulgaria-specific angles.

**How to read this doc:** each idea states what it is, why it fits this
platform specifically (not "any real estate site"), and a build-
complexity/data-availability call. Where a claim rests on outside
research rather than something already confirmed in this codebase, it's
sourced. Nothing here is marked as INFERRED-from-a-screenshot the way
`property-filter-spec.md` uses that word - the concern for *this*
document is different: whether an external factual claim (a legal rule,
a rental-yield figure, a regulatory date) is actually sourced or is my
own unverified extrapolation. Anything not explicitly sourced below is
my own product judgment, not a researched fact - flagged inline.

**Not reviewed by Missy.** No `Agent`/Task tool was available in this
session (checked - same recurring constraint several backlog entries
already flag), so this document has not had her fact-checking pass. Per
this repo's standing rule, that means it should not be treated as fully
verified or "ready" until someone with that tool available sends it to
her - flagged here plainly rather than silently skipped. What she'd be
checking specifically: that every externally-sourced factual claim below
(legal thresholds, tax rules, yield figures) really traces to the cited
source and isn't inflated or misremembered, and that every idea correctly
marked "own-data-only" genuinely doesn't need anything imotenradar
doesn't already scrape.

---

## Tier 1 - recommended first: cheap, own-data-or-near-it, and specifically
leans into this platform's aggregator/investor angle

### 1. Auction & distressed-asset hub (built around bcpea.org data this platform already uniquely scrapes)

**What it is:** a dedicated top-level view for bcpea.org (Bulgarian
Chamber of Private Enforcement Agents) listings - the public-auction/
forced-sale data this platform already scrapes into `data/leads_bcpea.json`
but currently just folds into the general listings pool. A real hub would
add: days-until-auction-deadline countdown, a starting-price-vs-comparable-
market-price gap % (reusing the existing Comparables/Area Data machinery
from backlog item 15), and a deposit (задатък) calculator (a fixed % of
starting price, per Bulgarian enforcement-sale procedure).

**Why this platform specifically:** no general consumer portal (imot.bg,
homes.bg, or international names like Zillow/Rightmove) surfaces
court-enforcement auction data at all - it's a distinct legal category
most portals don't touch. imotenradar already has this data ingested and
nowhere else does; a dedicated hub turns an existing, currently-buried
data source into a genuinely differentiated distressed-asset-sourcing
feature squarely aimed at the investor audience this platform already
serves with the Deal Pipeline/Lead Generators.

**Build complexity / data:** mostly own-data. The gap-vs-market-price and
comparables math reuse item 15's existing functions unchanged. Two real
unknowns to check before scoping: whether `scraper_bcpea.py` currently
captures an explicit auction date/deadline field (needs a quick check of
`data/leads_bcpea.json`'s field union - not confirmed here) and whether
the fixed deposit-% rule is uniform enough across cases to hardcode a
single default (would need a quick real-world confirmation, not assumed).

### 2. A dedicated, browsable "Arbitrage Opportunities" hub - not just a badge

**What it is:** backlog item work already ships a per-listing
cross-portal price-divergence *flag*. This extends it into its own
ranked, filterable, sortable page - "biggest price gaps between where
the same property is listed" platform-wide, with an optional alert
("email/notify me when a new arbitrage listing over X% appears in city
Y") reusing the Lead Generator saved-search infrastructure that already
exists.

**Why this platform specifically:** this is the one category of feature
a single-source portal (Zillow, Rightmove, or any one Bulgarian portal
individually) cannot build at all - it only exists because imotenradar
aggregates and deduplicates across 8 sources. It's the platform's most
structurally defensible differentiator, and today it's expressed only as
a small badge on individual listings rather than a first-class,
browsable surface.

**Build complexity / data:** own-data only, and cheap - it's a new view
and a new Lead-Generator-alert type over data the platform already
computes (cross-portal `member_count`/per-source price already exist per
backlog item 13's multi-portal badge work).

### 3. Rental-yield benchmark overlay, sourced externally instead of scraped

**What it is:** backlog's Parked section already investigated scraping
Bulgarian rental listings directly and found under ~400 usable
whole-property listings nationwide - not enough for a reliable per-area
yield. That's still true and this idea doesn't change it. But a
*periodically-updated, small, manually-maintained reference table* of
published city-level gross rental yields from a third-party market
report (Global Property Guide publishes per-city Bulgarian gross rental
yields - as of Q1 2026, a national average of 4.19%, with city figures
cited around Plovdiv ~6%, Varna ~5.5%, Burgas ~5%, Sofia ~4.8-6%
depending on the source) would let the Deal Calculator/BTL Stress
Test/Area Data "Est. Yield" panel show an illustrative market-yield band
for a listing's city, clearly labeled as a third-party benchmark, not a
live number - while still requiring the user's own real rent figure for
the actual calculation (per item 15's existing, correct "never fabricate
a rent number" design decision).

**Why this platform specifically:** directly unblocks the one thing
already flagged as NOT built in item 15 and item 16 for lack of data
("Est. Yield gauge", "yield" excluded from the Heat Map/Live Map metric
list) - not a new feature so much as finally closing a gap this codebase
has already twice declined to fake.

**Build complexity / data:** small. This is a static reference table
(same shape as `BG_MUNICIPALITY_TO_OBLAST`), refreshed by hand
periodically against a cited public source - not a scraper, not a live
integration. Genuinely new data, but the cheapest possible kind (a
handful of numbers, re-checked every few months).

Source: [Global Property Guide - Bulgaria rental yields](https://www.globalpropertyguide.com/europe/bulgaria/rental-yields), [Bulgaria Rental Yields: City-by-City Performance](https://www.globalpropertyguide.com/europe/bulgaria/rent-yields)

### 4. Plain-language "why this deal is flagged" summary - a cheap, real answer to the "AI valuation explainability" trend

**What it is:** 2026 proptech research is converging hard on
*explainability* as the differentiator for AI-driven valuation (Zillow's
own stated 2026 direction is "sharing the factors that influence an
estimate," not just a bare number). This platform already computes
several real signals per listing (5-component motivation score, price
drop count/%, days on market, relisting events, cross-portal price
divergence) but shows them as separate numbers/badges, not a synthesized
explanation. A template-based (not ML) natural-language generator -
"Flagged Hot: relisted twice in 45 days, 12% below the area average, and
listed 18% cheaper on alo.bg than on imot.bg" - would give the same
"why" clarity the industry is moving toward, with zero new data and no
ML model needed.

**Why this platform specifically:** this is exactly the kind of
"differentiator" that leans into being investor-facing rather than
generic browsing - a buyer scanning Lead Generator results wants the
reason a deal is flagged, not just a badge color.

**Build complexity / data:** own-data only, pure frontend templating
over fields the platform already computes. Cheapest idea in this
document.

Source (general 2026 trend context, not a specific claim about this
platform): [Zillow - How Zillow spent 20 years teaching AI to understand home value](https://www.zillow.com/news/how-zillow-spent-20-years-teaching-ai-to-understand-home-value/)

### 5. Foreign-buyer eligibility notes, surfaced on listings that need them

**What it is:** Bulgaria's ownership rules genuinely differ by property
category in ways worth surfacing given this site's English-language,
apparently non-Bulgarian-investor-leaning framing:
- EU/EEA/Swiss citizens: no restriction on residential property or the
  land under it. Since a January 2024 EU Court of Justice ruling,
  EU citizens also face no restriction buying agricultural land (the
  old 5-year-residency requirement was struck down).
- Non-EU nationals: cannot directly buy agricultural land, forest, or
  vineyard parcels - only through a Bulgarian company. Residential
  property and its land are unrestricted for everyone regardless of
  nationality.

A small, clearly-labeled "ownership note" badge on listings already
classified (via the existing `category_classifier.py`) as agricultural
land/vineyard/forest would surface this for exactly the users who need
it, with an explicit "informational only, not legal advice, confirm with
a Bulgarian lawyer" disclaimer.

**Why this platform specifically:** this only makes sense for a
foreign-investor-facing Bulgarian platform - not a feature any domestic
Bulgarian portal or any international one would build. Cheap because the
category classification already exists.

**Build complexity / data:** trivial - a static rule keyed off
`category`, no new scraping. The legal content itself needs a one-time
accuracy check (ideally by someone who can verify against a primary
Bulgarian-language legal source, not just the secondary English-language
sources found here) before shipping any specific legal wording.

Sources: [ELRA - Bulgaria: Limitations to Foreigners](https://www.elra.eu/contact-point-contribution/bulgaria/limitations-to-foreigners/), [EU Court ruling on foreigners buying agricultural land in Bulgaria](https://www.advocatemarkov.com/the-eu-court-allowed-foreigners-to-buy-agricultural-land-in-bulgaria/), [Investropa - Buying Land as a Foreigner in Bulgaria](https://investropa.com/blogs/news/bulgaria-foreigners-own-land-really)

### 6. Residence-by-investment threshold badge - flagged with an open discrepancy, not shipped confidently

**What it is:** Bulgaria has a real-estate-investment path to a
residence permit for non-EU nationals. A badge on qualifying listings/
Deal Pipeline entries ("this purchase may meet Bulgaria's
residence-by-investment property threshold - confirm with an immigration
lawyer") would be a genuine, differentiated hook for the foreign-investor
audience this site's English framing implies.

**Real problem found, not glossed over:** the sources found here
disagree on the actual threshold - one cites approximately €300,000 in
real estate, another cites a BGN 600,000 figure for certain
third-country nationals, and neither is a primary legal source. **Do not
ship a specific number from this research alone** - this needs
confirmation against Bulgaria's actual Law for Foreigners in the
Republic of Bulgaria (or a lawyer) before any number appears on the live
site, given how easily a wrong investment-migration threshold could
mislead a real buyer's decision.

**Build complexity / data:** cheap once the real number is confirmed (a
static price-threshold rule) - the only blocker is getting the number
right, not the engineering.

Sources: [Henley & Partners - Bulgaria Residence by Investment](https://www.henleyglobal.com/residence-investment/bulgaria), [Get Golden Visa - Bulgaria Golden Visa 2026](https://getgoldenvisa.com/bulgaria-golden-visa) (the two disagreed on the exact threshold - see caveat above)

---

## Tier 2 - good ideas, bigger lift (new external data source, or meaningfully more design/engineering work)

### 7. Coastal/seasonal market-pattern indicator

**What it is:** Bulgaria's Black Sea coastal property market (Burgas,
Varna, Dobrich oblasts) has a real, distinct seasonality that Sofia's
apartment market doesn't - inventory and asking prices for vacation
property move with the tourist season in a way generic "market trend"
charts don't call out. Extending the existing Area Data trend chart
(item 15) with a month-over-month overlay, specifically surfaced for
coastal areas, would show this real regional-dynamics difference the
brief specifically asked about (Sofia vs. coastal vs. rural).

**Why this platform specifically:** a genuinely Bulgaria-specific
regional pattern, not a generic "add seasonality to any chart" idea -
directly answers the brief's "regional market dynamics" prompt.

**Build complexity / data:** own-data only (uses the same historical
snapshots already being collected), moderate effort mainly because it
needs its own chart/UI treatment rather than reusing the existing trend
chart as-is.

### 8. Area "heating up / cooling down" trend arrow (time dimension added to the existing Heat Map)

**What it is:** the Market Data hub's Strategy Heat Map (item 16) is
already a real, own-data ranking by current metrics - it's a snapshot,
not a trend. Adding a simple trend arrow (comparing an area's current
30/90-day averages against the prior period, using data already being
collected) gives a lightweight version of "gentrification/momentum
signal" using only data the platform already has.

**Build complexity / data:** own-data only, low-to-medium effort -
mostly a second aggregation pass over already-collected historical
snapshots plus a small UI addition to the existing heat map.

### 9. Bulgaria-specific school-quality proxy layer

**What it is:** unlike UK school-catchment data (correctly dropped from
this platform's scope per the spec), Bulgaria does publish real,
government-sourced comparative school data: NVO (7th-grade) national
external evaluation results and Matura (12th-grade) state matriculation
exam results, with real regional disparities documented down to
municipality level (weaker clusters in Northeastern/Northwestern
Bulgaria and around Plovdiv/Stara Zagora; nationally top schools like
American College of Sofia stand out clearly in the data).

**Why this platform specifically:** genuinely fills the "school-district-
equivalent data for Bulgaria" prompt in the brief, with a real (if
imperfect) public source, rather than assuming no BG equivalent exists.

**Build complexity / data:** needs real new data acquisition - this is
not something the platform already scrapes, and the granularity found
in this research is municipality-level, not exact school-catchment
level (Bulgaria doesn't appear to have strict catchment zones the way UK
schools do), so it would show as a municipality-level overlay/score
rather than a precise "this listing's assigned school" the way UK
Property Filter-style tools work. Needs its own investigation pass (find
and validate the actual published dataset, likely Ministry of Education
or regional-profile publications) before scoping further - flagged as a
real, promising direction, not a confirmed-ready feature.

Source: [Regional Profiles - Municipalities and the Matriculation Exam in Bulgarian](https://www.regionalprofiles.bg/en/news/municipalities-and-the-matriculation-exam-in-bulgarian-results-in-2019/), [Regional Profiles - NVO math results by municipality](https://www.regionalprofiles.bg/en/news/the-average-result-of-national-external-evaluation-in-mathematics-after-the-seventh-grade-is-weak-2-in-181-municipalities/)

### 10. Walkability/amenity-density score computed from free OpenStreetMap data

**What it is:** rather than a commercial walkability API (Walk Score
itself is primarily US/Canada-focused, per Redfin's own usage of it -
international coverage isn't confirmed for Bulgaria and wasn't found in
this research), compute a simple amenity-density score directly from
free OpenStreetMap Overpass-API data using lat/lng the platform already
has per listing: count of transit stops, groceries, pharmacies, schools
within a fixed radius. Not a licensed third-party score, a self-computed
proxy.

**Why this platform specifically:** every listing already has
geocoding; this is a straightforward extension rather than a new core
data source, and gives a walkability-equivalent signal Property Filter
itself relies on a paid UK-specific provider for.

**Build complexity / data:** medium - a new external API dependency
(Overpass/OSM, free but rate-limited, would need caching/batching
design), moderate engineering, but no cost and no BG-coverage question
mark the way a commercial walkability vendor would carry.

### 11. Bulgaria-specific due-diligence checklist attached to Pipeline deals

**What it is:** the "automated AI due diligence" proptech trend, scaled
to what this no-login, no-document-upload platform can realistically
build: a static, Bulgaria-specific checklist per Pipeline deal (not
AI-automated document review) with deep links to the actual free public
Bulgarian registries a real buyer needs to check - Имотен регистър
(property register) and Кадастър (cadastre) self-service search, and
municipal detailed-development-plan viewers where available - tracked as
checkable items reusing the existing Pipeline/tags infrastructure from
item 14.

**Why this platform specifically:** leans directly into the
investor/CRM angle (Deal Pipeline already exists) rather than being a
generic "any real estate site" feature, and gives real Bulgarian
buyers/investors (who may not know these registries exist) a genuinely
useful, currently-missing piece of the workflow.

**Build complexity / data:** low-to-medium - mostly curated static
content (a checklist template + real deep links) plus small
Pipeline-UI additions; no scraping, no new data source, but needs
careful, accurate compilation of the actual public-registry links/steps
(not verified here beyond confirming these registries are the ones
already named as "unconfirmed scrapability" in the backlog's Open
Questions section for a *different* purpose - transaction-price data -
this idea only needs their public search UI to exist, not their data to
be scrapable).

### 12. Portfolio mark-to-market tracking for closed Pipeline deals

**What it is:** once a Deal Pipeline entry reaches a "closed/owned"
stage, keep valuing it against the same area's ongoing Area Data trend
(item 15) rather than letting it go stale in the pipeline - a simple
"est. current value based on area trend since purchase" line, clearly
labeled as an estimate, not an appraisal.

**Why this platform specifically:** extends the CRM angle past
"sourcing a deal" into "holding a deal," which is a real gap - today the
Pipeline appears to track deals only up to acquisition, not ongoing
portfolio performance, and the platform already has everything the
math needs (Area Data trend + the deal's own recorded purchase price/
date).

**Build complexity / data:** own-data only, low-to-medium effort (an
extension of existing Area Data aggregation, plus new Pipeline UI for a
"purchase price + date" field on closed deals - not confirmed whether
that field already exists on `PIPELINE_DEALS`, worth checking before
scoping).

---

## Tier 3 - noted, not recommended to prioritize (flagged so nobody re-researches them expecting a different answer)

- **Photo-based condition scoring (multimodal AI).** A real 2026
  industry direction (Zillow's own stated move toward incorporating
  images/floor plans into valuation models) and technically possible
  here since photos are already scraped - but real build complexity is
  high (needs an ML/vision model or a paid third-party vision API, with
  real accuracy risk on scraped, non-standardized photos), and no user
  demand signal for it has been raised. Worth revisiting only if a
  concrete accuracy-tested approach turns up later, not now.
- **Blockchain/NFT-anchored valuation audit trails.** Genuinely surfaced
  in current proptech-trend research as a 2026 direction, but no clear
  investor-facing benefit for this platform's actual users was found -
  flagging so it isn't independently "discovered" again later and
  chased for novelty's sake without a real use case attached.
- **Lifestyle/content marketing city guides** (the Redfin+Rover
  "best cities for dog walks" pattern found during this research). Could
  be adapted with Bulgaria-specific angles, but this is an SEO/content-
  marketing play, not a core product feature - out of scope for this
  brief's "feature" framing.
- **3D/virtual-tour aggregation.** Common on some portals, but it's
  unconfirmed whether any of the 8 source portals this platform scrapes
  even embed 3D tours widely enough to make aggregating them worthwhile
  - would need its own investigation before it's worth scoping, and
  wasn't a strong enough signal from this research pass to recommend
  spending that investigation time now.

---

## Explicitly not re-litigated here (already covered in `docs/backlog.md`)

Per the brief's own instruction to check the backlog first - these
overlap with ideas a first pass might otherwise suggest, and are already
either shipped, scoped, or explicitly answered there, so they're
deliberately not repeated as "new" above:
- Crime-data map, Census-data overlay, Price-vs-income tile, Planning
  Applications, true "Last Sold" (Registry Agency transaction-price)
  data, Bulgarian EPC-equivalent badge - all already listed in the
  backlog's "Open questions" section as uncertain BG-data-substitute
  questions, not fresh findings from this pass.
- Rental yield *from imotenradar's own scraped listings*, Agent
  Properties/Agent panel, floor-level field - already confirmed
  real data gaps (not buildable without new scraper work) in items
  13/14/16 and the Parked section; idea #3 above works around the first
  of these with an external benchmark rather than re-proposing scraping
  rental listings.
- Cross-portal price-divergence flagging, "what changed" digest, saved
  filter presets, comparables, area data, BTL stress test, deal
  calculator strategies, map clustering - all already shipped; ideas #1,
  #2, #3 above are explicitly framed as *extensions* of these, not
  restatements.

---

## Consolidated source list

- [Global Property Guide - Bulgaria rental yields](https://www.globalpropertyguide.com/europe/bulgaria/rental-yields)
- [Global Property Guide - Bulgaria Rental Yields: City-by-City Performance](https://www.globalpropertyguide.com/europe/bulgaria/rent-yields)
- [Zillow - How Zillow spent 20 years teaching AI to understand home value](https://www.zillow.com/news/how-zillow-spent-20-years-teaching-ai-to-understand-home-value/)
- [ELRA - Bulgaria: Limitations to Foreigners](https://www.elra.eu/contact-point-contribution/bulgaria/limitations-to-foreigners/)
- [Advocate Markov - The EU Court allowed foreigners to buy agricultural land in Bulgaria](https://www.advocatemarkov.com/the-eu-court-allowed-foreigners-to-buy-agricultural-land-in-bulgaria/)
- [Investropa - Buying Land as a Foreigner in Bulgaria (2026)](https://investropa.com/blogs/news/bulgaria-foreigners-own-land-really)
- [Henley & Partners - Bulgaria Residence by Investment](https://www.henleyglobal.com/residence-investment/bulgaria)
- [Get Golden Visa - Bulgaria Golden Visa 2026](https://getgoldenvisa.com/bulgaria-golden-visa)
- [Regional Profiles - Municipalities and the Matriculation Exam in Bulgarian - Results](https://www.regionalprofiles.bg/en/news/municipalities-and-the-matriculation-exam-in-bulgarian-results-in-2019/)
- [Regional Profiles - Average NVO math result by municipality](https://www.regionalprofiles.bg/en/news/the-average-result-of-national-external-evaluation-in-mathematics-after-the-seventh-grade-is-weak-2-in-181-municipalities/)
- [Wolf Theiss - New EU rules on short-term rentals (Regulation (EU) 2024/1028)](https://www.wolftheiss.com/insights/new-eu-rules-on-short-term-rentals-what-hosts-platforms-and-investors-need-to-know/)
- [Innovires - Renting Out Property in Bulgaria: Airbnb & Long-Term (2026)](https://innovires.com/tax-residency/blog/renting-property-bulgaria-foreigner.html)
- [Redfin - How Walk Score Works](https://www.redfin.com/how-walk-score-works)
- [Redfin/Rover - Best Cities for Dog Walks](https://www.redfin.com/news/tag/walk-score/)
