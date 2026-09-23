# Deal Calculator - strategy formulas (Bulgarian market)

Companion to `docs/property-filter-spec.md` section 8 and `docs/backlog.md`
item 18 ("Deal Calculator (investment strategy modeling)"). Property
Filter's own screenshots never showed a populated calculator, so the spec
left every strategy's input fields and math **INFERRED**. This document
replaces those inferences with real, standard real-estate-investment
formulas, adapted to Bulgarian-market inputs, so a builder can implement
the Deal Calculator directly from it.

**Author's note on scope:** this is independent financial-modeling
research, not a further Nosy capture pass. The formulas below are
well-established real-estate-investment mathematics (cap rate,
cash-on-cash return, GDV/residual valuation, BRRR "cash left in deal",
etc.) - not invented for this doc - cross-checked against the sources
listed in "Formula sources" at the bottom. The Bulgarian-market
*defaults* (tax rates, mortgage terms, STR licensing) were verified via
web research as of September 2026 and are cited inline; **a human
(ideally a Bulgarian real-estate lawyer/accountant/mortgage broker)
should sanity-check every BG-specific legal, tax, and rate figure below
before this becomes load-bearing for a real financial calculator that
investors act on.** Treat the formulas (the math) as solid; treat the
default numbers (tax %, rates, fees) as "best available as of writing,"
not live/authoritative data - the calculator should make every one of
them user-editable, exactly as the existing BTL Stress Test does.

---

## 0. Currency correction: BGN -> EUR

The backlog task that motivated this doc assumed BGN as Bulgaria's
currency. That is now out of date: **Bulgaria adopted the euro on 1
January 2026** (fixed conversion rate 1.95583 BGN = 1 EUR); the lev
ceased to be legal tender on 1 February 2026. imotenradar's own codebase
already reflects this - every listing field in `index.html` is
`price_eur` (`price_per_sqm`, etc.), not `price_bgn`. **All formulas and
UI fields below use EUR**, matching the rest of the app. Where a cited
source still quotes BGN (e.g. the ~10 BGN/bed STR registration fee),
this doc gives the EUR-equivalent using the fixed rate for reference,
and the actual calculator should just take today's real fee in EUR from
the relevant authority.
[Bulgaria adopts the euro (ECB)](https://www.ecb.europa.eu/euro/changeover/bulgaria/html/index.en.html)

---

## 1. Shared Bulgarian-market building blocks

These feed every strategy below. All should be editable "Preferences >
Deal Calculator Templates" defaults (backlog item 18's own Preferences
sub-tab), never hardcoded.

### 1.1 Property transfer / acquisition costs ("closing costs")

Bulgaria has no UK-style Stamp Duty. The equivalent bundle of one-off
purchase costs is:

| Cost | Typical range | Notes |
|---|---|---|
| Municipal property transfer tax (местен данък при придобиване на имот) | 0.1% - 3% of the higher of declared price or tax valuation | Set per municipality; Sofia is at the top of the range, 3% |
| Notary fee | ~0.4% - 1.5% of transaction value (banded, degressive at higher prices), + 20% VAT on the fee | Set by the Notary Fees Tariff, degressive by price bracket |
| Registry Agency entry fee | 0.1% of price | Flat, nationwide |
| **Total, typical rule of thumb** | **~3% - 4.5% of price** | Excludes agent commission and legal fees if separately engaged |

Suggested default input: **"Transfer tax + closing costs %"**, default
**3.5%**, user-editable per municipality - this directly replaces
Property Filter's UK "Stamp Duty" default field (per backlog item 19's
"Deal Calculator Templates defaults" sub-tab, shipping with item 18).

