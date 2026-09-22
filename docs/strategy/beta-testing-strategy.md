# Beta testing strategy

Owned by Selly. See `docs/strategy/README.md` for sequencing against the
other four documents — this one runs **before**
`docs/strategy/launch-strategy.md`'s public launch and its output
(real usage/willingness-to-pay signal, a de-risked bug backlog) directly
informs that launch's timing and `docs/strategy/subscription-strategy.md`'s
final price points.

---

## 1. What's being tested, and against what baseline

imotenradar.com is already live (a `CNAME` file points it at the
production domain) and already has real functionality: multi-portal
search/filtering, city/oblast browse, saved listings, Lead Generators,
reminders (all `localStorage`-based per `docs/decisions.md`'s 2026-09-22
login-removal entry). This is **not** a beta of an unlaunched product —
it's a structured beta specifically for the redesign work in
`docs/backlog.md` items 9-17 (listing detail redesign, comparables/area
data, the premium visual refresh) plus, once built, the subscription
tiers themselves.

**Recommendation — needs Kiril's sign-off:** run the beta in two
sequential phases rather than one, since they're testing different
things and mixing them muddies the signal:

- **Phase 1 — Free product beta** (once `docs/backlog.md` items 9-10 at
  minimum have shipped: the listing detail redesign and Lead
  Generators/pipeline). Tests: does the redesigned product work, is the
  new visual direction actually landing as "classy/luxurious" with real
  users (not just Selly/Nosy's own read of the design guidelines), and
  does the core saved-search workflow retain users.
- **Phase 2 — Paid-tier beta** (once `docs/strategy/subscription-strategy.md`'s
  billing infrastructure exists). A smaller group, likely drawn from
  Phase 1's most-engaged users, tests the actual checkout/upgrade/
  Customer-Portal flow and gives real willingness-to-pay signal before
  the price points in that document are finalized.

---

## 2. Recruiting testers (automated/scalable, not manual outreach)

**Recommendation — needs Kiril's sign-off** on channel selection:

- **In-product recruitment (primary, zero manual effort):** a small,
  dismissible banner on the live site itself (imotenradar already has
  real organic traffic as a live product) inviting visitors to "Try the
  new [redesign] and tell us what you think" — this requires no manual
  outreach at all, since the traffic already exists. Target: 150-300
  Phase 1 testers, enough for a meaningful sample without needing a
  large recruiting push.
- **Targeted community seeding (one-time setup, not ongoing manual
  work):** a single post in 2-3 Bulgarian real-estate-investor-adjacent
  communities (relevant Facebook groups, a Bulgarian property-investing
  subreddit or forum if one has real activity) — written once, posted
  once, not a recurring manual task. This is the one piece of this
  document that's inherently a one-time human action (writing and
  posting an announcement) rather than an automated system, flagged
  plainly rather than pretending it's automatable — it's small enough
  (a few posts, once) not to be a meaningful ongoing time cost.
- **Explicitly not recommended:** paid ad spend to recruit beta testers.
  Premature before there's product-market signal, and clashes with the
  bootstrapped, AI-run-operation framing — organic + community seeding is
  sufficient for a beta cohort of this size.

---

## 3. Feedback capture — automated, feeding directly into the existing
backlog process

This is the load-bearing part of this document, since the founder's
brief is explicit: automated feedback capture and triage, **not** "email
Kiril your feedback."

### In-app feedback mechanism

- A small, persistent, unobtrusive **"Feedback" affordance** (consistent
  with `docs/design-guidelines.md`'s restraint principles — a quiet text
  link or small icon, not a jarring floating button) present during the
  beta, plus the per-listing **"Report a bug for this advert"** pattern
  already speced in `docs/property-filter-spec.md` section 5 (flagged
  there as "replicable... useful given imotenradar is scraper-based and
  will have data-quality issues too" — build this as part of the beta,
  not deferred).
- **Structured form, not a free-text box**, so triage can be automated:
  category (Bug / Data looks wrong / Feature request / General
  feedback), a short description field, and for "Data looks wrong,"
  auto-attach the listing ID/URL the user was viewing so no manual
  cross-referencing is needed later.
- **In-app prompts at natural checkpoints** (not interruptive
  pop-ups): e.g. a single, dismissible "How's the new design working for
  you?" micro-survey (1-5 stars + optional comment) shown once per
  tester after their first session past a meaningful interaction (saving
  a listing or creating a Lead Generator) — a signal of real engagement,
  not a random-page-load prompt.

### Automated triage → the backlog, not a Kiril inbox

This should reuse the pipeline the team already runs and trusts, not
invent a parallel one:

