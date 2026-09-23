# imotenradar.com - Design Inspiration Round 2 (2026-09-23)

Compiled by Nosy in response to a repeated complaint this session: *"The
overall design and appearance of the website does not come as luxurious
and stylish."* Dessy already completed a site-wide design pass against
`docs/design-guidelines.md` (palette: brass/ivory/ink/taupe; type:
Playfair Display + Inter; philosophy: restraint over decoration,
photography-led, progressive disclosure). This document does **not**
repeat that research or re-derive the palette/type system - it assumes
you've read `docs/design-guidelines.md` in full and is additive to it:
new references, and a small set of concrete, actionable extensions to
what's already specified. Where a recommendation here would mean
deviating from or extending an existing numbered section of
`docs/design-guidelines.md`, that's called out explicitly.

**This is a research document, not an implementation.** Nosy has not
touched `index.html` or any other site file. Everything below is for
Dessy to evaluate and build from.

---

## Sourcing note (read before treating anything below as settled)

All research below is from **WebSearch only**. WebFetch is blocked to
essentially every external domain in this environment - confirmed again
this round on `typza.com` in addition to the sites already confirmed
blocked in `docs/design-guidelines.md` (Sotheby's, Christie's, Knight
Frank, etc.). So nothing below is a first-hand pixel audit of any live
site; it's drawn from search-result summaries, design write-ups, and
case-study pages *about* these sites. Where a design write-up gives a
specific, concrete mechanism (a named typeface, a named UX pattern, a
documented design-system decision), that's presented with more
confidence. Where search results only returned generic marketing
copy ("elegant," "sophisticated," "premium") with no concrete mechanism
behind it, that's flagged as weak and you should treat it as a lead to
verify by visiting the site yourself, not as a finding.

---

## 1. The central tension, stated up front

Almost every "luxury website design" reference that comes up in general
search results is a **single-product or low-density** site: one resort
brand, one fashion house's edit, one architecture firm's portfolio, one
estate agency's flagship listing. Their signature move is nearly always
the same - one enormous photo, very little competing text, lots of
empty space, slow deliberate motion. That move works precisely *because*
there's only one or a handful of things on screen at a time.

imotenradar's actual working screens (search results, saved searches,
comparables) are **structurally the opposite problem**: dozens of
listings on screen simultaneously, each needing enough comparative data
(price, m², price/m², beds, location) for a user to actually shop
between them. A homepage hero can borrow the "one giant photo, almost no
text" move wholesale. A grid of 40 listing cards cannot - doing so would
break the page's actual job. This tension is the organizing idea behind
everything below: each reference is tagged with whether it's directly
usable on a **data-dense working screen** or only on a **low-density
marketing/hero surface**, and recommendations are split accordingly
rather than treated as one undifferentiated "make it more luxurious"
pile.

---

## 2. New real-estate references (closer to imotenradar's actual problem)

These four are more useful than most generic "luxury site" references
because each one, to varying degrees, has to solve the *same* problem
imotenradar has: showing many listings, not one.

### The Modern House (UK, themodernhouse.com)

**What it is:** a boutique UK estate agent specializing in
Modernist/design-led homes, explicitly positioned by reviewers as a
"design-led alternative to Rightmove" - i.e. the same market-positioning
move imotenradar could make against imot.bg/imoti.net.

**What's confirmed by research:** an editorial-first framing - a
"Journal" section of articles/interviews about architecture and design
sits alongside the property listings themselves, not walled off in a
separate "blog" nobody visits; the brand is built around *curation*
(only Modernist/design-led homes, not a general catalog) as much as
visual design.

**Why this is the single most relevant reference in this document:**
it's proof, in the same country and against the same kind of mainstream
portal competitor Property Filter/Rightmove represents, that a listings
business selling into a market with a dominant plain-utilitarian
incumbent *can* read as premium while still showing a real catalog of
many homes - it doesn't have to shrink down to one hero listing per
page to do it.

**Recommendation for Dessy:** consider whether imotenradar's home page
or a dedicated section could carry a light editorial layer - short
written context (a neighborhood note, a market-trend line, an agent's
take) attached to listings or search results, not just raw data. This
is a genuinely new idea beyond what `docs/design-guidelines.md` covers,
and it's **INFERRED/aspirational** - depends on whether imotenradar has
or wants to produce this kind of content at all, and search results
didn't give pixel-level detail on how The Modern House lays this out on
the page. Flag for a second look (ideally a direct site visit) before
committing engineering time to it.

### JamesEdition (jamesedition.com)

**What it is:** a global luxury-goods marketplace (real estate, cars,
yachts, jets) with 200,000+ real-estate listings - genuinely data-dense
at scale, much closer to imotenradar's actual catalog size than a
boutique agency.