Sources: [Innovires - Local Taxes and Fees in Bulgaria 2026](https://www.innovires.com/en/blog/mestni-danaci-taksi-imot-mps.html), [Investropa - Sofia property taxes/fees](https://investropa.com/blogs/news/sofia-property-taxes-fees)

### 1.2 Mortgage / financing defaults

| Parameter | Typical BG value (2026) | Notes |
|---|---|---|
| LTV, owner-occupier | up to 85% | Banks typically cover 70-85% of appraised value |
| LTV, buy-to-let / investment | ~70% (illustrative default already used by the shipped BTL Stress Test - see section 2) | Lower than owner-occupier terms is standard industry practice; not a quoted bank rate |
| Interest rate (EUR-denominated) | ~2.5% - 4.5% / year | Rates below 60% LTV price ~0.2-0.5pp lower; above 80% LTV price higher + mandatory insurance |
| Rent-cover rule of thumb | rental income should cover >= ~80% of the mortgage installment (soft underwriting guideline, not a hard ICR figure) | Distinct from the UK-style ICR stress-test convention already implemented (section 2) - both are legitimate framings; the calculator should keep the existing ICR-based test as the default since it's already shipped and working |

Sources: [Pirotska/Unistroy - Mortgage rates in Bulgaria 2026](https://pirotska.bg/en/article/mortgage-rates-bulgaria-2026-fixed-variable-how-to-choose), [Votchina - Mortgage programs in Bulgarian banks 2026](https://votchina.eu/en/mortgage-programs-in-bulgarian-banks-598-3.html)

### 1.3 Standard amortizing-loan monthly payment

Needed wherever a strategy needs an actual repayment (not interest-only)
mortgage payment (e.g. ongoing BTL/BRRR cash-flow after refinance):

```
r = (annual_interest_rate / 100) / 12        // monthly rate
n = loan_term_years * 12                     // number of monthly payments
M = P * (r * (1 + r)^n) / ((1 + r)^n - 1)    // standard amortization formula
```

Where `P` = loan principal. This is the standard mortgage-amortization
formula (any finance textbook / calculator).

---

## 2. BTL (Buy-To-Let) - extends the shipped Stress Test

**Status: mostly already implemented.** `index.html`'s
`computeBtlStressTest()` (backlog item 15, shipped) already contains
real, working affordability-stress-test math:

```js
loanAmount        = price * (ltvPct / 100)
monthlyRate       = (interestPct / 100) / 12
monthlyInterestOnly = loanAmount * monthlyRate
minRentToPass     = monthlyInterestOnly * (icrPct / 100)
maxPriceToPass    = monthlyRent / ((ltvPct/100) * monthlyRate * (icrPct/100))
```

This is the standard UK/EU lender "Interest Cover Ratio" (ICR)
buy-to-let stress test (rent must cover the interest-only payment by a
multiple, typically 125-145%) - it is not UK-specific math, only the
label/convention, so it's correctly kept as-is with BG defaults.

**What the Deal Calculator's BTL strategy adds on top** (new fields, not
yet in the Stress Test tab):

| Output | Formula |
|---|---|
| Gross Rental Yield (%) | `(monthlyRent * 12 / price) * 100` |
| Net Rental Yield (%) | `((monthlyRent * 12 - annualOperatingCosts) / price) * 100` |
| Annual Operating Costs | sum of: property management fee (typical 8-12% of rent if managed), maintenance/repairs reserve (~1% of price/year is a common rule of thumb), insurance, void-period allowance, HOA/building maintenance (Bulgarian condo etazhna sobstvenost fee) |
| Cap Rate (%) | `(NOI / currentMarketValue) * 100`, where `NOI = annual rent - annual operating costs` (excludes debt service - unlike net yield above it's valued against current/refinanced value, not necessarily purchase price - same number as Net Rental Yield when using purchase price, diverges post-refinance) |
| Monthly cash flow (€) | `monthlyRent - monthlyMortgagePayment(amortizing, from 1.3) - monthlyOperatingCosts` |
| Total cash invested | `deposit (price * (1 - ltvPct/100)) + closingCosts (1.1) + any pre-let refurb/furnishing cost` |
| Cash-on-Cash Return (%) | `(annualCashFlow / totalCashInvested) * 100` |

Formula sources: [Wall Street Prep - Cash-on-Cash Return](https://www.wallstreetprep.com/knowledge/cash-on-cash-return/), [New Silver - Cash-on-Cash Return Calculator](https://newsilver.com/cash-on-cash-return-calculator/)

---

## 3. BRRR (Buy, Rehab, Rent, Refinance)

**Inputs:** purchase price, closing costs % (1.1), rehab/renovation
budget, after-repair value (ARV, user-estimated - imotenradar has no
BG comparable-sales dataset to auto-estimate this, same "never fabricate
a number the app can't back" rule the shipped BTL tab already follows),
initial purchase financing (cash or bridging loan + rate), refinance LTV
%, refinance interest rate %, refinance loan term (years), monthly rent
post-refinance, monthly operating costs.

**Outputs / math:**

```
totalCashInvestedUpfront = purchasePrice + closingCosts + rehabCost
                            (+ bridging-loan interest, if used, over the
                              hold period before refinance)

refinanceLoanAmount = ARV * (refinanceLtvPct / 100)
                       // BG buy-to-let/investment refinance LTV ceilings
                       // are commercially similar to the 70-75% ARV cap
                       // commonly used as the standard cash-out-refinance
                       // convention - same ceiling this doc uses for BTL
                       // (1.2); treat as an editable default, not a fact.

cashReturnedAtRefinance = refinanceLoanAmount - anyBridgeLoanPayoff

cashLeftInDeal = totalCashInvestedUpfront - cashReturnedAtRefinance
                 // the BRRR strategy's defining metric: the goal is to
                 // drive this toward zero (or negative = cash pulled OUT)

monthlyMortgagePayment = amortization(refinanceLoanAmount, refinanceRate,
                                       refinanceTermYears)   // see 1.3

monthlyCashFlow = monthlyRent - monthlyMortgagePayment - monthlyOperatingCosts

annualCashFlow = monthlyCashFlow * 12

Cash-on-Cash Return (%) =
    if cashLeftInDeal > 0:  (annualCashFlow / cashLeftInDeal) * 100
    if cashLeftInDeal <= 0: report as "infinite" / "all capital returned"
                            (the textbook BRRR outcome - a
                            self-financed rental with none of the
                            investor's own money left in it)

Post-refinance Cap Rate (%) = (NOI / ARV) * 100   // NOI as in section 2
```

Formula source: [AssetBaseline - BRRRR Calculator methodology](https://assetbaseline.com/calculators/brrrr-calculator/) (standard "cash left in deal" / cash-on-cash-post-refinance convention, cross-checked against the general BRRRR literature).

---

## 4. FLIP (Buy, Refurb, Sell)

**Inputs:** purchase price, closing costs % (1.1), renovation budget,
holding-period financing cost (bridging-loan interest over the expected
hold period, or opportunity cost of cash), holding costs during the
project (utilities, condo fees, insurance, council/property tax pro-
rated), expected resale price, selling costs % (agent commission -
typically 2-3% in Bulgaria, plus any resale notary/legal costs).

**Outputs / math** (matches the strategy-output field names Property
Filter's own screenshots already showed for FLIP, per spec section 8):

```
Total Project Costs = purchasePrice + closingCosts + renovationBudget
                       + holdingCosts + financingCost

Total Cash Needed  = deposit-or-full-cash-portion + renovationBudget
                      + closingCosts + holdingCosts + financingCost
                      // i.e. Total Project Costs minus any purchase-
                      // financing loan principal that isn't the
                      // investor's own cash

Gross Profit (Potential Profit) = expectedResalePrice
                                    - (expectedResalePrice * sellingCostsPct/100)
                                    - Total Project Costs

ROI (%) = (Gross Profit / Total Cash Needed) * 100
```

This is the standard flip-ROI formula (profit measured against cash
actually deployed, not total project cost, since some of the project
cost may be borrowed).

---

## 5. BTSA (Buy-To-Serviced-Accommodation / short-term let)

Same purchase/financing math as BTL (section 2), with rental income
modeled as short-term/nightly rather than a fixed monthly lease, plus
short-term-rental-specific operating costs.

**Additional inputs:** average nightly rate (€), expected occupancy %
(annual average - Bulgarian coastal/mountain resort towns swing
seasonally, so an "average annual occupancy %" rather than a flat
monthly figure is the honest input), cleaning cost per turnover,
booking-platform commission % (Airbnb/Booking typically ~15-18%
combined host+guest fees, or ~3% direct-channel), STR
registration/categorization cost (see section 8's legal note - a real,
required annual/one-off cost in Bulgaria, not optional).

```
Annual Gross STR Revenue = nightlyRate * 365 * (occupancyPct / 100)

Annual STR Operating Costs = (Annual Gross STR Revenue * platformCommissionPct/100)
                              + (turnovers/year * cleaningCostPerTurnover)
                              + utilities (higher than long-term let - guest-paid)
                              + STR registration/categorization fee (see this
                                section's legal/licensing note below)
                              + standard BTL operating costs (management, HOA, insurance)

NOI = Annual Gross STR Revenue - Annual STR Operating Costs

Gross STR Yield (%) = (Annual Gross STR Revenue / price) * 100
Net STR Yield (%)   = (NOI / price) * 100
Cash-on-Cash Return (%) = as in section 2, using STR NOI instead of
                          long-term rent
```

**Legal/licensing note (see section 8 below):** short-term rental in
Bulgaria requires formal categorization as an accommodation place
("места за настаняване, клас Б") under the Tourism Act, with a
per-bed registration fee and platform-side registration-number
verification - this is a real, mandatory input line item, not a
business-model nicety, and should be a required cost field the
calculator forces the user to fill in (same "never silently omit a
real cost" principle as the shipped BTL tab's required-rent field).

---

## 6. BRSAR (Buy, Refurb, Serviced-Accommodation, Refinance)

This is BRRR (section 3) with the post-refinance income model swapped
for BTSA's short-term-rental math (section 5) instead of a long-term
lease. Concretely:

```
[same as BRRR section 3 through refinanceLoanAmount / cashLeftInDeal]

monthlyCashFlow = (Annual Gross STR Revenue / 12) - monthlyMortgagePayment
                  - (Annual STR Operating Costs / 12)

[same Cash-on-Cash Return / "infinite" handling as BRRR]
```

No new formula concepts - it is the direct composition of sections 3
and 5, which is exactly why Property Filter models it as its own named
strategy rather than forcing users to combine two calculators manually.

---

## 7. R2R (Rent-To-Rent)

No purchase - the investor takes a head lease from the property owner
at an agreed monthly rent, then sublets it (long-term, often
room-by-room in a shared house / "co-living" model) at a higher
aggregate rent. Margin is the spread.

**Legal basis in Bulgaria (researched, not inferred):** under the
Obligations and Contracts Act (ZZD), a tenant **may sublet by default
unless the head lease expressly forbids it** - the opposite default from
some other jurisdictions. The original tenant (the R2R investor) remains
personally liable to the head landlord regardless of the subletting
arrangement. This means the R2R mechanism is **structurally legal in
Bulgaria without any special licensing**, subject to: (a) the head
lease not containing a no-subletting clause (a real, checkable
contract-negotiation input, not a legal blocker), and (b) ordinary
residential subletting is not itself commercially regulated the way
short-term/tourist accommodation is (contrast with R2SA, section 8's
note). Source: [Bulgarian law of obligations - lease of immovable property](https://www.bulgaria-law-of-obligations.bg/rent-movable-immovable-property.html), summarized further at [Innovires - Rental Agreement Bulgaria 2026](https://www.innovires.com/en/blog/rental-agreement-bulgaria.html).

**Inputs:** head-lease monthly rent (paid to owner), any deposit/
guarantee paid to owner, setup/refurb cost (furnishing, safety
compliance, room partitioning if applicable), sublet income per room/
unit and number of rooms/units, void allowance %, management/admin
cost, contract length (years) - R2R margins are typically modeled over
the lease term since there's no property purchase to amortize.

```
Total Monthly Sublet Income = sum(perRoomRent * numberOfRooms)
                               * (1 - voidAllowancePct/100)

Monthly Margin = Total Monthly Sublet Income - headLeaseMonthlyRent
                  - monthlyOperatingCosts (utilities if landlord-inclusive,
                    management, maintenance)

Setup Capital = ownerDeposit + refurbCost + first month's head rent
                (as working capital)

Cash-on-Cash Return (%) = (Monthly Margin * 12 / Setup Capital) * 100

Annualized Margin over contract term = Monthly Margin * 12 * contractYears
                                        - Setup Capital
```

---

## 8. R2SA (Rent-To-Serviced-Accommodation)

Same head-lease structure as R2R (section 7), but the sublet is run as
short-term/serviced accommodation instead of long-term subletting -
i.e. combine R2R's head-lease economics (7) with BTSA's nightly-rate
income model (5):

```
Total Monthly STR Sublet Income = (Annual Gross STR Revenue from
                                    section 5's formula) / 12

Monthly Margin = Total Monthly STR Sublet Income - headLeaseMonthlyRent
                  - Annual STR Operating Costs/12 (section 5, including
                    the STR registration/categorization cost)

[same Cash-on-Cash Return / Setup Capital math as section 7]
```

**Legal/licensing note - this is the strategy where Bulgarian regulation
actually bites, unlike plain R2R:**

- Short-term/tourist letting in Bulgaria requires the unit to be
  registered and categorized as an accommodation place - apartments,
  rooms and houses let for overnight stays fall under **"места за
  настаняване, клас Б"** (accommodation, class B) under the Tourism
  Act, with an application + a per-bed fee (reported as ~10 BGN/bed,
  i.e. ~€5.11/bed at the fixed euro conversion rate).
- Online platforms (Airbnb, Booking.com, etc.) are required to verify
  listings' registration numbers and delist unregistered ones; new
  2026 legislation tightened this further, with a compliance grace
  period before fines/enforcement.
- **Whether the head-lease *owner* will consent to this** (both to
  subletting at all, and specifically to running it as a registered
  short-term-rental business out of their unit) is a separate,
  real-world negotiation point on top of the legal default described
  in section 7 - R2SA operators typically need explicit owner buy-in
  even where plain subletting wouldn't require it, since categorizing
  someone else's unit as commercial short-term accommodation is a more
  material change of use than an ordinary sublet.
- This licensing/registration cost and process should be a required
  input in the calculator (a cost line + a checkbox/confirmation that
  categorization has been or will be obtained), the same way the
  shipped BTL tab treats monthly rent as a required, non-defaulted
  field.

**Bottom line for the "is this viable in Bulgaria" business question
flagged in the backlog:** short-term rental itself is legal and fairly
common in Bulgaria (Black Sea coast, ski resorts, Sofia/Plovdiv
city-break markets), but it is **regulated, not a legal gray area** -
it requires formal registration/categorization with a real fee and
platform-enforced compliance. R2R (long-term subletting) is legally
simpler than R2SA (short-term/serviced) specifically because of this
categorization requirement. This is a factual regulatory picture, not
a recommendation - the go/no-go on building R2R/R2SA/BTSA/BRSAR into
the Deal Calculator remains the user's business call, per the backlog.

Sources: [KGK law firm - 2026 Airbnb/Booking rule changes](https://kgk.bg/blog/novi-pravila-za-airbnb-i-booking-prez-2026-kakvo-tryabva-da-znaete/), [Innovires - Hotel and guest-house categorization in Bulgaria](https://www.innovires.com/en/blog/kategorizacia-hotel-kashta-gosti.html), [Investor.bg - Bulgarian parliament passes Airbnb/Booking legislation](https://www.investor.bg/a/451-balgariya/295215-deputatite-prieha-zakonodatelstvoto-sreshtu-airbnb-i-booking)

---

## 9. COM2RESI-TOSELL (Commercial-to-Residential conversion, sell by units)

Property Filter's own saved-template screenshot already named this
strategy's exact output fields (spec section 8): *Gross Development
Value, units buildable, Total Cost of Build with Finance, Deposit,
Equity Released, Equity %, Return on Capital, ROI.* These map cleanly
onto the standard property-development "residual appraisal" method used
industry-wide - here is the real math behind each named field.

**Inputs:** commercial property purchase price, closing costs % (1.1),
change-of-designation/conversion permit cost (see legal note below),
construction/conversion cost per m² buildable, total buildable m²
(or unit count x average unit m²), professional fees % (architect,
engineer, project management - typically 8-15% of build cost),
contingency % (typically 5-10% of build cost), development finance
amount and rate/term, expected sale price per unit (or per m²),
target developer profit % (of GDV or of cost - user-selectable, both
are standard conventions).

```
Gross Development Value (GDV) = sum(unitSalePrice) across all units
                                 = unitsBuildable * avgSalePricePerUnit

Total Build Cost = (buildCostPerSqm * totalBuildableSqm)
                    + professionalFees (% of build cost)
                    + contingency (% of build cost)

Total Cost of Build with Finance = Total Build Cost
                                    + purchasePrice + closingCosts
                                    + conversionPermitCost
                                    + developmentFinanceInterest
                                      (loanAmount * rate * termYears,
                                       interest-only during the build,
                                       the standard development-finance
                                       convention)

Deposit = investor's own cash portion of the purchase + build
          (i.e. Total Cost of Build with Finance - developmentFinanceLoanAmount)

Equity Released (at practical completion, via refinance/sale of first
units) = value unlocked once completed units are worth more than their
build cost - i.e. (GDV of completed/sold-so-far units) - (Total Cost of
Build with Finance attributable to those units)

Equity % = (Equity Released / GDV) * 100

Gross Profit = GDV - Total Cost of Build with Finance

Return on Capital (%) = (Gross Profit / Deposit) * 100
                         // return measured against the investor's own
                         // cash in, i.e. the same cash-on-cash logic as
                         // every other strategy above, applied to a
                         // development project

ROI (%) = (Gross Profit / Total Cost of Build with Finance) * 100
          // return measured against total cost, i.e. "return on cost" -
          // the standard secondary developer metric alongside Return on
          // Capital
```

This is the standard property-development "residual value" / GDV
appraisal method (GDV minus build cost, fees, finance, and profit = the
maximum viable land/purchase price, or conversely GDV minus actual
costs = actual profit once a price is fixed) - not adapted from a
UK-specific mechanism, it is generic development finance.

**Legal/regulatory note - Bulgarian change-of-use procedure:** converting
a commercial unit/building to residential use in Bulgaria requires a
**"промяна на предназначението" (change of designation)** permit from
the municipality's chief architect. Since a 2021 amendment to the
Territorial Planning Act, conversions that don't involve construction
work have a simplified permitting path; conversions that do involve
construction/structural work go through the fuller permit process
(notification of investment proposal, possible environmental-impact
opinion, notarized consents from co-owners/condominium assembly where
applicable, and sign-off from relevant authorities). This is a real,
budgetable line item (permit fees + professional fees to prepare the
application) and a real timeline risk (permitting duration), not a
blocker - Bulgaria has a working legal mechanism for this, unlike
Title Split (below).

Sources: [Concordia Legal - Change of designation/status of a property under ZUT](https://concordialegal.bg/promiana-statut-prednaznachenie-na-nedvijim-imot/), [LandTech - Residual land value method](https://land.tech/blog/how-to-value-land-for-development-residual-value-and-planning-risk-landtech), [Investment Property Partners - GDV guide](https://investmentproperty.co.uk/property-investment-resources/gross-development-value-gdv-property-developers-guide-to-financial-appraisals/)

---

## 10. Assisted Sale (Add Value & Sell)

A lighter-touch cousin of FLIP (section 4): typically light cosmetic/
staging work plus active sale management (rather than a full renovation
project), often used when helping a distressed/motivated seller
maximize their sale price for a fee or profit-share, rather than the
investor buying the property outright.

**Inputs:** current unimproved market value (or the seller's likely
achievable price as-is), cost of value-add works (staging, minor
repairs, marketing/photography, legal/agent fees), expected improved
sale price, and - because this strategy can be structured either as
the investor buying then reselling, *or* as a fee/profit-share
arrangement with the existing owner - a "deal structure" input that
picks which cost base applies.

```
// Structure A: investor buys outright, same math as FLIP (section 4),
//              typically with a smaller renovationBudget and shorter
//              holding period than a full FLIP.

// Structure B: profit-share / assisted-sale-for-a-fee (investor never
//              takes title):
Value Uplift = expectedImprovedSalePrice - currentUnimprovedValue
Net Uplift   = Value Uplift - costOfValueAddWorks - agent/legalFees
Investor's Share = Net Uplift * agreedProfitSharePct/100
                    (agreedProfitSharePct is a negotiated deal term,
                     not a formula - the calculator should just take it
                     as an input)
ROI (%) = (Investor's Share / costOfValueAddWorks) * 100
          // ROI measured against the investor's own outlay only, since
          // no purchase price was paid under Structure B
```

The calculator should let the user pick Structure A vs. B up front
(a "do you take title?" toggle), since the cost base and therefore the
ROI denominator differ materially between them - this is the one
strategy where Property Filter's own single "Assisted Sale" label
plausibly covers two different real-world deal structures, and no
screenshot confirmed which one Property Filter itself models, so both
are documented here rather than guessing.

---

## 11. PLO (Purchase Lease Option) - remains genuinely open, no formula written

Per the backlog, this needs Bulgarian legal confirmation before a
formula is written, and that has **not** been resolved by this doc -
only researched enough to explain *why* it's still open:

- A UK "lease option"/PLO structure typically combines (a) a lease
  giving the investor immediate control/income rights over the
  property, with (b) a separate, binding option to purchase later at a
  price fixed today, often paid for with a small option fee, letting
  the investor profit from both rental income and price appreciation
  without an immediate full purchase.
- Bulgarian contract law's closest native mechanism is the
  **preliminary contract (предварителен договор)** for the sale of
  real estate: it is mandatory in written form, typically paired with
  a ~10% deposit, and gives the buyer time to arrange financing before
  completion at the notary - but a preliminary contract does **not**
  itself grant the buyer occupation, income rights, or a property
  interest the way a PLO's lease component does; it is a promise to
  complete a sale, not a lease-with-an-option.
- Bulgaria's general contract-law framework (Obligations and Contracts
  Act) is flexible enough that a lawyer could likely *draft* something
  combining a lease with a standalone option-to-purchase clause, but
  this research did not find an established, commonly-used Bulgarian
  legal product equivalent to the UK PLO the way the preliminary
  contract is an established equivalent to a UK exchange contract, nor
  confirmation of how enforceable a "pure option" (bind the seller,
  not the buyer) would be in Bulgarian courts if the seller tried to
  walk away and sell to someone else during the option period.
- **Recommendation: do not build a PLO formula until a Bulgarian
  real-estate lawyer confirms (a) whether a lease-plus-option structure
  is enforceable in the way UK PLOs rely on, and (b) what it would cost/
  require to draft one.** This is exactly the kind of legal-structure
  question a formula can't paper over - a made-up PLO calculator would
  produce numbers for a deal structure that might not hold up in a
  Bulgarian court, which is worse than not offering the strategy at
  all. This remains an **open question for the user**, not a technical
  blocker.

Source used to assess the closest BG mechanism: [Ruskov & Kollegen - Preliminary contract for purchasing real estate in Bulgaria](https://ruskov-law.eu/bulgaria/article/preliminary-contract-purchasing-real-estate.html), [lawfirm.bg - Preliminary contract in Bulgaria: Main aspects](https://lawfirm.bg/en/publications/preliminary-contract-in-bulgaria-main-aspects)

---

## 12. Title Split - Hold / Title Split - Sell - confirmed drop, no formula needed

Already flagged as a likely drop in the spec; this research confirms it
more specifically rather than just leaving it as "no known BG
equivalent":

UK title splitting exists because a single freehold building's units
often don't have their own separate registered titles until an investor
deliberately splits them out. **Bulgaria doesn't have this problem in
the first place**: multi-unit residential buildings in Bulgaria are
built and registered under the condominium ownership regime (**етажна
собственост**, "floor/horizontal ownership"), under which each
apartment already gets its own individual property title at
construction/first-sale time, with common areas (stairwells, roof,
land) held in shared co-ownership automatically. There is no separate
"split the title" transaction to perform - and where a *building* isn't
yet legally divided into separately-titled units (e.g. a commercial
building being converted), the relevant Bulgarian mechanism is the
change-of-designation/conversion process already covered under
COM2RESI-TOSELL (section 9), not a distinct "Title Split" strategy.

**Recommendation: keep this dropped, as the backlog already states** -
this isn't a gap needing a BG substitute, it's a UK-specific problem
that doesn't exist in the Bulgarian system.

---

## Formula sources (general reference, beyond the inline citations above)

- Cash-on-cash return, cap rate: [Wall Street Prep - Cash on Cash Return](https://www.wallstreetprep.com/knowledge/cash-on-cash-return/), [New Silver - Cash-on-Cash Return Calculator](https://newsilver.com/cash-on-cash-return-calculator/)
- BRRR "cash left in deal" / refinance ARV convention: [AssetBaseline - BRRRR Calculator](https://assetbaseline.com/calculators/brrrr-calculator/)
- GDV / residual development appraisal: [LandTech - Residual value and planning risk](https://land.tech/blog/how-to-value-land-for-development-residual-value-and-planning-risk-landtech), [Investment Property Partners - GDV guide](https://investmentproperty.co.uk/property-investment-resources/gross-development-value-gdv-property-developers-guide-to-financial-appraisals/)
- Bulgarian transfer tax / notary / registration fees: [Innovires - Local Taxes and Fees in Bulgaria 2026](https://www.innovires.com/en/blog/mestni-danaci-taksi-imot-mps.html), [Investropa - Sofia property taxes and fees](https://investropa.com/blogs/news/sofia-property-taxes-fees)
- Bulgarian mortgage rates/LTV 2026: [Pirotska/Unistroy - Mortgage rates in Bulgaria 2026](https://pirotska.bg/en/article/mortgage-rates-bulgaria-2026-fixed-variable-how-to-choose), [Votchina - Mortgage programs in Bulgarian banks 2026](https://votchina.eu/en/mortgage-programs-in-bulgarian-banks-598-3.html)
- Bulgarian subletting default rule: [Bulgaria - Law of Obligations - Lease of immovable property](https://www.bulgaria-law-of-obligations.bg/rent-movable-immovable-property.html)
- Bulgarian short-term-rental categorization/registration: [KGK - 2026 Airbnb/Booking rule changes](https://kgk.bg/blog/novi-pravila-za-airbnb-i-booking-prez-2026-kakvo-tryabva-da-znaete/), [Innovires - Hotel/guest-house categorization](https://www.innovires.com/en/blog/kategorizacia-hotel-kashta-gosti.html)
- Bulgarian change-of-designation (change of use) procedure: [Concordia Legal](https://concordialegal.bg/promiana-statut-prednaznachenie-na-nedvijim-imot/)
- Bulgarian preliminary-contract convention (for the PLO assessment): [Ruskov & Kollegen](https://ruskov-law.eu/bulgaria/article/preliminary-contract-purchasing-real-estate.html), [lawfirm.bg](https://lawfirm.bg/en/publications/preliminary-contract-in-bulgaria-main-aspects)
- Bulgaria euro adoption (currency correction, section 0): [ECB - Bulgaria joins the euro area](https://www.ecb.europa.eu/euro/changeover/bulgaria/html/index.en.html)
