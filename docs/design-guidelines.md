# imotenradar.com - Visual Design Guidelines

Compiled by Nosy, expanding the short "Design direction for the Bulgarian
build" closing section of `docs/property-filter-spec.md` into a
standalone, implementable design brief. This document is about *how the
site should look and feel*, not what it should do - see the spec for
workflow/feature direction. Nosy does not write code or produce final
visual assets; this is a direction document a designer/builder should be
able to implement from without having to guess at what "classy and
luxurious" means in practice.

**Sourcing note:** direct WebFetch access to the reference sites named
below (Sotheby's International Realty, Christie's International Real
Estate, Knight Frank, The Agency, Douglas Elliman, Savills, imoti.net)
was blocked by this environment's network egress proxy, so the
descriptions below are drawn from web search results (design write-ups,
case studies, brand-guideline pages) rather than a direct pixel-by-pixel
audit of each live site. Where a claim is well-supported by multiple
independent sources it's presented as solid; single-source or
general-knowledge claims are flagged as such so the user can verify by
visiting the sites directly before treating them as settled. General
knowledge about typical Bulgarian property-portal design (imot.bg,
imoti.net) is flagged separately below as it's from Nosy's general
knowledge of the classifieds-portal genre, not a direct site audit -
Nosy attempted to fetch both directly and both were blocked.

---

## 1. Design philosophy - what "simple, ordered, classy, luxurious" means for THIS product

The user's brief was: *"nice layout in perfect order with a simple user
interface... classy and luxurious and with style."* Translated into
concrete product principles, in priority order:

1. **Simple = fewer things fighting for attention per screen, not fewer
   features.** imotenradar's own feature spec (see
   `docs/property-filter-spec.md`) calls for real density of information
   *per listing* - beds, price/m², motivation signals, pipeline stage,
   etc. Simplicity here does not mean stripping that data out; it means
   *sequencing* it (primary facts visible immediately, secondary facts
   one interaction away) rather than dumping all of it into one dense
   visual field at once, the way Property Filter's icon-grid stat blocks
   and Bulgarian portal listing grids both do.
2. **Perfect order = a strict, repeated visual hierarchy.** Every screen
   type (listing card, listing detail, search/filter panel) should
   present its elements in the *same relative position and the same
   relative weight* every time, so a user's eye learns the pattern once.
   Order is a typographic/spacing discipline, not a synonym for "dense."
3. **Classy = restraint, not decoration.** One accent color, not four.
   One primary action per view, not a row of equal-weight buttons. Quiet
   confidence rather than badges, ribbons, or exclamation-mark urgency
   cues. This is the single biggest lever available and the one most
   luxury real-estate sites lean on hardest (see Christie's/Sotheby's
   notes below) - restraint, not embellishment, reads as expensive.
4. **Luxurious = the photography and the whitespace do the persuading,
   not the UI chrome.** In every reference site researched below, the
   property photo is the largest, most dominant element on any given
   screen, and everything else (price, address, filters, buttons) is
   deliberately smaller and quieter so it doesn't compete with the
   image. imotenradar's redesign should follow the same rule: the UI's
   job is to get out of the photo's way.
5. **"With style" = a considered, consistent typographic and color
   identity carried through every screen**, not a generic default
   Bootstrap/Material look (which is roughly what Property Filter itself
   has, per the spec: plain blue/white SaaS chrome with maroon buttons).

---

## 2. Research references (what was looked at, and what's drawn from each)

- **Sotheby's International Realty** - classic serif typography paired
  with a clean sans-serif for supporting text (brand fonts reported as
  Mercury + Benton Sans; free/open equivalents commonly suggested are
  Playfair Display + Open Sans/Inter); a restrained palette built on
  rich gold, deep black/charcoal, and crisp white; disciplined,
  white-space-led layout that "prevents extensive content from feeling
  overwhelming" even though the underlying content (global listings) is
  large in volume. **What imotenradar should take from this:** the
  serif-headline/sans-body pairing direction, and the principle that a
  content-heavy site can still read as calm through white space
  discipline rather than by reducing content.
- **Christie's International Real Estate** - a striking black-and-white
  aesthetic with marble-like background textures on some pages; the
  documented design strategy (via the Bitovi case study) explicitly
  centers on "generous spacing, careful typography, and visual
  restraint" to deliver a "luxurious atmosphere," built as a flexible
  component system rather than one-off pages. **What imotenradar should
  take from this:** restraint and generous spacing as the actual
  mechanism of "luxury," not a specific color (imotenradar should not
  copy Christie's black-and-white identity itself, since that would
  read as a visual clone of a named competitor's brand - the *principle*
  of restraint is what transfers, not the palette).
