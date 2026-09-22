# Property Filter spec - for imotenradar.com's redesign

Compiled by Nosy from 34 screenshots the user captured while logged into
their own Property Filter account (UK property-search / deal-sourcing
tool), plus ordinary public-web background research on Property Filter's
marketing material. No gated part of Property Filter was accessed by
Nosy directly - everything below is transcribed from material the user
supplied, or is explicitly marked as inferred.

**Purpose:** imotenradar.com should match Property Filter's *workflow*
and *information density* per listing, adapted to Bulgarian data. This
is not a request to clone Property Filter's visual design, wording, or
branding - see the closing "Design direction" section.

**How to read this document:** each screen/feature is (1) described,
(2) classified as **Bulgarian-replicable** or **UK-only-dependent**
(with a suggested BG substitute where one plausibly exists), and
(3) flagged **INFERRED** wherever Nosy is inferring behavior rather than
having it directly confirmed in the material supplied. Everything not
marked INFERRED was directly observed in a screenshot as described by
the user.

---

## 0. Account / plan context

Observed directly from Account Settings screens, not the public
marketing/pricing page.

- Three-tier plan structure: **Explorer** (entry) -> **Investor** (mid,
  "MOST POPULAR") -> **Deal Maker** (top, "GET EVERYTHING"). The user is
  on Investor, £99+VAT/month.
- Each tier gates *quantities*, not features: number of Saved Searches
  (Lead Generators), number of Postcodes searchable, number of Saved
  Properties, number of DTV Letter Campaigns, plus tier-specific
  community/training perks (Deal Clinic Call, Ask The Community,
  Investment Strategies Trainings on Investor; Deal Making Call, Deal
  Exchange Space, Offer & Negotiation Systems on Deal Maker).
- Billing: monthly invoices, single card on file, UK billing address.

**Classification:** the tiered-quantity-gating *model* (not the specific
numbers or UK community perks) is replicable if imotenradar ever wants
paid tiers - this is a generic SaaS pattern, not UK-specific data. The
community/training content itself (Deal Clinic Calls, podcasts) is
Property-Filter-brand content, not something to copy.

**Gap - not supplied:** the public marketing/pricing page and the
sign-up/onboarding flow were not captured. If those matter for the
redesign, a separate capture pass is needed - this was flagged as a
checklist item and never followed up.

---

## 1. Home dashboard (post-login landing)

Three-column layout under a global "Find your next deal" search bar:

1. **"Start Here" card** - an onboarding checklist/progress tracker (5
   tasks: save a search as a Lead Generator, add a property to the
   pipeline, add a note/link/tag, create a deal calculator, organise a
   viewing) plus an embedded tutorial video. Purpose: get a new user to
   touch every major feature once.
2. **"Lead Generators" card** - "New motivated sellers to look at": a
   scrollable list of every saved search, each row showing a green
   "total matches" badge and an orange "new since last check" badge,
   clickable through to that generator's results.
3. **"Pipeline Actions" card** - "X properties to check": one row per
   pipeline stage with a live count, clickable through to that stage's
   filtered view.

**Classification: fully Bulgarian-replicable.** This is a workflow
pattern (recent activity + saved-search inbox + pipeline summary), not
data-dependent. Recommend as the imotenradar landing page once saved
searches and a pipeline exist.

**INFERRED:** the exact wiring of "new" counts to a "last checked"
timestamp per generator is inferred from the badge behavior described in
Preferences > Notifications (section 9 below), not shown as an isolated
event in this screen's screenshot.

---

## 2. Lead Generators list (saved searches)

A grid of cards, one per saved search ("Lead Generator"):

- Small static map thumbnail with the search's geographic boundary
  drawn on it.
- Two count badges (green = total matches, orange = new/unchecked).
- Name, a short filter summary (price range, bed count, property types,
  For Sale/To Rent tag).
- "Check Leads" button (opens the results list for that saved search).
- Icon row: duplicate, edit, share, delete.
- Sale-type tag row.
- Toolbar above the grid: sort by "Max Property to Check", tabs
  All / For Sale / To Rent / For Sale & To Rent.
- "Add New Lead Generator" card at the end of the grid (entry point to
  create a new saved search).
- User has ~18 saved searches, several are near-duplicates of the same
  area with slightly different filters (a real usage pattern worth
  designing for: users iterate on filter variants of the same region).

**Classification: fully Bulgarian-replicable.** Saved-search-as-a-card,
with a map thumbnail and a new-vs-total badge pair, maps directly onto
imotenradar's existing city/area-based listings - no UK-only data
involved. The "duplicate" action (clone a saved search to tweak it) is a
small but clearly load-bearing UX detail worth keeping.

---

## 3. Deal Pipeline (kanban board)

- Horizontal stage tabs with live counts, arrow-shaped dividers implying
  flow/sequence: Do Due Diligence -> Organise a viewing -> Make an offer
  -> Follow up -> Offer Accepted. (Stage names/icons are user-editable,
  see Preferences > Pipeline, section 9.)
- Toolbar: Sort and Filter, Tags:All, Lead Generator:All, Agent:All,
  address search box, and Card/Table/Map/Export view toggles.