- Every structured submission needs a path from an anonymous public
  visitor's browser to a **GitHub issue** labeled `beta-feedback` (or
  `beta-bug` for the bug-report path) without ever putting a
  GitHub-write credential in that visitor's page — **this needs a small
  serverless function** as the write target for the feedback form, not
  a client-side script, the same problem
  `docs/strategy/subscription-strategy.md` §4 already flags for its own
  Stripe webhook and the same shape of fix (a lightweight Cloudflare
  Worker/Vercel/Netlify function holding the credential server-side).
  Recommend that function file the issue directly via the GitHub API
  (`mcp__github__issue_write`-equivalent from server-side code, or a
  plain REST call using a stored token) rather than going through a
  committed-file-plus-push-triggered-workflow indirection — per
  `docs/decisions.md`'s 2026-09-21 entry, that committed-file shape
  (`.github/workflows/missy-findings-issue.yml`) is now documented as a
  **secondary, best-effort fallback** for Missy's own findings pipeline,
  not its primary path; the primary path there is a persistent session
  with real GitHub access calling `mcp__github__issue_write` directly.
  Filing the beta-feedback issue the same direct way (via the new
  serverless function, since there's no persistent session sitting
  behind the public feedback form) avoids relying on the superseded
  mechanism as "the" current pattern. Either way, this reuses Kiril's
  existing GitHub-issue email notifications as the real awareness
  channel — nothing new for him to check.
- **Automated triage, not manual sorting:** category from the structured
  form (above) maps directly to a GitHub label; a lightweight duplicate
  check (e.g. fuzzy-match new submissions against open `beta-feedback`
  issue titles/URLs before filing a new one, bumping a `+1` comment on
  an existing issue instead of opening a duplicate) keeps the backlog
  from filling with the same complaint 40 times. Building this duplicate
  check is a small script, in the same spirit as `check_scrape_freshness.py`
  or `merge_history_conflict.py` already in the repo — flagged for
  whoever picks this up, not something Selly builds (she doesn't touch
  code).
- **This becomes Bossy's normal backlog input**, exactly like Missy's
  findings already are (`docs/decisions.md`'s 2026-09-21 entry: "Bossy
  now also reads `docs/missy-findings/` at the start of every session")
  — `beta-feedback`-labeled issues should be read the same way, not
  treated as a separate stream requiring Kiril's personal triage.

---

## 4. Exit criteria — what decides "ready for launch," not a fixed
calendar date

**Recommendation — needs Kiril's sign-off.** Time-boxing a beta to an
arbitrary date risks either launching with real unresolved problems or
sitting in beta longer than needed. Concrete thresholds instead:

**Phase 1 (free product) exit criteria — all of the following:**
- **150+ testers** have used the redesigned product for at least one
  real session (not just landed on the page).
- **No open `beta-bug` issue tagged `severity:high`** (data-loss,
  broken core workflow, broken on a majority of common browsers) older
  than 5 days.
- **Qualitative design signal is net positive**: the micro-survey
  average is ≥4.0/5, and free-text comments don't show a recurring
  complaint about the "classy/luxurious" redesign reading as confusing
  or worse than the old layout (a real risk worth checking for directly,
  since `docs/design-guidelines.md`'s direction is a genuine departure
  from typical Bulgarian portal conventions).
- **Core retention signal**: of testers who create at least one Lead
  Generator, a meaningful share (recommend ≥30% as the bar, adjust once
  real numbers come in — this is a reasoned starting threshold, not a
  benchmarked industry figure) return for a second session within 7
  days. This is the single best proxy available for "does the core loop
  actually work" given there's no login/account system yet to track
  users more precisely.

**Phase 2 (paid tier) exit criteria:**
- At minimum **10-15 real, voluntary upgrades** to a paid tier during
  the beta window (even at a discounted/beta price — see below), as
  direct willingness-to-pay evidence, not just survey answers about
  hypothetical pricing.
- **Stripe checkout → magic-link → paid-feature-unlock flow tested
  end-to-end with zero failures** across at least 2 browsers, since this
  is new infrastructure with no prior production use.
- No unresolved billing/dunning issue open longer than 48 hours (this
  phase is small enough that any real billing bug should surface and
  get fixed fast, not linger).

**Recommendation — needs Kiril's sign-off:** offer Phase 2 testers a
**meaningful, time-limited discount** (e.g. 50% off for 6 months) in
exchange for real payment-flow testing and feedback — this both
de-risks the billing infrastructure with real transactions before full
public pricing goes live, and rewards the testers most likely to become
long-term paying customers and vocal early advocates.

---

## Open questions for Kiril

1. **Beta cohort size targets (150-300 free, 10-15 paid)** — these are
   Selly's reasoned starting points given expected organic traffic, not
   validated against real numbers yet; revisit once Phase 1 actually
   starts recruiting.
2. **The retention threshold (≥30% 7-day return)** is a reasoned
   placeholder, not an industry-benchmarked figure specific to this
   product category — treat it as provisional and tighten once real
   data exists.
3. **Community-seeding posts (§2)** are the one manual, human step in
   this document — confirm Kiril is fine writing/posting these himself
   (a few one-time posts) or whether that should be scoped out to
   someone else.
4. **Discount depth/duration for Phase 2 beta testers** — 50%/6 months
   is Selly's placeholder; needs Kiril's real pricing sign-off, which
   also depends on `docs/strategy/subscription-strategy.md`'s final
   price points being settled first.