- **Knight Frank** - bold, editorial-feeling hero typography over
  large architectural photography; broader luxury-property-site
  research converges on a palette family of warm beige, deep charcoal,
  and off-white (as opposed to bright white), and a serif
  headline/sans-serif body pairing (Playfair Display + a neutral sans is
  named explicitly as a common luxury-real-estate default). **What
  imotenradar should take from this:** the warm-neutral (not
  clinical-white) background family, and confirmation of the
  serif-headline convention from a second independent source.
- **The Agency** - minimalist layout, generous white space, full-width
  photography treated as the content (each listing presented "as a
  lifestyle story rather than a data sheet"), black-and-gold accenting,
  subtle hover animation, tasteful parallax used sparingly on
  marketing/hero sections rather than throughout the working UI.
  **What imotenradar should take from this:** the specific idea that
  "editorial" framing (large photo first, data second) reads as premium
  versus a data-sheet-first framing, and that decorative motion (like
  parallax) belongs on marketing surfaces, not on the working
  search/results UI.
- **Douglas Elliman** - cinematic hero imagery, serif/sans-serif
  typographic pairing again confirmed independently, media-rich but
  organized layout following a rebrand explicitly aimed at feeling more
  premium. Reinforces the serif-headline pairing as a near-universal
  convention across every luxury real-estate brand looked at, not a
  one-off choice.
- **Savills ("Portfolio by Savills")** - editorial/magazine-style
  presentation of listings and lifestyle content; search results
  confirm the brand's general positioning but didn't yield enough
  specific layout/color detail to cite concretely - noted as a
  directionally-consistent reference, not a detailed source.
- **General luxury real-estate design research (cross-site, from
  design-agency write-ups on the genre as a whole, not one specific
  site):** the consistent, repeated advice across multiple independent
  write-ups is that badges/icons must be used with real restraint,
  that cluttered "show everything above the fold" homepages actively
  undercut a luxury read, and that clean/minimal layouts with
  high-quality photography are what signal sophistication - clutter is
  named directly and repeatedly as the thing that breaks the luxury
  read. This directly grounds the anti-pattern list in section 8.
- **Property Filter itself** (from the user's own screenshots, already
  documented in `docs/property-filter-spec.md`): plain blue/white SaaS
  chrome, dark maroon accent buttons, dense 2x3 icon-grid stat blocks on
  every card, saturated multi-color status ribbons (green/yellow/pink/
  orange), flat bordered boxes rather than considered surfaces. This is
  the explicit *negative* reference throughout this document - concrete
  things to move away from, not toward.
- **Typical Bulgarian real-estate portals (imot.bg, imoti.net)** -
  **general knowledge only, not a direct audit**: both sites were
  attempted via WebFetch and both were blocked by this environment's
  egress proxy, so nothing below about them is a confirmed pixel-level
  observation. From general familiarity with the classifieds-portal
  genre these sites belong to (dense grid-of-small-thumbnails listing
  pages, mixed-in banner advertising, multiple competing colored
  "VIP/Top/Premium" listing-boost badges stamped on photos, inconsistent
  photo crop ratios producing a visually noisy grid, small
  low-contrast type, promotional/urgency-toned copy): this is named
  explicitly as the *category* of look to move away from, but the user
  should verify against the live sites directly (or supply screenshots)
  before treating any specific claim about imot.bg/imoti.net as settled
  fact rather than genre-level pattern-matching. **Flag: this bullet is
  the weakest-sourced item in this document.**

---

## 3. Typography

**Pairing direction:** a serif display face for headings/prices/hero
text, paired with a clean humanist sans for body text, UI labels, and
data (numbers, filters, form fields). This pairing is the single most
consistent signal across every luxury real-estate reference researched
above (Sotheby's, Knight Frank, Douglas Elliman all confirmed
independently) - it is the fastest, cheapest way to separate
imotenradar's visual identity from Property Filter's plain default-sans
SaaS look and from a typical portal's all-sans, all-same-weight look.

- **Headline/display serif:** recommend **Playfair Display** (or a
  close relative such as Fraunces or Lora for a slightly softer feel).
  Reasoning: it's the specific font named by name in the luxury-real-estate
  design research above, it's free/open (Google Fonts), and - important
  for this build specifically - **it has full Cyrillic character
  support**, which is a hard requirement given Bulgarian is the site's
  primary language and most premium serif "luxury" fonts (e.g. Sotheby's
  actual brand font Mercury) do not ship Cyrillic glyphs at all. Use it
  for: page hero titles, the price figure on listing cards and detail
  pages, section headers ("Similar properties," "Price history"), and
  nowhere else - a serif used everywhere stops reading as an accent and
  starts reading as inconsistent body copy.
- **Body/UI sans:** recommend **Inter** (or Söhne/Neue Haas Grotesk if a
  paid/licensed option is acceptable later). Reasoning: neutral,
  highly legible at small sizes for dense data (m², beds, dates,
  filters), full Cyrillic support, and widely used so it renders
  consistently and loads fast. Use it for: navigation, filter labels,
  body/description text, form fields, buttons, all numeric stat data.
- **Weight/size hierarchy** (relative scale, exact pixel values are a
  builder's call, but the *ratio* and *restraint* matter):
  - Display/hero (serif, regular or light weight, not bold - bold serif
    display reads heavy/dated rather than elegant): largest step on the
    page, reserved for page-level headings only.
  - H1/price (serif, regular weight): the price on a listing card or
    detail page should be the visually dominant number on that
    surface - larger and quieter (regular weight, not heavy/black
    weight) rather than bold-and-small.
  - H2/section headers (serif or sans, medium weight): one consistent
    style for every "Similar Properties," "Price History," "Agent"
    section header across the site.
  - Body (sans, regular weight, generous line-height ~1.5-1.6):
    description text, agent bios.
  - Meta/label text (sans, small size, medium weight, wide letter-
    spacing, often uppercase): address, tags, filter labels, status
    text - small-caps-with-tracking is a recurring luxury-brand
    convention (seen across the reference sites' navigation and tag
    treatments) precisely because it reads as considered rather than
    default, and it lets small metadata stay legible without competing
    visually with the price/photo.
  - **Rule of restraint:** no more than 3 font weights in active use
    site-wide (e.g. serif-regular, sans-regular, sans-medium). Property
    Filter and typical portals tend to accumulate many ad-hoc weights
    (bold labels, bold badges, bold buttons, bold prices all fighting
    each other) - cap this deliberately.

---

## 4. Color

**Direction:** a warm, restrained neutral base with a single considered
accent color - explicitly *not* Property Filter's utilitarian
blue-with-maroon-buttons, and *not* the bright teal/green that's
become a generic real-estate-tech default (Zillow, Rightmove-style
portals, most SaaS listing tools). The multi-source research above
converges on warm neutrals (beige/charcoal/off-white, per the
Knight-Frank-adjacent research) plus a single metallic/rich accent
(gold, per Sotheby's) or a strict black/white restraint (per Christie's)
as the two dominant luxury-real-estate color strategies. imotenradar
should take the *warm-neutral-plus-one-accent* approach rather than the
black/white approach, because pure black/white risks reading cold/
corporate rather than warm/inviting for a general-audience Bulgarian
property site (Christie's black-and-white works for a fine-art-auction-
adjacent brand identity; imotenradar isn't that).

**Light mode (primary, default):**
- **Background:** warm ivory/bone, not clinical white - e.g. something
  in the range of `#F7F4EE` to `#FAF7F1`. This single choice does more
  than almost anything else to avoid the "generic SaaS dashboard" read
  Property Filter has, since flat pure-white (`#FFFFFF`) backgrounds are
  the default of every utilitarian tool.
- **Text/ink:** a deep warm charcoal, not pure black and not
  Property-Filter-style dark blue-grey - e.g. `#211D1A` to `#2A2521`.
  Near-black rather than true black is a deliberate softness cue used
  consistently by print/editorial-adjacent luxury brands.
- **Structural neutral (borders, dividers, secondary text, disabled
  states):** a warm taupe/greige, e.g. `#8C8378` to `#A69E92` - never a
  cool grey, which would clash with the warm ivory base and read
  "generic dashboard" again.
- **Primary accent (one color, used sparingly):** a muted antique
  brass/gold, e.g. `#A9812E` to `#B08D3F`. Use for: primary CTA buttons,
  active/selected states, key numeric highlights (e.g. a price
  change), section dividers/rules, focus outlines. This is deliberately
  metallic-adjacent rather than a flat saturated hue, echoing the
  gold notes in the Sotheby's palette research without copying it
  outright (a muted brass, not Sotheby's specific bright gold, and never
  paired with Sotheby's specific black/white/gold combination as a
  whole system - the goal is "in the same family of restraint," not
  "recognizably the same brand").
- **Status/signal color (the ONE place a second color is allowed):** a
  single muted, desaturated green-adjacent tone reserved strictly for
  small text labels indicating something like "New" or "Price reduced"
  (e.g. a dusty sage `#7A8B6F`) - used as small-caps text only, never as
  a saturated badge fill or a colored ribbon banner (see section 8's
  anti-pattern on Property Filter's ribbons). If a negative/urgency
  signal is ever needed (e.g. "withdrawn"), use the same ink/charcoal at
  reduced opacity rather than introducing red - red reads as
  alarm/urgency, which undercuts a calm luxury tone.

**Dark mode (if/when built):** don't simply invert light-mode colors
(that's a common mistake that makes warm palettes look muddy). Instead:
- **Background:** deep warm espresso/near-black, e.g. `#17130F` to
  `#1C1712` - warm-toned black, not a cool `#000000` or a blue-black
  (which would drift back toward Property Filter's blue SaaS register).
- **Text/ink:** warm off-white, e.g. `#F0EBE2`, not pure white (too
  high-contrast/harsh against a warm dark background).
- **Accent:** the same brass family, shifted slightly lighter/warmer for
  contrast against the dark background, e.g. `#C9A464` to `#D4B577` -
  keep it the *same* color family as light mode (this is what makes it
  read as one consistent brand rather than two different sites).
- Reduce accent usage even further in dark mode than in light mode -
  gold accents against a dark background get visually loud fast if
  overused; reserve strictly for primary CTAs and the price figure.

**Explicitly avoid:** Property Filter's bright primary blue + maroon
combination; any teal/green as a *primary* brand color (too close to
generic real-estate-tech default); more than one accent hue anywhere in
the system; pure white backgrounds; pure black text or backgrounds;
saturated red/orange/yellow status colors used as fills rather than
restrained text.

---

## 5. Spacing, layout, and information density

Property Filter (and, per general knowledge of the genre, typical
Bulgarian portals) both default to maximum information density: many
simultaneous filter widgets visible at once, dense icon-grid stat
blocks on every card, multiple ribbons/badges stacked on a single
listing photo. The brief explicitly calls for "simple" - here is what
that means concretely, so it doesn't get interpreted as "remove
features":

- **Grid and margins:** use an 8px base spacing unit throughout (4px for
  the tightest internal gaps, 8/16/24/32/48/64 for everything else).
  Generous outer margins on every page - content should never run edge-
  to-edge except full-bleed hero photography. A max content width in the
  ~1280-1440px range on desktop with real breathing room either side,
  rather than Property Filter's edge-to-edge dense-dashboard layout.
- **Card padding:** generous internal padding inside every card/panel
  (24-32px), not the tight ~8-12px padding typical of dense dashboard
  tools. This is one of the highest-leverage, lowest-effort changes
  available - the same content, given more room to breathe, reads as
  premium; the same content packed tight reads as a spreadsheet.
- **One primary action per view.** Property Filter's listing detail page
  has a right-rail with a pipeline-stage indicator, a prominent action
  button, Wait/Hide buttons, "Create Share Link," and "Copy Data for
  AI" all visible with equal visual weight simultaneously. For
  imotenradar: pick the one action that matters most in that context
  (e.g. "Save" or "Contact agent" on a public listing view) and give it
  full visual weight (solid brass button); demote every other action to
  a smaller, quieter secondary style (text link or outline button) or
  move it behind an overflow/"more" affordance.
- **Filters: progressive disclosure, not all-visible-at-once.** Property
  Filter's Comparables tool shows ~10+ simultaneous filter
  controls (property-type checkbox groups, numeric ranges, EPC pills,
  tenure pills, auction/build-type/purpose dropdowns) all on screen at
  once. For imotenradar: show 3-4 of the most common filters
  (location, price range, property type, beds) directly on the results
  view, and collapse everything else behind a single "More filters"
  panel that opens on demand. This preserves the same *filtering power*
  (nothing from the feature spec needs to be cut) while presenting a
  simple default view - density is still available one click away, not
  gone.
- **Listing cards: fewer simultaneous stats, not less data overall.**
  Property Filter's card shows a 2x3 icon grid (beds, floor area, EPC,
  floor level, a distance stat, a yield %) plus two colored ribbons plus
  a colored pill, all on one small card. For imotenradar's default card
  view: show price, address, and 2-3 key facts (beds, m², price/m²) as
  plain inline text - the rest of the density documented in the feature
  spec (motivation signals, full stat set, status history) belongs on
  the listing detail page, not compressed onto every card in a grid of
  20 cards. This is the core "simplify without removing features"
  move: push secondary density one level deeper in the navigation
  rather than deleting it.
- **Vertical rhythm:** consistent spacing between sections site-wide
  (e.g. always 48px or 64px between major page sections) so the page
  has a predictable, calm scroll rhythm rather than sections of
  inconsistent height crowding into each other.

---

## 6. Component-level guidance

### The property listing card (single most-repeated element on the site)

This is the highest-priority component to get right, since it appears
dozens of times per page across search results, saved searches, and
comparables.

- **Photo dominance:** the photo should occupy roughly 65-75% of the
  card's visual area - the largest single element on the card by a wide
  margin. This directly reflects The Agency's "listing as lifestyle
  story, not data sheet" framing and Knight Frank/Douglas Elliman's
  photography-first hero treatment.
- **Consistent crop ratio:** every card photo cropped to the same ratio
  (recommend 4:3 or 3:2 - pick one and use it everywhere) so that a grid
  of cards reads as an ordered, considered arrangement rather than the
  visually noisy mixed-ratio grids typical of budget listing portals.
- **Text block below the photo, not overlaid on it:** price (serif,
  largest text on the card) first, then address (sans, secondary
  weight), then 2-3 key facts as plain inline text separated by a thin
  middle-dot or hairline divider (e.g. "3 bed · 85 m² · €1,200/m²") -
  not an icon-plus-badge grid. Overlaying text directly on the photo
  (common in dense portal grids to save space) should be avoided except
  for a single, small, restrained status label if truly needed (see
  below) - it competes with the photo and undermines the
  photography-first principle above.
- **Status labels, not ribbons:** if a card needs to flag something
  (e.g. "New," "Price reduced"), use small-caps muted text in the
  sage-green signal color from section 4, positioned quietly (e.g.
  top-left corner of the photo, small, not a diagonal ribbon or a
  saturated color block) - this directly replaces Property Filter's
  saturated multi-color ribbon system (green/yellow/pink/orange status
  ribbons stacked with price-change ribbons) which is one of the most
  "utilitarian SaaS" things about its current card design.
- **Card surface:** a very subtle shadow (soft, low-opacity, e.g.
  `0 2px 12px rgba(0,0,0,0.06)`) or a thin 1px hairline border in the
  taupe neutral - not both, and never a heavy drop shadow or a thick
  colored border. Slightly rounded corners (small radius, ~4-8px) read
  as considered without tipping into the fully-rounded "app" look that
  would clash with the serif/editorial tone.
- **Hover state:** a subtle photo zoom (scale to ~1.03-1.05 over
  300-400ms ease) is the one hover effect worth having - it's the
  single hover convention repeatedly associated with the luxury
  reference sites researched above and it draws attention to the photo,
  reinforcing the photography-first principle. Avoid hover effects that
  move/shift the card's layout, change its color, or animate icons.

### Buttons

- **Primary button:** solid fill in the brass accent color, ink-colored
  text (not white-on-gold, which can read low-contrast/cheap depending
  on exact shade - verify contrast when real hex values are picked),
  small border-radius (2-4px, not pill-shaped), generous horizontal
  padding. Reserve solid-fill treatment for exactly one action per
  screen.
- **Secondary/tertiary actions:** outline button (1px ink or taupe
  border, transparent fill) or a plain text link with an understated
  hover underline - never more than one solid-fill button visible at
  once on a given screen, directly addressing Property Filter's
  multi-equal-weight-button rail problem (section 5 of the pattern
  above).
- **Labels:** consider small-caps with slight letter-spacing on primary
  CTA button text specifically (a recurring luxury-brand convention) -
  keep body/secondary button text in normal case to avoid overusing the
  effect.

### Navigation

- Minimal top nav: logo, a small number of primary section links
  (search, saved searches, pipeline if the feature spec's pipeline
  ships, account), generous horizontal spacing between items - not a
  dense mega-menu with icons per item.
- Hover state on nav links: understated (color shift to accent, or a
  thin underline) - no background-fill hover states, which read as
  "software toolbar" rather than editorial navigation.
- Search bar (the primary entry point, per the feature spec's "Find
  your next deal" home-dashboard pattern): should be visually the
  largest, most inviting single element on the landing page, with
  generous internal padding and a serif or large-sized placeholder
  text treatment - it's the equivalent of the "one primary action per
  view" principle applied to the homepage specifically.

### Forms and filter panels

- Fields: generous height, ample internal padding, a simple 1px taupe
  border (not Property Filter's more utilitarian boxed-and-labeled
  form style), label text in the small-caps meta style from section 3
  positioned above the field rather than dense inline labels.
- Validation/error states: text in ink color with a small icon, not a
  saturated red box - keep the calm palette even in error states,
  reserving any stronger color purely for the text itself, not a filled
  background.

---

## 7. Photography and imagery treatment

- **Crop ratio consistency is non-negotiable** for cards and grids (see
  section 6) - this single detail is what separates an "ordered" grid
  from a "cluttered" one, per the repeated clutter/inconsistency
  critiques found in the anti-pattern research (section 2).
- **Detail-page hero:** full-width (or near full-width within the
  content max-width), large single hero image, not a cramped carousel
  with small arrow icons crammed in a corner - Property Filter's
  "Floorplan & Pictures panel" is a dense multi-element panel; the
  luxury convention instead is one large hero image with a slim
  thumbnail strip below it, or a full-screen lightbox gallery on click.
- **Gallery navigation:** simple, minimal - either a thumbnail strip
  below the hero (each thumbnail also cropped to a consistent ratio) or
  numbered dots, not a dense filmstrip of many small unlabeled
  thumbnails.
- **No overlaid marketing badges on photos** (e.g. no "NEW," "HOT
  DEAL," "VIP" stickers stamped across the image itself) - this is the
  most direct instruction against the general Bulgarian-portal pattern
  flagged in section 2 as weakly-sourced but genre-typical; any status
  information belongs in the text block below/beside the photo per
  section 6, never stamped on the image.
- **Consistent treatment across all photos site-wide:** same crop ratio,
  same corner radius, same subtle hover zoom - visual consistency across
  hundreds of listing photos (which vary wildly in original quality,
  since they're scraped from multiple source portals per the feature
  spec) is itself what makes the site look "ordered" rather than
  "luxurious" being solely a function of any individual photo's
  quality. Given imotenradar aggregates photos from multiple Bulgarian
  portals of inconsistent quality, this consistency-of-presentation
  point matters more here than it would for a single-source
  photography-controlled site like the UK/US references above.

---

## 8. Motion and interaction restraint

Luxury design across every reference researched uses motion sparingly
and subtly - it signals confidence rather than trying to impress through
effects. Concrete rules:

- **Transition timing:** 150-300ms, ease-out curves. Nothing snappier
  (feels twitchy/app-like) and nothing slower (feels laggy).
- **No bounce/spring/elastic easing** anywhere - these read as playful/
  consumer-app, not premium.
- **Hover effects limited to:** subtle photo zoom (cards, section 6),
  understated color/underline shift on text links, and a slight
  brightness/shadow change on buttons. Nothing else needs a hover
  animation - icons should not spin, badges should not pulse, cards
  should not shift position on hover.
- **Page/section transitions:** simple fade or none at all, not slide-
  in/slide-out panel animations - Property Filter's tab-switching
  (7 tabs on the listing detail page) and its expandable chevron rows
  are exactly the kind of dense interactive surface that, if carried
  into imotenradar, should switch content with a simple fade rather
  than a flashy transition.
- **Parallax/scroll-triggered effects:** acceptable only on marketing
  surfaces (homepage hero, about/landing pages) per The Agency's
  "tasteful parallax" reference, and used sparingly even there - never
  on working search/results/pipeline screens, where motion should be
  functional (e.g. a smooth filter-panel expand/collapse) rather than
  decorative.
- **Loading states:** a simple, quiet skeleton/shimmer or a small
  centered spinner in the ink or brass color - not a branded animated
  logo spinner, which draws attention to itself rather than staying out
  of the way.

---

## 9. Explicit anti-patterns - what to avoid and why

Concrete things observed in Property Filter (per the feature spec) or
typical of the property-portal genre generally, that would undercut a
"classy/luxurious" read if carried into imotenradar uncritically:

1. **Dense icon-grid stat blocks on cards** (Property Filter's 2x3 icon
   grid of beds/floor-area/EPC/floor-level/distance/yield on every
   pipeline card). **Avoid.** Replace with 2-3 plain-text key facts per
   card (section 6) - full stat density belongs on the detail page.
2. **Saturated, multi-color status ribbons and price-change ribbons**
   (Property Filter's green/yellow/pink Available/STC/Removed ribbons
   plus separate red/green price-change ribbons, stacked on the same
   card). **Avoid.** Replace with a single small-caps muted text label
   (section 4's sage signal color), used sparingly and never as a
   filled colored banner across the photo.
3. **Bright primary-blue-plus-maroon SaaS palette.** **Avoid entirely** -
   this is Property Filter's specific palette and the most immediately
   recognizable thing to not copy; imotenradar's warm-neutral-plus-brass
   direction (section 4) is the explicit replacement.
4. **Utilitarian boxed form styling** (dense labeled input boxes with
   tight spacing, visible everywhere at once in Property Filter's
   Comparables filter panel - 10+ simultaneous filter widgets on
   screen). **Avoid** showing everything at once; use progressive
   disclosure (section 5) - a small set of primary filters visible,
   the rest behind "More filters."
5. **Flat, tightly-bordered boxes with no breathing room** (Property
   Filter's general panel style). **Avoid** tight 8-12px padding on
   panels/cards; use generous 24-32px padding (section 5) and a subtle
   shadow or hairline border, not a heavy rectangular box outline.
6. **Multiple equal-weight action buttons in one view** (Property
   Filter's listing-detail right rail: pipeline button, Wait, Hide,
   Create Share Link, Copy Data for AI, all visually equal). **Avoid** -
   one solid primary action per view, everything else demoted to text
   links or outline buttons (section 6).
7. **Icon-heavy navigation and tab rails** (Property Filter's 7-tab
   listing-detail header, its icon-rail map-layer switcher). Icons are
   fine as small supporting elements next to text labels, but **avoid**
   relying on icon-only navigation for primary wayfinding - it reads as
   dense/technical rather than editorial. Prefer text labels, small
   icons as accents only.
8. **Marketing badges/stickers overlaid directly on listing photos**
   (general property-portal pattern - "VIP," "TOP," "NEW," "HOT"
   stickers stamped across the image; flagged in section 2 as
   general-knowledge/unconfirmed for the specific Bulgarian sites named,
   but a well-documented genre pattern worth guarding against
   regardless). **Avoid** - any status text belongs beside/below the
   photo, never stamped on top of it (section 7).
9. **Inconsistent photo crop ratios producing a visually noisy grid**
   (general portal-grid pattern, same sourcing caveat as above).
   **Avoid** - enforce one consistent crop ratio across every card
   site-wide (section 6/7).
10. **Urgency-toned copy and saturated red/orange alert colors used
    decoratively** rather than functionally (common across budget
    portals' promotional listing labels). **Avoid** - reserve red/
    orange, if used at all, strictly for genuine functional error
    states, in text only, never as a decorative fill or a marketing
    label.
11. **Pure white backgrounds and pure black text/UI elements.**
    **Avoid** - use the warm ivory/charcoal pairing from section 4
    instead; pure white-and-black defaults are what make dashboard
    tools (Property Filter included) look generic rather than
    considered.
12. **Bouncy/spring animation and busy scroll-triggered effects on
    working UI screens** (not named as a Property Filter trait
    specifically, but a common way redesigns overcorrect toward
    "modern" at the expense of "classy"). **Avoid** - see section 8's
    motion restraint rules; save any expressive motion for marketing
    pages only.

---

## 10. How this relates to the feature spec

Nothing in this document asks for any feature, data field, or workflow
step from `docs/property-filter-spec.md` to be removed. Every "simplify"
instruction above is about *visual presentation and sequencing*
(what's shown by default vs. one click deeper, how much visual weight
each element gets, how much room each element is given) - not about
cutting the information density that spec calls for. A builder should
be able to implement the full feature set from the spec using the visual
language described here without the two documents contradicting each
other: the spec says *what* to show and *when* in the workflow; this
document says *how it should look* while showing it.

---

*This design brief is ready to inform backlog items and visual/UI work -
prioritization and sequencing against the feature backlog is Bossy's
call, not this document's.*