- Property cards, each showing:
  - Status ribbon (Available / Withdrawn / Back / STC / Sold) with a day
    count, e.g. "Available 28 Days".
  - Price-change ribbon when relevant (e.g. "Reduced -7% (34 days)",
    "Increased 50% (4 days)").
  - Listing date, photo, a small action-icon row + tag icon.
  - Price, price/m², address with a verified checkmark, property type +
    tenure.
  - A 2x3 icon grid of stats: beds, floor area, EPC letter, floor level,
    a distance/other stat, a yield-like %.
  - A colored sale-type pill at the bottom (For Sale = white, To Rent =
    orange).

**Classification: mostly Bulgarian-replicable, one UK-only field.**
The pipeline itself (configurable stages, kanban cards, multi-view
toggle, filtering by tag/generator/agent) is a pure workflow pattern -
fully replicable. Card contents:
- Status/price-change ribbons, listing date, photo, price, price/m²,
  address, beds, floor area, floor level, distance: **replicable**,
  imotenradar already tracks most of these.
- **EPC letter: UK-only dependent.** UK Energy Performance Certificates
  (A-G bands) are a specific national scheme. Bulgaria has its own
  mandatory energy performance certification (сертификат за енергийна
  ефективност, A-G-ish bands under the national energy-efficiency
  scheme) for buildings above a certain age/size - if imotenradar's
  scraped listings ever expose this, it's a plausible substitute;
  otherwise this field should be omitted rather than faked.
- **Verified-address checkmark: INFERRED meaning.** Not explained
  in any screenshot; assumed to mean "address confirmed/geocoded" by
  analogy to similar tools. Needs confirmation before treating as a
  spec'd feature, or omit and revisit.
- **Yield-like %** on the card: likely a rental/BTL yield estimate
  (ties to the Market Data / Stress Test tooling below) -
  **replicable in principle** if imotenradar has or estimates average
  rents per area, but the exact formula was not shown on this card, only
  inferable from the separate Yield tooling in section 5's Area Data tab
  and section 7. **INFERRED formula.**

---

## 4. Comparables tool (standalone, top-level nav)

A postcode-search-first tool, independent of any single listing:

- Postcode search box + radius dropdown (This postcode only / Postcode
  sector / Postcode district / Within 1/4 mile / 1/2 mile / 1 mile) +
  Search button.
- Live map (OpenStreetMap-based) with a red road-highlight overlay and a
  toggleable "Display HMO Article 4" layer.
- Property-type filters in 3 checkbox groups (house subtypes, bungalow
  subtypes, other: flat/studio/room/HMO), each group with its own
  "select all" master checkbox.
- Numeric ranges: Bedrooms (min/max), Price Range For Sale (min/max),
  Surface Area m² (min/max).
- EPC filter: single-select pills A-G + Unknown.
- Property Tenure filter: pill toggle No filter/Freehold/Leasehold/
  Unknown.
- A clearly-labeled divider: "FILTERS FOR ONLINE ADVERTS ONLY - NOT
  AFFECTING LAST SOLD DATA", under which sit: Auctions (Yes/No/Only
  auctions), Build type (No filter/Existing/New build), Property Purpose
  (All Other/Retirement homes/Care home/Listed building/Shared
  Ownership).
- Empty state: "Please run search to display a result" until a postcode
  is searched.

**Classification: mostly Bulgarian-replicable, several UK-only fields.**
- Postcode-radius search: **UK-only mechanism, BG substitute exists.**
  UK postcodes are small, precise geographic units with defined
  "sector"/"district" hierarchies. Bulgaria doesn't have an equivalent
  fine-grained postcode system in common real-estate use; the direct
  substitute is imotenradar's existing city/quarter (кв.) + radius-in-km
  search, which already serves the same "search this area at this
  granularity" purpose.
- Property-type checkboxes, bedroom/price/size ranges, tenure pill:
  **replicable**, standard listing attributes (Bulgarian tenure concept
  is simpler - effectively always freehold-equivalent ownership, so a
  Freehold/Leasehold toggle likely doesn't apply in Bulgaria and should
  probably be dropped rather than mapped).
- **EPC filter: UK-only, same BG substitute note as section 3** (use
  Bulgarian energy-efficiency certificate bands if/when scraped data
  supports it; otherwise omit).
- **"HMO Article 4" layer: UK-only, no BG substitute known.** This is a
  UK planning-law overlay (areas requiring planning permission to
  convert a property into a House in Multiple Occupation). Nosy is not
  aware of a Bulgarian planning-law equivalent worth mapping this to -
  flag as UK-only with no known substitute, drop rather than force-fit.
- **"Last Sold Data" concept (Land Registry): UK-only, BG substitute
  exists but is weaker.** The divider explicitly distinguishes "online
  adverts" from "last sold" data, implying the UK Land Registry feeds a
  parallel dataset of actual transaction prices, separate from asking
  prices. Bulgaria's equivalent would be the Имотен регистър (Registry
  Agency's property register) / cadastral data (Кадастър), but Nosy does
  not know whether transaction-price data from it is realistically
  scrapable/available the way UK Land Registry data is (UK publishes
  sold-price data openly; Bulgarian equivalents are not known to be as
  openly published). **Flag as open question for imotenradar's data
  team, not a resolved substitute.**