**What's confirmed:** personalized search with custom filters, saved
wish lists, and listing alerts; a stated quality-review gate (listings
must meet minimum photo/pricing standards before going live) as a trust
mechanism.

**Honest caveat - do not skip this:** search results also surfaced
genuinely mixed reviews, including complaints about broken/unloaded
photos and a meaningful share of listings reported as stale or
unavailable. This matters for imotenradar specifically because it
aggregates listings from multiple Bulgarian source portals, which
carries the same risk (duplicate, stale, or delisted properties showing
up looking "live"). **Visual polish will not fix that underlying
data-quality problem if it exists** - it's a product/data-pipeline
concern, not a design one, but it's worth flagging here since it
surfaced directly from this research and "luxurious and stylish" can be
undermined fast by a listing that photographs beautifully but turns out
to be six months stale.

**Recommendation for Dessy:** the *filters/wishlist/alerts as a
personalized layer* pattern is worth confirming against
`docs/property-filter-spec.md` (saved searches / alerts sections) -
this is workflow territory, not visual design, so route it there rather
than treating it as a visual-design ask.

### Engel & Völkers (engelvoelkers.com)

**Weakly sourced** - search results returned mostly brand/business
description rather than concrete design mechanism. The one specific
point that came through: a flexible template system letting individual
agent sites carry "bold and dynamic" imagery while staying on-brand.
Not enough here to recommend anything specific; noting it mainly so the
user knows it was checked and came up thin, rather than silently
skipping a well-known name in the category.

### Compass (compass.com) - the density-handling precedent

**What it is:** not marketed as a "luxury" brand per se, but the
largest US residential real-estate platform, and the single most
relevant reference in this whole document for the *density* half of the
tension in section 1 - because Compass's actual product problem (agents
working fast across large volumes of listing data, on web/iOS/Android)
is structurally the same shape as imotenradar's.

**What's confirmed** (via a documented design-system case study, not
Compass's own marketing): the listing card was treated as a first-class
design-system component, explicitly engineered "to accommodate more
information in less space" for a data-dense context; a separate
documented pattern exists for **bulk actions** because "agents deal with
large amounts of data" and had no single consistent way to act on it in
bulk before the system existed.

**Why this belongs here even though Compass ≠ "luxury":** it's the
concrete counter-proof to a wrong instinct - the instinct that "more
luxurious" always means "show less at once." Compass demonstrates that a
data-dense listing platform can be handled with real design discipline
(a documented, consistent card system; a considered bulk-action pattern)
without that discipline requiring low density. **Cite Compass for its
systems discipline, not for its visual aesthetic** - nothing in the
research surfaced Compass's actual color/type choices as something
imotenradar should borrow.

**Recommendation for Dessy:** when the listing card component (section
6 of `docs/design-guidelines.md`) is actually built, treat it the way
Compass's case study describes treating theirs - as a single reusable
component with one documented spec, not something restyled ad hoc
per screen (results grid vs. saved-search list vs. comparables). This
is a build-process recommendation, not a new visual direction; it
reinforces rather than changes what section 6 already says.

---

## 3. Adjacent-category references (marketing/hero surfaces only)

Per section 1's tension, these are strong references for imotenradar's
**homepage hero and individual listing detail hero** - not for the
results grid, saved-searches list, or any screen showing multiple
listings at once.

### Aman Resorts (aman.com)

**What's confirmed:** hospitality-press and brand-identity write-ups
converge on describing Aman's digital presence as "quiet luxury" -
immersive full-bleed photography with no cluttered overlays, sparse
typography, and deliberately slow, minimal interactions (a redesigned
brand identity from studio Construct is cited by name, built around
custom typography and an earthy palette). Aman operates roughly two
dozen resorts worldwide - a genuinely low-density catalog, which is
exactly what makes this move affordable for them.

**Where this translates:** the homepage hero and the listing
detail-page hero, both already called out in
`docs/design-guidelines.md` sections 5 and 7 as places for a single
dominant image. **Concrete extension beyond what's already written
there:** consider a full-viewport-height (not just full-width) hero
image on the homepage, with the search bar rendered as a light,
semi-transparent panel positioned low in the frame over the photo,
rather than a solid boxed panel sitting below/beside it. This is a
genuinely new idea, not something already specified in section 5 (which
currently says the search bar should be "the largest, most inviting
single element" but doesn't specify it sitting *over* a full-height
photo). Flag as a real extension for Dessy to evaluate, not a confirmed
requirement.

**Where this does NOT translate:** the results grid. A 40-card grid
cannot each be "one enormous immersive photo with almost no
surrounding text" without becoming unusable for comparison shopping -
this is the section 1 tension in concrete form.

### Rosewood Hotels (rosewoodhotels.com)

