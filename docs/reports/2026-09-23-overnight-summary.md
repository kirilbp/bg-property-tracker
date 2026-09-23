# Overnight summary — 2026-09-23 session, for Kiril's 7am read

Prepared by Selly, with a final status pass and corrections applied
afterward once several items that were still in flight when Selly wrote
this finished, merged, and were reviewed. Covers (1) what an autonomous
overnight work session did to imotenradar.com, in plain business terms,
and (2) the concrete next actions from the existing business strategy in
`docs/strategy/` — kept as two clearly separated parts, per your request.
Everything below is drawn directly from `docs/decisions.md`,
`docs/backlog.md`, the live `index.html` on the `main` branch, and this
repo's own git history — nothing invented.

**Editor's note on the corrections below:** everywhere this report
originally said something was "not yet merged," "pending review," or
flagged a documentation gap, that status has since changed and is
corrected in place (marked "Update:") rather than silently rewritten, so
you can see what was true when compiled vs. what's true now.

---

## Executive summary

**What shipped and is live on `main` overnight:** the site is now branded
"Imoten Radar" (was "BG Property Tracker"), a new "Only with photos"
listing filter, a redesigned "Browse by city" section with real city
photos, a preview-only Account & Subscription page, a redesigned Lead
Generator creation flow, and a nationwide coverage expansion for two
scraper portals (bazar.bg, imot.bg). A category-allocation bug that had
2,058 apartments mis-filed under "Garages" was found, root-caused, and
fixed. **Update: every item in this paragraph is now Missy-reviewed,
approved, and merged to `main`** — at the time Selly compiled this
report, the garage fix and two of the design changes were still mid-
review; all have since cleared review and shipped. Design-inspiration
research (Nosy) is also merged, ready to hand to Dessy for
implementation.

**What needs your decision before it goes further** (full list in Part 1,
section 3): (1) the new Account/Subscription page shows a placeholder
price (€19/mo, one tier) that is a strategist's placeholder, not a real
pricing decision — nothing should connect to a real payment processor
until you've set actual price points and tiers; (2) whether to move
forward with real login/Supabase Auth and a real payment processor at all,
now that you can see the preview page; (3) five small-town photo tiles on
the new Browse-by-city page (Asenovgrad, Dupnitsa, Svishtov, Montana,
Dimitrovgrad) used Wikimedia Commons filenames that could not be verified
live this session — worth a 30-second glance to confirm they show the
right city; (4) Send Letters (outreach campaigns) stays parked, not
resumed, per your own earlier instruction — flagged again here only so
it's not forgotten, not because it needs a fresh decision; (5) you asked
Placy and Ready to each re-run a much more exhaustive, full-population
audit of location and category allocation respectively, beyond their
earlier fixes — both are still running as of this report and will need
their own review/merge/report once done, likely after 7am.

**Top 3 strategic actions ready to act on now** (full reasoning in Part 2):
1. Because the Account & Subscription preview page now exists, the
   subscription-strategy.md pricing decision (tier count, price points,
   annual discount) is now the actual bottleneck — it's the one input that
   unlocks wiring real billing, and marketing's referral mechanics wait on
   it too.
2. Turn on the SEO content-page generator now — it depends on nothing that
   shipped or is still pending tonight, it's ready to start today, and it
   compounds the longer it runs.
3. Stand up the AI customer-service agent (Crisp vs. Intercom Fin) before
   opening beta recruitment — it's the one item actually gating the beta
   from starting, per `docs/strategy/beta-testing-strategy.md`'s own
   sequencing.

(Getting tonight's work through Missy's review is no longer on this
list — it was the top action when this report was first drafted, but all
five PRs have since been reviewed and merged; see Part 2, Action 1.)

---

# Part 1 — What happened overnight

### How to read this section