- Auction / Build type / Property Purpose filters: **replicable as
  generic listing attributes** if Bulgarian listings expose them (new
  build vs. resale is common; auction and "retirement home/care home"
  categories are less likely to be common in BG data and may not be
  worth building).

---

## 5. Individual listing detail page

The single most information-dense screen in Property Filter - this is
the main benchmark for imotenradar's own listing detail redesign.
Header persists across all 7 tabs below: back arrow, full
address+type+price title, Prev/Next navigation through the current
result set, a summary strip (thumbnail with status/price ribbons, price,
price/m², date, address, beds/area/EPC/floor icon row), and a right-side
action rail: current pipeline stage, a prominent "+ Take an action"
button, Wait/Hide buttons, "Create Share Link", "Copy Data for AI".

**Classification (rail-level):** Prev/Next paging through a result set,
pipeline-stage indicator + action button, Wait/Hide, and shareable links
are all **fully replicable workflow patterns**, no data dependency.
"Copy Data for AI" is a plain-text/structured export of the listing for
pasting into an external LLM tool - **replicable**, low effort, worth
keeping as a nice small feature.

### Tab: Advert Details

- **Multi-portal badge row**: shows the SAME physical property as
  advertised by up to 6 different named agents/portals simultaneously,
  each with its own "Listed on: [date]", currently-viewed source
  highlighted. This is Property Filter's cross-portal listing-matching/
  deduplication surfaced as a feature, not hidden.
  **Classification: fully Bulgarian-replicable, and imotenradar likely
  already has the underlying data** (it aggregates multiple Bulgarian
  portals already per the repo's stated purpose) - this tab is arguably
  the single highest-value feature to prioritize, since it turns
  imotenradar's existing multi-portal scraping into a visible,
  differentiating feature rather than a background deduplication step.
- **Price & Status History**: a step-chart, one line for price over
  time, background color-coded by status band (Available=green,
  STC=yellow, Removed=pink). **Replicable** - imotenradar's scrapers
  already track price and status over time per the backlog notes on
  relisting/price-drop detection; this is a visualization of data
  already being collected.
- **Floorplan & Pictures panel**: floorplan image + scrollable photo
  carousel + "Download pictures" button. Floorplan: **UK-only in
  practice** (floorplans are a near-universal UK listing convention;
  much rarer in scraped Bulgarian portal data) - **replicable only if
  source portals provide one**, treat as optional/conditional field, not
  a guaranteed one. Photo carousel + download: **fully replicable**.
- **Due Diligence panel** - the densest single panel, several fields
  UK-only:
  - Bed/bath/garage icons, floor area: **replicable**.
  - **CT Band (Council Tax Band): UK-only, weak/no BG substitute.**
    UK council tax bands (A-H) are a property-value-banding system for
    local taxation. Bulgaria's closest analog is the local "данък
    сгради" (building tax) which is assessed differently (per declared
    tax value, not a public band lookup) and Nosy does not know of a
    public, scrapable per-property banding system in Bulgaria. Flag as
    UK-only, no confirmed substitute.
  - "Existing Extension" tag, Construction age (date range):
    **replicable** if source data includes build year/renovation info.
  - **Energy Rating (EPC) with colored badge + "Estimated EPC
    improvement costs" (£ range): UK-only**, same substitute note as
    above (Bulgarian energy certificate if available); the "improvement
    cost estimate" sub-feature is UK-scheme-specific financial modeling
    Nosy has no BG equivalent for - would need a Bulgarian energy-
    retrofit cost benchmark to replicate, likely not worth building
    initially.
  - Feature Rating: **INFERRED, unclear what this scores** - not
    explained in the material given, needs clarification before
    speccing further.
  - "Last building use known" (date + value, e.g. "Owner occupier"):
    **UK-only, no confirmed BG substitute known** - likely sourced from
    Land Registry transaction history.
  - Nearby amenities list with icons + distances (town centre, station,
    supermarket, hospital, school): **fully replicable**, standard POI-
    distance data available via any mapping API for Bulgarian addresses
    too.
  - Owner (company/individual name, clickable): **UK-only, no BG
    substitute** - sourced from UK Land Registry / Companies House data
    (public ownership records at this level of detail are not something
    Nosy is aware of as being similarly public/scrapable in Bulgaria).
  - "HMO Article 4 area: yes/no": **UK-only, no BG substitute**, see
    section 4.
  - Registered Lease (years remaining), Restrictive covenant, Title
    (Land Registry title number, clickable): **UK-only, no BG
    substitute** - these are all UK Land Registry / leasehold-system
    concepts. Bulgarian property is overwhelmingly freehold-equivalent,
    so "years remaining on lease" and "restrictive covenant" likely
    don't apply; the closest Bulgarian analog to a "Title number" is a
    cadastral identifier (идентификатор по Кадастъра), which could be
    surfaced as a reference/lookup field if available, but this is a
    much thinner substitute than the UK title-number ecosystem (no
    equivalent one-click ownership/covenant history behind it that Nosy
    is aware of).
  - Each of the last several rows has a chevron implying an expandable
    detail panel - **INFERRED** that these expand to show more detail;
    not seen expanded in the material given.