**What's confirmed:** a 2025 redesign explicitly described as blending
"editorial storytelling with seamless functionality" - the stated goal
being to let visitors browse inspirational content *and* transact
(book) in the same flow, not two separate site sections. The rebrand
also introduced a named signature color ("Discovery Green") as a
deliberate brand device.

**Recommendation for Dessy - two small, concrete ideas:**
1. The "browse and transact in one flow" framing is a reasonable model
   for imotenradar's homepage: it already needs to be both an
   inspiration/discovery surface and the entry point into real search -
   this reinforces (doesn't change) the existing section-5 "search bar
   as the primary landing-page element" direction.
2. **Name the accent color.** `docs/design-guidelines.md` section 4
   defines the brass accent by hex range only. Giving it an internal
   name (e.g. something evoking the ivory/brass palette already chosen)
   is a zero-cost, zero-code documentation change that makes the brand
   identity easier to reference consistently across future design work
   - purely a nice-to-have naming convention, not a visual change.

### Mytheresa (mytheresa.com) - the best density-plus-boutique-feel precedent

**What's confirmed by research:** a luxury fashion e-commerce platform
carrying 200+ brands and presumably thousands of SKUs, explicitly
positioned by its own marketing as maintaining "an elevated
boutique-like feel" despite catalog scale, achieved through a "highly
curated edit" framing rather than an exhaustive-catalog framing.

**Caveat:** search results here were largely business-description level
(brand count, market positioning) rather than a pixel-level breakdown of
the actual product grid. The specific mechanisms below are **partly
inferred from general knowledge of the luxury-ecommerce grid genre**,
not confirmed line-by-line from the research - flagged accordingly:

- **CONFIRMED by research:** curation framing ("the finest edit") as the
  substitute for "everything we have" - i.e., positioning even a large
  catalog as a selection, not a dump.
- **INFERRED, not confirmed in the material found:** the specific
  grid mechanics luxury fashion e-commerce sites are generally known
  for - consistent neutral/plain-background product photography across
  every item regardless of source, price and product name set below
  the image in small restrained type rather than overlaid, and
  generous gutter spacing between grid cells even at high item counts.
  These are genre-typical, not something this research run actually
  observed on Mytheresa's live grid.

**Why this matters specifically for imotenradar, more than any other
reference in this document:** imotenradar aggregates photos from
multiple Bulgarian source portals of wildly inconsistent quality, crop
ratio, and original resolution - a problem Mytheresa's studio-shot,
single-source product photography simply doesn't have. **Concrete,
new recommendation:** rather than hard-cropping inconsistent source
photos to force the fixed ratio `docs/design-guidelines.md` section 6
already calls for (which can cut off parts of a building or a room),
consider **letterboxing/padding** photos that don't natively fit the
target ratio with a subtle neutral fill (a muted tone from the taupe
family already in the palette) instead of a hard crop. This preserves
the full source photo while still guaranteeing every card renders at
the same fixed frame size - the "ordered grid" effect section 7 asks
for, achieved without losing photo content. This is a genuinely new
technical/visual recommendation beyond what section 6/7 currently
specify (which only says "pick one ratio and use it everywhere," not
how to handle source photos that don't already fit it).

### Foster + Partners / OMA (architecture firm portfolios)

**What's confirmed:** Foster + Partners' project archive is filtered by
project type (e.g. airport, museum, residential) and reviewers describe
reaching a narrow, specific subset of the portfolio "in three clicks,"
with a minimal, discreet navigation UI (menu items highlight only on
hover, no persistent visual chrome). OMA's site is described as
deliberately editorial, treating written theory/research as
first-class content alongside built projects rather than a separate
section.

**Recommendation for Dessy:** this is a second, independent
(non-real-estate) confirmation of the progressive-disclosure filter
principle already specified in `docs/design-guidelines.md` section 5
("3-4 common filters visible, rest behind a 'More filters' panel") -
it doesn't change that guidance, but it's worth citing to Dessy as
evidence the "get to a narrow result set fast, with almost no visible
filter chrome" pattern works well outside real estate too, and that the
"More filters" trigger itself should stay visually minimal (a text
link/hover state, not a boxed button with an icon and a count badge,
which is the more typical SaaS-dashboard treatment this project is
explicitly trying to avoid per section 9 of the guidelines).

---

## 4. Cross-cutting research: what "looks expensive" mechanically

Several general (non-brand-specific) design-trend write-ups converged
on the same few claims, independent of any specific luxury brand. These
aren't new information relative to `docs/design-guidelines.md`'s
existing direction, but they're useful **independent confirmation** from
a different research angle, and one adds a genuinely new practical point:

- **Typography carries more of the "expensive vs. cheap" signal than any
  other single element**, per multiple independent write-ups - this
  directly reinforces the serif/sans pairing already locked in at
  section 3 of the guidelines; no change needed, just confirms the
  existing call was right.
- **Consistent grid discipline reads as expensive**; one write-up
  specifically credits Apple's site's grid consistency (not its color
  or imagery) as the reason it reads as premium. This reinforces the
  8px spacing system already specified at section 5 - again,
  confirmation, not a new instruction.
- **Restraint is repeatedly framed as active omission** - "the most
  expensive-looking sites are the ones where the most things were
  deliberately left out" - which is exactly the progressive-disclosure
  principle already in the guidelines (section 5), from an independent
  source.
- **New practical point not yet in the guidelines: load performance
  itself is cited as part of the "premium" perception** - a beautiful
  but slow-loading page reads as less professional regardless of visual
  design. This is a genuinely new addition worth flagging to Dessy as a
  concrete build concern, not just a visual one: given imotenradar
  displays many aggregated photos of inconsistent original size per
  section above, a consistent image-compression/lazy-loading pipeline
  for the results grid is itself part of delivering the "luxurious"
  read, not a separate performance concern unrelated to the design
  brief. **This is a recommendation to flag for whoever builds the
  image pipeline, not something Dessy alone can fully own if her scope
  is limited to `index.html`/CSS.**

---

## 5. Explicit "don't import this" list

Things that showed up in research and would actively work against this
project if copied uncritically:

1. **Do not apply the Aman/Rosewood "one enormous hero photo, almost no
   text" move to the results grid, saved-searches list, or comparables
   view.** It's correct for the homepage hero and listing detail-page
   hero only (section 3 above). Applying it to a 40-card grid breaks
   the comparison-shopping task the page exists to do.
2. **Do not strip real estate's filter set down to fashion-e-commerce
   sparseness.** Mytheresa-style luxury e-commerce grids often have very
   few filter dimensions (size, color, brand). Real estate genuinely
   needs more simultaneous filter power (location, price, type, beds,
   and whatever else `docs/property-filter-spec.md` calls for) -
   progressive disclosure (hide most of it behind "More filters") is
   the right move per section 3 above, deleting filter power to match a
   lower-complexity category is not.
3. **Do not treat Compass as a visual-style reference** - it's cited
   here purely for its documented design-systems discipline around
   data-dense components, not for its color/type choices, which
   weren't researched and aren't being recommended.
4. **Do not assume JamesEdition's visual polish is a template to copy
   wholesale** - its own user reviews flag real data-quality complaints
   (broken photos, stale listings) that visual redesign alone wouldn't
   fix. Worth keeping in mind given imotenradar's own multi-portal
   aggregation model carries a similar risk.
5. Everything already listed as an anti-pattern in
   `docs/design-guidelines.md` section 9 still applies and isn't
   repeated here.

---

## 6. Summary of concrete, actionable recommendations for Dessy

In priority order, the genuinely new (not-already-in-`design-guidelines.md`)
items from this document:

1. **Homepage hero: go full-viewport-height** with the search panel as a
   light, semi-transparent overlay low in the frame, rather than a
   boxed panel below/beside the photo (section 3, Aman/Rosewood).
2. **Photo letterboxing instead of hard-cropping** for source photos
   that don't natively match the fixed card crop ratio, using a neutral
   taupe-family fill - solves the "grid of inconsistent aggregated
   photos" problem that pure-luxury single-source-photography sites
   don't have to deal with (section 3, Mytheresa-derived).
3. **Treat the listing card as one documented, reusable design-system
   component from the start**, not restyled per screen (section 2,
   Compass) - a process recommendation, reinforcing rather than
   changing section 6 of the guidelines.
4. **"More filters" trigger should be a minimal text/hover affordance,
   not a boxed button with icon+badge** (section 3, Foster + Partners) -
   reinforces guidelines section 5/9, adds a concrete UI-treatment
   detail.
5. **Consider a light editorial layer** (neighborhood notes, market
   commentary) attached to listings or search results, if content
   resources allow - flagged clearly as aspirational/inferred, needs a
   second look before any build commitment (section 2, The Modern
   House).
6. **Name the brass accent color** internally for brand-documentation
   consistency - zero-cost, no visual change (section 3, Rosewood).
7. **Flag image-pipeline performance (compression, lazy-loading) as
   part of the luxury brief**, not a separate concern, and route it to
   whoever owns that layer if it's outside Dessy's own scope (section
   4).

Everything else in this document is context/reasoning for *why* these
seven items are recommended, plus explicit warnings (section 5) about
what not to copy from the same research.

---

*This document is additive to `docs/design-guidelines.md`, which remains
the canonical implementable spec (palette hex values, type scale,
component-level rules, anti-pattern list). Nothing here overrides it;
where the two might read as in tension, `docs/design-guidelines.md`'s
existing numbered sections are the base and this document's
recommendations are proposed extensions to specific sections, called
out as such throughout.*