This was an autonomous, unattended session with multiple specialist agents
working in parallel (scraper/data-quality fixes, frontend design, and
documentation). Everything below is grounded in `docs/decisions.md` and
`docs/backlog.md`'s dated 2026-09-23 entries, cross-checked against the
live `index.html` file and this repo's git history where the two logs
didn't fully agree (noted explicitly where that happened — see the
"documentation gap" note in section 2).

## 1. What shipped and is live on `main`

- **Category-allocation fix: 2,058 listings corrected — shipped and
  live.** A data-quality bug meant that whenever a listing's category was
  a genuine toss-up between "garage" and something else (most commonly a
  real apartment that happens to mention a parking space in its text,
  e.g. "Two-room apartment + parking space"), the system always defaulted
  to "garage" — regardless of what the listing actually was. This wrongly
  filed 2,058 real apartments (plus a handful of houses/land/commercial
  listings) under the Garages section. The fix now reads which category's
  own keyword appears first in the listing's title (the strongest signal)
  to break the tie correctly. **Update: Missy reviewed and approved this
  (catching and requiring one small arithmetic correction in the written
  record, not in the fix itself), and it merged as PR #255** — this was
  still pending review when Selly's original draft was written; it's
  fully shipped now.
- **"Only with photos" filter — shipped and live.** A new checkbox filter
  lets visitors hide listings that have no photo. Small, low-risk,
  self-contained change; confirmed present and wired up in the live site
  code.
- **Site renamed to "Imoten Radar" — shipped and live.** The site's
  displayed name (browser tab title, sidebar header, main heading) changed
  from the placeholder "BG Property Tracker" to "Imoten Radar" — a real
  branding step, not a functional change. No URL/domain change was part of
  this (imotenradar.com was already the domain).