- **Agent panel**: logo, name, phone (tel: link), address, "See agent's
  other properties" button, "Add note" link. **Fully replicable** - this
  maps directly onto Bulgarian agent/agency data already present in
  scraped listings.
- **Property Details & Keywords panel**: Property Type, Tenure (pill),
  Sale Feature tags (Investment/Auction/Empty), Property Feature tags
  (Parking/Garage), "Close By" tags (Public transport/Commuter
  routes/Local shops/Good car links/Park) - these read as auto-extracted
  keyword tags from the free-text listing description.
  **Classification: fully replicable, high value.** This is an NLP/
  keyword-extraction pattern applicable to Bulgarian listing descriptions
  with no UK-specific dependency - genuinely one of the better features
  to prioritize since it's pure text-processing on data imotenradar
  already has (description text), not a new data source.
- **Description panel**: full text + "See More" expand. **Replicable**,
  trivial.
- Small embedded map with Show more/Open Map: **replicable**.
- "Property Details Walkthrough" tutorial video widget (dismissible):
  **replicable as a UX pattern**, content would need to be built fresh
  for imotenradar, not copied.
- "Report a bug for this advert" -> "Send a message" link: **replicable**,
  simple user-flagging of bad data, useful given imotenradar is scraper-
  based and will have data-quality issues too.

### Tab: Deal Making

- **Actions and notes panel**: inline pipeline-stage selector (current
  stage highlighted, next stage shown greyed as "Or..."), "Take action"
  button, Tags/Quick Note/Links each with an inline "Add" link, a
  timestamped activity log (e.g. "Added to pipeline Do Due Diligence"
  with edit/delete icons). **Fully replicable**, pure workflow.
- **Deal calculator panel**: empty state + "Create" button, links to the
  strategy-based calculator (section 8). **Replicable in structure**;
  the specific strategies themselves are UK-investment-method-specific,
  see section 8's classification.
- **Viewing Pictures panel**: empty state "No pictures added yet" + Add
  button - a place for the USER's own viewing photos, distinct from the
  listing's marketing photos. **Fully replicable**, simple file-upload
  feature.

### Tab: Maps

Icon rail switches the main viewer between 7 layers, each rail icon
showing a small live thumbnail preview:
- **Street View** (Google Street View embed): **replicable**, Google
  Street View has real coverage in Bulgarian cities (coverage quality in
  smaller towns is a real-world risk worth flagging, but the feature
  itself is not UK-specific).
- **Title Plans** (boundary/parcel map): **UK-only concept as named**
  (Land Registry title boundaries), but a **direct BG substitute
  exists**: Bulgaria's cadastral map (Кадастрална карта, publicly
  viewable via the Agency of Geodesy, Cartography and Cadastre) provides
  parcel boundaries - this is a genuinely good substitute, worth
  prioritizing if imotenradar can integrate it.
- **Satellite**: **fully replicable**, generic map layer.
- **Amenities** (POI map): **fully replicable**.
- **Crime** (crime-data map): **UK-only in practice, BG substitute
  uncertain.** UK police.uk crime data is public, open, and geocoded at
  a fine grain. Nosy is not aware of an equivalent public, geocoded
  crime dataset for Bulgaria at comparable granularity - flag as
  UK-only with no confirmed substitute; would need confirmation from
  whoever has BG public-data knowledge before attempting.
- **Postcode** (postcode-boundary map): **UK-only mechanism**, same as
  section 4 - substitute with Bulgarian city/quarter (кв.) boundaries if
  imotenradar has or can source that shape data.
- **Census Data** (census overlay): **UK-only in practice, BG substitute
  uncertain.** Bulgaria's National Statistical Institute (NSI) does
  publish census data, but Nosy does not know whether it is available at
  a fine enough geocoded granularity, or in a similarly easy-to-overlay
  form, to replicate this directly - flag as open question, not a
  confirmed substitute.

**INFERRED:** the exact content/detail of each map layer beyond what's
described above (e.g. what specifically the Amenities map shows besides
"POIs") is inferred from the layer name and thumbnail description, not
seen in an expanded/interacted state.

### Tab: Area Data

Three-column layout, heaviest data-analysis tab:

- **"[Postcode] - Market Live Data" panel**: filtered to match the
  current listing's bed count + type, showing Est. Postcode Yield / Est.
  Property Yield with a gradient gauge bar (both "Not Enough Data" in
  the example shown - worth noting this state exists and needs a graceful
  empty state in the BG build too), a For Sale vs. To Rent comparison
  block (avg asking price, avg days available, avg days STC/time to
  relet), a historical line chart (Yield / [other metric] dropdown), and
  an "Open Market Live Map" button.
  **Classification: replicable**, this is aggregate stats over
  imotenradar's own already-scraped listings for an area, not a UK-only
  data source - the postcode-based scoping would map to city/quarter
  scoping.
- **"[Postcode] - Last Sold Data" panel**: three histograms (price
  distribution, £/m² distribution, m² size distribution), each with the
  SUBJECT property's own value marked as a labeled pointer against the
  distribution, filtered by type/beds/date range/EPC, "Open Last Sold
  Map" button.
  **Classification: partially replicable.** The histogram-with-subject-
  marker visualization pattern is fully replicable using imotenradar's
  own asking-price data. The underlying "Last Sold" (actual transaction
  price, not asking price) data source is the same UK Land Registry
  dependency flagged in section 4 - open question whether a Bulgarian
  equivalent transaction-price dataset is realistically obtainable.
  Recommend building this panel against imotenradar's own asking-price
  data first (fully achievable now), and treating a true "last sold"
  version as a stretch goal pending data availability.
- **"Planning applications" panel**: link-out "Check history" button,
  content not shown beyond that. **UK-only, no BG substitute confirmed**
  - UK planning applications are published per-council in a standardized,
  often API-accessible way; Nosy does not know of an equivalent public,
  structured Bulgarian municipal planning-application database. Flag as
  open question.
- **"LHA Rates" panel** (Local Housing Allowance by bedroom count: HMO/
  1-4 bed, showing Yield % and, for one row, Allowance £/month and
  £/year): **UK-only, no BG substitute known.** LHA is a UK social-
  housing/benefits rent-cap scheme; Nosy is not aware of an equivalent
  Bulgarian government rent-benchmark dataset. Likely just drop this
  panel rather than force a substitute.
- **"Buy To Let - Stress Test" panel**: A/B pass-toggle, collapsible
  Parameters, "Minimum Rental Income Per Month To Pass" / "Maximum Price
  Offer To Pass" outputs, disclaimer to confirm with a lender/broker.
  **Classification: replicable as a generic mortgage-affordability
  calculator**, the underlying math (LTV, interest rate, rent-cover
  ratio) is not UK-specific, only the specific default assumptions
  (UK mortgage products/rates) would need Bulgarian-market defaults
  (BG mortgage rates, typical LTV terms). Worth building since it's pure
  calculation, not a data-source dependency.

### Tab: Comparables

Same tool as the standalone Comparables nav item (section 4), but
pre-scoped to the current listing's location + type. Adds: a filter-
summary bar ("3 Properties found and 1 last sold"), status-count pills
(For sale: Available/STC/Removed + counts, Last sold(Land reg) + count;
To rent: Available/Removed + counts), sort/date filters, "Has pictures
only" toggle, running averages (avg price, avg surface area, avg
price/m²), Card/Table/Map view toggle + export icon. Cards show date,
photo, price, price/m², address, type/tenure, bed/area/EPC icons, and
distance from the subject property.

**Classification:** inherits section 4's classification field-by-field.
The "distance from subject property" per-card computation and the
running-average summary bar are **fully replicable** generic patterns.
The "Last sold(Land reg)" count pill specifically inherits the Land-
Registry-dependency flag from section 4 - would simply not appear (or
show 0) in a Bulgarian build unless a transaction-price data source is
found.

### Tab: Send Letter