- **Nationwide scraper coverage expansion (bazar.bg, imot.bg) — shipped
  and live, reviewed by Missy.** Two of the eight portals imotenradar
  scrapes were previously limited to a fixed list of ~25-30 major cities,
  meaning Bulgaria's ~230 smaller towns and ~5,000 villages were
  structurally invisible to those two portals' data, even though the
  listings existed. imot.bg now queries at the broader "province" level
  (27 provinces) instead of just city-by-city, roughly matching the
  approach already used on a couple of other portals. bazar.bg's site
  doesn't technically support that same province-level query without
  breaking its own filtering, so its city list was instead widened by 8
  real, individually-checked towns (29 → 37 cities). Both scrapers were
  also made more resilient (they now checkpoint and resume their crawl
  instead of always starting from the same place and starving the same
  towns every run). **Honest limitation, stated plainly in the project's
  own notes rather than glossed over:** this is a real, meaningful
  widening of coverage, not full nationwide coverage — most of Bulgaria's
  ~5,000 villages are still outside both scrapers' reach. This was
  reviewed and merged through the normal process (PRs #251/#252).
- **"Browse by city" redesign with real city photos — present and live on
  `main`.** The city-browsing section of the site now shows a photo tile
  per major city (pulled from Wikimedia Commons) instead of a plain text
  button, intended to read as more premium/visual, consistent with the
  site's "classy, luxurious" design direction. See the open item on
  unverified small-town photos below (section 3, item 3).
- **New Account & Subscription page — present and live on `main`,
  deliberately inert/preview-only.** A new "Account" section was added to
  the site showing what a future login and paid-subscription experience
  will look like — a login/signup form and a subscription page showing one
  paid tier ("Imoten Radar Pro," €19/month or €190/year) with a feature
  list. **This is explicitly non-functional by design**: submitting either
  form does nothing except show a "preview only" message — no account is
  created, no card is charged, nothing is wired to Supabase Auth or any
  payment processor. The page carries in-code comments explicitly warning
  against wiring it up without your fresh, explicit go-ahead, out of
  respect for your earlier direct instruction to remove login entirely.
  Saved listings, Lead Generators, Reminders, and the Pipeline all
  continue to work exactly as before, with no account required — this
  page doesn't gate anything.

**Update on the documentation gap Selly flagged here:** at the time this
was written, the Browse-by-city redesign and the Account & Subscription
page were live on `main` but had no matching `docs/decisions.md`/
`docs/backlog.md` entry, despite both having actually been reviewed by
Missy before merging (PRs #257 and #259) — the review happened, it just
hadn't been written up yet. That gap is now closed: both, plus the Lead
Generator modal redesign (PR #258) and the design-inspiration doc (PR
#260), have full write-ups in `docs/decisions.md`'s "2026-09-23 (later)"
entry, including exactly what Missy checked and found for each.

## 2. Still in progress as of report time

**Update:** three of the five items Selly originally listed here have
since shipped - the Lead Generator modal redesign (merged, PR #258) and
the design-inspiration research doc (merged, PR #260) are now covered in
section 1 above, not here. What genuinely remains running, likely still
in progress when you read this at 7am:

- **Site-wide visual alignment audit.** A fresh, full-budget pass
  specifically responding to your complaint that some windows/buttons/
  maps look misaligned - going through every major page at desktop and
  mobile widths looking for concrete layout defects (not a vague
  redesign), fixing what it finds with before/after screenshots as
  evidence, and flagging anything it can't safely fix without touching
  the concurrent Lead Generator work. Still running as of this report.
- **Exhaustive location-allocation audit (Placy) - round 2.** You asked
  for a much more careful, full-population pass beyond her earlier fixes
  tonight (which had already corrected 1,358 mis-provinced listings).
  This round is checking every listing that has real map coordinates
  against what those coordinates actually resolve to, not just the
  administrative-area text fields, and will root-cause and fix whatever
  real mismatches it finds. Still running as of this report - a
  materially bigger task than her earlier pass, likely the last of
  tonight's work to finish.
- **Exhaustive category-allocation audit (Ready) - round 2.** Similarly,
  you asked for a much more careful full-population pass beyond the
  garage/apartment fix (section 1). This round covers all 8 portals (her
  first fix only touched 3), starting with her own two already-disclosed
  residual gaps before looking for new patterns. Still running as of this
  report.

## 3. Decisions/judgment calls made on your behalf that need your actual input

This is the section worth reading first at 7am. Nothing below has been
wired to anything real or made irreversible — these are all either
inert previews or reversible engineering choices — but each one had to
default to *something* overnight, and that default is not the same thing
as your decision.

1. **The Account/Subscription page's €19/month single-tier pricing is a
   placeholder, not a real pricing decision.** It exists so you can see
   what the page looks like, not because €19/mo/one-tier is a considered
   recommendation — Selly's actual pricing recommendation (three tiers,
   different price points, see Part 2 and `docs/strategy/subscription-
   strategy.md`) hasn't been reconciled with what's on this preview page
   yet. **Action needed:** decide real tiers/pricing before anyone touches
   this page again, let alone connects it to a payment processor.
2. **Whether to proceed with real login (Supabase Auth) and a real payment
   processor (Stripe or otherwise), now that you've seen the preview
   page.** The page was deliberately built inert specifically because your
   earlier instruction to remove login entirely was explicit and direct —
   nobody should reverse that without your fresh, explicit go-ahead. This
   preview exists to make that decision easier to make by showing you the
   shape of it, not to nudge you toward reactivating it.
3. **Five small-town "Browse by city" photo tiles used Wikimedia Commons
   filenames that could not be verified live this session** (no internet
   access to check the actual images): Asenovgrad, Dupnitsa, Svishtov,
   Montana, and Dimitrovgrad, using files named "Asenovgrad montage.jpg,"
   "Dupnitsa montage.jpg," "Svishtov montage.jpg," "Montana, Bulgaria
   montage.jpg," and "Dimitrovgrad, Bulgaria montage.jpg" respectively.
   These are named plausibly and were deliberately chosen with lower
   confidence flagged in the code's own comments for exactly this reason
   (smaller towns, more disambiguation-prone names than the larger
   regional-capital cities). **Action needed:** a 30-second glance at these
   5 tiles on the live Browse-by-city page to confirm each photo actually
   shows the right town, not a wrong/generic/unrelated image.
4. **Send Letters (motivated-seller outreach campaigns) stays parked —
   not a new decision, just flagged so it isn't forgotten.** This was
   built end-to-end earlier but parked per your own explicit direction,
   with an explicit "do not resume without asking" note attached in
   `docs/backlog.md`. Nothing changed on this overnight; it's listed here
   only because it's exactly the kind of standing decision this report is
   meant to surface, not because anyone acted on it without asking.
5. **Resolved by the time you're reading this:** the garage/category fix
   and the two originally-un-logged design features have all since been
   confirmed Missy-reviewed, merged, and properly documented - no action
   needed on this point, kept here only so you can see it was checked.

---

# Part 2 — Strategy: prioritized actions to take now

This synthesizes the five documents in `docs/strategy/` (`launch-
strategy.md`, `beta-testing-strategy.md`, `marketing-strategy.md`,
`subscription-strategy.md`, `customer-service-ai-strategy.md`) into the
actual next moves, prioritized, with tonight's shipped work folded in
where it changes what's actionable. It does not re-dump all five
documents — read those directly for full reasoning; this is the "what do
I actually do Monday morning" version.

**Currency check on the strategy docs themselves:** all five were written
against a pre-tonight snapshot of the product (their own "Current state"
framing describes the app as of before tonight's rename/photos-filter/
Browse-by-city/Account-page work). None of tonight's changes invalidate
their reasoning — if anything, the new Account/Subscription page is the
single piece of tonight's work most directly relevant to them, since
`subscription-strategy.md` was written assuming that page didn't exist
yet. Treat `subscription-strategy.md` as newly partially-actionable (see
action 2 below), not stale.

## Action 1 — Resolved: tonight's work is through Missy's review

This was the top action when this report was first drafted: the garage/
category fix and two un-logged features (Browse-by-city, Account page)
all needed their review status confirmed. **Update: resolved.** All five
of tonight's PRs (#255 garage fix, #257 Browse-by-city, #258 Lead
Generator modal, #259 Account page, #260 design-inspiration research)
have since been Missy-reviewed, approved, and merged to `main` — see
`docs/decisions.md`'s "2026-09-23 (later)" entry for what each review
specifically checked and found. Nothing here needs your action; kept in
this list only so you can see the process was followed, not skipped.

## Action 2 — Now that the Account/Subscription page exists, the pricing decision is the real bottleneck

Per `docs/strategy/subscription-strategy.md`, the biggest open item
blocking any real monetization work was never technical — Stripe
Checkout, magic-link auth, and the Customer Portal are all well-understood,
buy-don't-build pieces. The actual blocker has always been **your pricing
sign-off**: tier count, price points, and whether the free tier stays free
forever. Tonight's preview page makes this concrete and visible for the
first time rather than abstract. Recommended next step: review
`docs/strategy/subscription-strategy.md` §2's three-tier proposal (Free /
Investor €14.99/mo/€149/yr / Deal Maker €39.99/mo/€399/yr) against the
page's current placeholder (one tier, €19/mo) and decide which direction
to take — Selly's reasoning for feature-gating (not quantity-gating, since
the free tier has no accounts) still applies regardless of which price
points you land on.

**Also unblocked by this:** legal entity/VAT setup (subscription-
strategy.md's open question #2) is the one gate on this whole area with a
long, externally-controlled lead time — worth starting now, in parallel,
rather than after pricing is finalized, exactly as `launch-strategy.md`
§2 already recommends.

## Action 3 — Start the SEO content-page generator now; it depends on nothing pending

Per `docs/strategy/marketing-strategy.md` §2, this is the single highest-
leverage automated marketing move available, and it was already scoped to
need nothing beyond data the scrapers already produce (per-area average
price/m², the motivation score). Tonight's nationwide coverage expansion
(bazar.bg/imot.bg) makes this marginally stronger, not blocking — more
towns now have real listing data to generate area-guide pages from. This
doesn't wait on the beta, on pricing, or on any of tonight's still-open
items. Recommended: get the page-template/copy-structure review (the one
human-in-the-loop step this needs, per marketing-strategy.md) scheduled
this week.

## Action 4 — Beta recruitment banner is now closer to ready, but not quite yet

Per `docs/strategy/beta-testing-strategy.md`, Phase 1 beta recruitment
should start once the listing-detail redesign and Lead Generators/pipeline
have shipped (already true) and once the AI customer-service knowledge
base is live, even minimally (not yet true — see Action 5). Tonight's
design-consistency fixes (section 1/2 above) further reduce the risk of
recruiting testers into a visibly-unfinished redesign, which strengthens
the case for starting soon once Action 5 is done.

## Action 5 — Stand up the AI customer-service agent before beta recruitment opens

Per `docs/strategy/customer-service-ai-strategy.md` and the sequencing
note in `docs/strategy/README.md`, this has to exist before the beta
starts asking strangers for feedback — there's no channel today for that
feedback to land anywhere but an inbox you'd have to personally check.
Selly's recommendation remains Crisp (with its AI-agent add-on) over
Intercom Fin to start, mainly on cost at low volume — this needs your
quick hands-on trial of both against the real FAQ content to settle
(open question in that document). This is the one item on this list that
gates the beta from actually starting, so it's worth prioritizing this
week if the beta itself is a near-term goal.

## Action 6 — Beta feedback intake and bug-report pipeline

Also from `beta-testing-strategy.md` §3 and `customer-service-ai-
strategy.md` §5: both reuse the same structured-form → GitHub-issue
pipeline, and both need a small serverless function to file issues on
behalf of anonymous visitors without exposing a GitHub credential
client-side. This is real, scoped build work (not something Selly builds)
— worth handing to whoever's doing engineering work next, since it's a
shared dependency for both the beta and ongoing post-launch support.

## What's explicitly NOT ready to act on yet

- **Paid tier launch** — waits on Action 2 (pricing sign-off) and legal/
  VAT completion, per `launch-strategy.md` §2's Stage 2→3 gate. Don't
  connect the Account page to Stripe before both are done.
- **Referral program** — waits on paid tiers existing at all
  (`marketing-strategy.md` §4).
- **Paid ad spend** — explicitly not recommended until the beta validates
  retention (`marketing-strategy.md` §5).
- **Social media content calendars** — explicitly deprioritized for this
  audience/product; see `marketing-strategy.md` §5 for the full reasoning
  (weak fit for an investor audience, plus a real scraped-photo usage-
  rights question that's still open).

---

## Open questions for Kiril (collected from this report only)

1. Glance at the 5 small-town Browse-by-city photo tiles (Asenovgrad,
   Dupnitsa, Svishtov, Montana, Dimitrovgrad) to confirm the images are
   actually correct for each town.
2. Real pricing/tiering decision for the Account/Subscription page — see
   Part 2, Action 2. This is the single highest-leverage decision on this
   whole report, since it unblocks the most other work.
3. Whether you want to proceed toward real login/Supabase Auth + a real
   payment processor at all, now that you've seen the preview page — no
   action has been taken toward this, by design.
4. Whether to greenlight standing up the AI customer-service agent
   (Crisp vs. Intercom Fin vs. a quick trial of both) this week, since
   it's the one item gating beta recruitment from starting.
5. Check back on the site-wide alignment audit and Placy's/Ready's round-2
   exhaustive audits (Part 1 §2) — all three were still running when this
   report was finalized and will need their own review/merge, likely
   after 7am.