- **"Letters Campaign" panel**: pre-filled delivery address from the
  listing (change-address link), editable addressee name (default "The
  Homeowner"), "Add to Letter Campaign" button.
- **"DTV Letters Generator" panel** (labeled "AI Powered by ChatGPT"):
  "Open the letters template generator" button - a second, AI-assisted
  letter-writing path distinct from the templated campaign system
  (section 6).

**Classification: fully Bulgarian-replicable, no UK dependency.**
Direct-mail-to-owner outreach ("Direct To Vendor" / motivated-seller
letters) is a workflow, not a data source - the postal system and
letter-writing conventions differ slightly (Bulgarian addresses, name
conventions) but nothing here is UK-only. This is a genuinely portable
feature if imotenradar wants to pursue a deal-sourcing angle, not just a
listings aggregator.

### Tab: Get Finance

A lead-gen/partner-referral form: "Secure your Decision in Principle
below. Get Your Finance Agreed Today" - fields "What type of finance are
you looking for?" (dropdown), "How will you fund the property
purchase?" (text), Next button.

**Classification: UK-only in its current form (broker-partner
integration), but the workflow pattern is replicable.** "Decision in
Principle" is a UK mortgage-specific term/process. If imotenradar wanted
an equivalent, it would need a Bulgarian mortgage-broker partner and
Bulgarian-appropriate finance-type options (Bulgarian mortgage product
types differ) - this reads as a partner-integration/monetization
feature more than a core workflow feature, lowest priority of the 7
tabs. **INFERRED** that this is a partner integration rather than
Property Filter's own product, based on the "Secure your Decision in
Principle" phrasing and generic lead-capture form shape - not confirmed
by any explicit "powered by" label in the material given.

---

## 6. Send Letters (campaign management, top-level nav)

Distinct from the per-listing Send Letter tab - this is the campaign
management system. Three sub-tabs plus a persistent "Send yourself a
free letter" CTA in the header:

- **Campaigns tab**: a "Draft" campaigns table (Addresses count, Letter
  Design used, Review-And-Send action, Batch Cost) and an "Active"
  campaigns table (adds Next Batch Cost, Batch Delivered e.g. "1/4",
  **Responses** - a response-tracking count, Delivery Dates
  Last/Next). "Create a new campaign" button. An embedded onboarding
  video panel.
- **Letter Designs tab**: 2-step wizard (Design -> Name). Step 1
  "Template": a bank of Property Filter's own pre-written templates as
  pills, each keyed to a specific motivated-seller SITUATION (General,
  Back on the market, Long time sold STC, Low EPC, Multiple Agents,
  Price Reduced, R2R guaranteed rent, Short Lease, Withdrawn, Long time
  on the market), plus "Your Templates"/"Create my own". A "Letter
  Sequence & Timing" section shows a multi-touch drip sequence ("4
  Letters", expandable). A "Content" section has per-letter tabs
  (Letter 1-4, each with a preview icon) and a rich-text editor with
  insertable tokens ({property_address}, {phone_number},
  {email_address}, presumably {homeowner_name}) and a live line-count
  (e.g. "22/28 lines").
- **Property Lookup tab**: empty state - a reverse address-lookup tool
  so that when a seller calls back, the user can pull up which
  letter/campaign that address belongs to.

**Classification: fully Bulgarian-replicable, high-value workflow.**
Nothing here depends on UK-only data - it's a mail-merge/CRM-style
campaign system layered on top of listing addresses, which imotenradar
already has. The situation-keyed template bank
(Back-on-market/Price-Reduced/Withdrawn/Long-time-on-market/Multiple-
Agents) is a particularly good pattern to copy conceptually: it ties
directly to signals imotenradar's scrapers already detect (relisting,
price drops, days-on-market) - i.e. the letter templates should trigger
off the same motivation signals already computed for the motivation
score. The "Low EPC" and "Short Lease" templates are the only two
situation types in the bank that are UK-only-dependent (EPC per earlier
notes; "Short Lease" doesn't apply to Bulgarian freehold-dominant
ownership) - the other 8 situation types transfer directly.

---

## 7. Market Data hub (top-level nav, grid of tool tiles)

Three sections:

- **"Postcodes Live Data"**: Strategy Heat Map, Postcode Performance
  (BTL performance), Market Live Map (Yield/Asking Prices/Time On
  Market/Demand), Adverts Evolution (stock changes: Available-STC-
  Removed over time), Postcode Prices Trend (marked "Soon", not yet
  released even in Property Filter itself), Agent Properties (find all
  properties of a given agent).
- **"Sold Prices Data"**: Last Sold Map, Price vs Income (house-price-
  to-income ratio in an area).
- **"Due Diligence"**: Title Boundaries Map, Planning Applications,
  Stress Test (standalone version of the per-listing calculator), Census
  Data, Planning Constraint Map (badged "HMO Article 4").

**Classification (tile by tile):**
- Strategy Heat Map, Postcode Performance, Market Live Map, Adverts
  Evolution, Agent Properties: **fully replicable**, all built purely
  from imotenradar's own scraped listing history (price, status,
  time-on-market, agent) aggregated by area - no UK-only data needed.
  Genuinely good candidates given imotenradar already has the raw data.
- Postcode Prices Trend: **replicable** (and notably not even shipped by
  Property Filter yet - low pressure to prioritize).
- Last Sold Map, Price vs Income: **partially UK-only.** Last Sold Map
  inherits the Land Registry dependency (section 4). Price vs Income
  needs a Bulgarian regional-income dataset as the substitute input -
  Bulgaria's NSI does publish regional average income/salary data
  publicly, which is a plausible substitute, though Nosy hasn't verified
  its granularity matches what this tile needs.
- Title Boundaries Map: **UK-only concept, BG substitute exists** - same
  as the Title Plans map layer (section 5), substitute with Bulgarian
  cadastral map data.
- Planning Applications: **UK-only, no confirmed BG substitute** - same
  flag as section 5's Area Data tab.
- Stress Test: **replicable**, see section 5's classification.
- Census Data: **UK-only in practice, BG substitute uncertain** - same
  flag as section 5's Maps tab.
- Planning Constraint Map (HMO Article 4): **UK-only, no BG
  substitute** - same flag as section 4.

---

## 8. Deal Calculator (investment-strategy modeling)

Reached via Preferences > Deal Calculators Templates, or via the
per-listing "Create" button (Deal Making tab). A 3-step wizard: choose a
strategy -> choose a template (optional) -> choose a name. 12 strategy
options, each a distinct UK property-investment method: BTL (Buy To Let
- Long term Let / HMO), BRRR (Buy Refurb Rent Refinance), BTSA (Buy To
Serviced Accommodation - Short term Let), BRSAR (Buy Refurb Serviced
Accommodation Refinance), FLIP (Buy Refurb Sell), R2R (Rent To Rent),
R2SA (Rent To Serviced Accommodation), PLO (Purchase Lease Option),
COM2RESI-TOSELL (Commercial to Residential Conversion, sell by units),
Assisted Sale (Add Value & Sell), Title Split - Hold, Title Split -
Sell. Legal disclaimer that figures are guidance only.

Saved templates are shown as result-summary cards with strategy-specific
output metrics (e.g. FLIP: Total Project Costs / Total Cash Needed /
Potential Profit / ROI; COM2RESI-TOSELL: Gross Development Value / units
buildable / Total Cost of Build with Finance / Deposit / Equity
Released / Equity % / Return on Capital / ROI), each with edit/
duplicate/delete and a "go to linked property" link where applicable.
"My templates" (reusable, not tied to a property) and "Linked to
properties" (saved against one specific listing) are separate sections.

**Classification: mixed - the mechanism is replicable, several specific
strategies are UK-market-specific.**
- The overall mechanism (pick a strategy, get a strategy-specific
  calculator with its own output metrics, save as a reusable template or
  link to a specific property) is **fully replicable** and a strong
  pattern to adopt regardless of which strategies are included.
- **Title Split - Hold / Title Split - Sell: UK-only, likely not
  replicable.** "Title splitting" relies on the UK Land Registry's
  ability to register separate freehold/leasehold titles for units
  within one building - Nosy is not aware of an equivalent legal
  mechanism readily available in the Bulgarian property-registration
  system; would need Bulgarian legal confirmation before attempting,
  flag as likely drop.
- **PLO (Purchase Lease Option): UK-only-leaning.** Relies on a
  leasehold/option-contract convention common in UK property law; unclear
  applicability to Bulgarian contract law - flag as uncertain, would need
  Bulgarian legal confirmation, not a confident drop or keep.
- BTL, BRRR, BTSA, BRSAR, FLIP, R2R, R2SA, COM2RESI-TOSELL, Assisted
  Sale: the underlying financial *mechanics* (purchase cost, refurb
  cost, financing cost, rental/resale income, ROI) are **generic and
  replicable** with Bulgarian-market default assumptions (Bulgarian
  mortgage rates/LTV, Bulgarian rental yields, Bulgarian
  renovation-cost benchmarks) substituted for UK ones. Whether "Rent To
  Rent" and "Serviced Accommodation" strategies are common/legal enough
  in the Bulgarian market to be worth building is a market-fit question
  outside Nosy's scope, not a data-availability one - flag as a business
  decision for whoever prioritizes the backlog, not a technical
  blocker.

**INFERRED:** the exact calculation formula behind each strategy's
output metrics was not shown (only labeled output fields were visible in
the screenshots) - replicating the *math* precisely would require either
further screenshots of a populated/expanded calculator or independent
financial-modeling work, not just this spec.

---

## 9. Preferences (settings) - 8 sub-tabs

- **Display**: Surface Metric (Meters(m²), implying a Feet² option
  exists), Distance Metric (Miles, implying Km exists), Menu Collapse
  toggle, Global site zoom % stepper, Property Card Size % stepper with
  a live-rendering preview card. **Fully replicable** - and notably,
  Bulgaria already uses metric units natively (m², km), so imotenradar
  doesn't even need the unit-toggle complexity Property Filter has to
  support (UK still commonly uses miles) - one less thing to build.
- **Search Results**: "Motivated Seller Banner" thresholds (days
  Available/New/STC, each also feeding a "Waiting for Changes"
  notification) - this is the mechanism behind the "Available X Days"
  ribbons on cards (section 3). **"Motivation Indicators"** section
  (min/max range pairs): Difference from Last Sold Price (%), Lease
  Remaining Years, £/m², BTL Yield (%), Below Average Postcode Price
  (%). **This is a direct, near-exact analog of imotenradar's own
  existing motivation-score feature** (per the backlog's 5-component
  formula: relisted, distinct reductions, size of drop, days on market,
  below area average) - confirms Property Filter scores motivation on
  materially the same kind of signals imotenradar already computes, with
  two UK-only exceptions: "Difference from Last Sold Price" inherits the
  Land Registry dependency (section 4), and "Lease Remaining Years"
  doesn't apply to Bulgaria's freehold-dominant market. The other three
  (£/m², BTL Yield, Below Average Postcode Price) map directly onto
  imotenradar's existing computed fields. Also: default sort +
  Sourcing Stage filter for saved-search results, a note that "Quick
  Search results always show all properties," a save-confirmation popup
  toggle, pagination (15-100 cards/page). **All replicable.**
- **Lead Generator**: default sort/filtering/postcode for saved
  searches, "Enable advanced filters" toggle, "Clear local data" link.
  **Fully replicable** (substitute postcode default with a
  city/quarter default).
- **Pipeline**: pipeline stage names AND icons are fully user-editable,
  with per-stage "Remove this step" and an "Add a pipeline step" - i.e.
  the pipeline is an arbitrary-length, user-configurable stage list, not
  a fixed 5 steps (important detail: don't hardcode 5 stages in the BG
  build). Default pipeline sort/filter options, "Show only properties
  with action to take" toggle. A full custom-tag system (name, icon
  picker, color swatch, delete) usable across both Pipeline and Lead
  Generator contexts - user has 12+ custom tags in active use.
  **Fully replicable**, no UK dependency, and the "pipeline stages are
  user-configurable, not fixed" detail is worth calling out explicitly
  to whoever builds this so it isn't accidentally hardcoded.
- **Notifications**: explains the underlying mechanism for both the
  pipeline "Waiting For Change" auto-return-to-stage + top-right
  notification behavior (triggered by status change, time-on-market
  threshold, or price change), and the Lead Generator "new" badge
  increment behavior (section 1/2). **Fully replicable** - this is the
  spec for how the "orange new-count badge" and "Available X Days
  ribbon" mechanisms actually work, useful to have documented precisely
  for whoever implements the BG equivalent.
- **Deal Stacker**: Stress Test defaults (LTV %, Interest Rate %, ICR %)
  feeding the Stress Test tool's default assumptions. **Replicable**,
  substitute UK mortgage-rate defaults with Bulgarian ones.
- **Calendar**: default calendar view, Google Calendar connect, iCal
  feed link - for viewing/follow-up appointments booked via the
  Pipeline. **Fully replicable**, generic calendar integration.
- **Letters**: default addressee email/phone/name ("The Homeowner"),
  company logo upload, footer image upload - populate the letter
  templates' tokens; sorting/display defaults for Property Lookup and
  letter-status views. **Fully replicable**, no UK dependency.
- **Deal Calculators Templates**: default Stamp Duty setting (a
  UK-specific property-purchase tax, dropdown defaulted to "None" in the
  example) presumably auto-applied to calculator strategies; plus the
  My Templates / Linked-to-Properties management screens (section 8).
  **UK-only field flagged: Stamp Duty.** Bulgarian substitute: Bulgaria
  levies a местен данък at property transfer (typically ~2-3%, set per
  municipality) plus notary fees - a "Default transfer tax %" setting is
  a reasonable direct substitute for this one field.

---

## Gaps - on the original checklist but not supplied in this batch

These were requested but the 34 screenshots supplied don't cover them.
Listed explicitly so nothing is silently gap-filled or assumed:

1. **Public marketing/pricing page** - not captured (only the logged-in
   Account Settings billing view was). Needed if imotenradar wants to
   compare Property Filter's *pitch*, not just its in-app workflow.
2. **Sign-up / onboarding flow** (before first login) - not captured.
3. **Mobile / responsive view** of any screen - all 34 screenshots
   appear to be desktop; no confirmation of how (or whether) Property
   Filter adapts this density for mobile. Given imotenradar's own users
   likely include mobile visitors, this is a real gap worth a follow-up
   capture if a mobile-first pass is planned.
4. **Alert emails** (as opposed to in-app notifications) - Preferences >
   Notifications explains in-app behavior only; whether Property Filter
   also emails users about new leads or status changes wasn't shown.
5. **Export file contents** - Card/Table/Map/**Export** view toggle
   appears on both the Pipeline (section 3) and Comparables (section 5)
   screens, but no exported file (CSV/PDF/etc.) was itself captured, so
   its exact contents/format are unknown.
6. **Empty/error states beyond the two shown** - only two empty states
   were captured (Comparables' "Please run search to display a result"
   and Property Lookup's empty state); no validation-error state (e.g.
   an invalid postcode, a save-limit-reached error tied to the plan
   tiers in section 0) was shown.
7. **Any expanded chevron/detail panel** in the Due Diligence panel
   (section 5) - each row (Energy Rating, Owner, Title, etc.) implies an
   expandable detail but none were shown expanded.
8. **Deal Calculator's actual input form and formulas** - only the
   strategy-selection step and saved-result summary cards were shown,
   not a populated calculator mid-entry, so the specific input fields
   and math behind each strategy's outputs are unknown (see section 8's
   INFERRED note).

---

## Design direction for the Bulgarian build

Everything above describes Property Filter's *workflow* and
*information density* to match - not its visual skin. Property Filter's
own look is a fairly plain, utilitarian blue/white SaaS interface with
dark maroon accent buttons: functional, not premium.

imotenradar's redesign should replicate the workflows and per-listing
information density documented above, but should not look like a copy
of Property Filter, and should read as more luxurious/premium than
Property Filter's own current style. A direction (not a finished design)
for whoever builds it: richer typography (a serif or high-contrast
display face for headings rather than a default system sans), more
generous whitespace and spacing between listing-card elements instead of
Property Filter's dense utilitarian packing, a refined and restrained
color palette in place of Property Filter's flat blue/maroon (e.g. deep
neutral tones with a single considered accent, rather than a bright
primary-blue SaaS palette), and subtle elevation/shadow and rounded
surfaces on cards instead of flat bordered boxes. The goal is the same
depth of information per listing and the same saved-search / pipeline /
comparables workflow shape, presented with a calmer, higher-end visual
language than Property Filter's own.

---

*This spec is ready to be broken into backlog items - that decision and
the prioritization of it belong to Bossy, not to this document.*
