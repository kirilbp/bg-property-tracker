# Strategy docs — index

Owned by Selly, the business/growth strategist for imotenradar.com. This
index ties together the five documents below. Each is individually
concrete and decision-ready; read this page first for how they sequence
against each other and against `docs/backlog.md`'s engineering roadmap.

- [`launch-strategy.md`](./launch-strategy.md) — the rollout plan;
  read **last**, since it depends on all four documents below.
- [`beta-testing-strategy.md`](./beta-testing-strategy.md) — recruiting,
  automated feedback capture, and the exit criteria that decide launch
  timing.
- [`subscription-strategy.md`](./subscription-strategy.md) — tiers,
  self-serve billing, and how paid access works without reviving the
  login system that was just removed.
- [`marketing-strategy.md`](./marketing-strategy.md) — automated,
  scalable channels (SEO content generation, email drip, referrals).
- [`customer-service-ai-strategy.md`](./customer-service-ai-strategy.md) —
  the AI support agent and its narrow human-escalation path; this one
  underpins all the others operationally.

---

## The constraint every document here is built around

Kiril's explicit instruction: **"I want to build the platform around AI
running it rather than me having to do a manual input."** Every
recommendation in these five documents is designed for an AI/automation-
first operation — self-serve billing, an AI agent handling most support,
automated content generation, automated feedback triage — with a
narrow, explicitly-named human-escalation path only where something
genuinely can't be automated yet (legal/VAT setup, GDPR complaints,
refund disputes outside a standard policy). Where that's the case, it's
stated plainly in the relevant document rather than hand-waved.

## Current state (grounding all five documents)

As of this writing, imotenradar.com is a **live, static GitHub Pages
site** (see the repo's `CNAME` file) with:
- Real, working functionality: multi-portal listing search/filter, city/
  oblast browse, saved listings, Lead Generators, reminders — all
  `localStorage`-based, **no accounts, no login** (removed entirely per
  `docs/decisions.md`'s 2026-09-22 entry, at Kiril's explicit direction).
- **Zero payment infrastructure, zero subscription logic, zero support
  channel of any kind** — every one of these five documents is a
  build-from-zero plan for the respective area, not a tune-up of
  something already running.
- A real, active engineering backlog (`docs/backlog.md` items 9-17) that
  will substantially change the product's information density and visual
  design before a public launch makes sense — see `launch-strategy.md`
  §2 for exactly which items gate which stage.
- Bulgaria adopted the euro on 1 January 2026 (sole legal currency since
  1 February 2026) — pricing throughout `subscription-strategy.md` is in
  EUR, not BGN, on that basis.

## How the five documents sequence

1. **Beta testing informs launch timing**, not the other way around.
   `beta-testing-strategy.md`'s Phase 1 exit criteria (tester count, bug
   severity, retention signal) are the actual gate `launch-strategy.md`
   uses to decide when the redesigned product is ready for full traffic
   — there is no fixed launch date in this plan, by design (see
   `launch-strategy.md` §2 and its open question #1).
2. **Subscription strategy has to exist, technically and legally, before
   marketing drives paid signups.** `marketing-strategy.md`'s referral
   mechanics (§4) and any paid-conversion-focused spend explicitly wait
   on `subscription-strategy.md`'s billing infrastructure and Kiril's
   legal/VAT sign-off — but `marketing-strategy.md`'s SEO content engine
   (§2) does **not** wait on this; it should start as early as Stage 1 of
   the launch plan, since it drives free-tier growth independent of
   monetization.
3. **Customer-service AI has to be live before the beta starts
   recruiting**, not before public launch — a beta actively asking
   strangers for feedback needs a non-Kiril-personal channel to receive
   it from day one, per `beta-testing-strategy.md` §3 and
   `customer-service-ai-strategy.md`'s intake/triage design (both reuse
   the same GitHub-issue pipeline pattern Missy's own findings already
   use, per `docs/decisions.md`'s 2026-09-21 entry).
4. **Subscription strategy's Phase 2 beta (real paid upgrades, at a
   discount) is itself the validation step** for the price points
   `subscription-strategy.md` proposes — pricing isn't finalized until
   that phase produces real willingness-to-pay evidence, per
   `beta-testing-strategy.md` §4.

See `launch-strategy.md` §2 for the full stage-by-stage readiness-gate
checklist that operationalizes this sequencing.

## Review status

**These documents have not yet been reviewed by Missy.** Per the
standing rule that document review (like code review) now routes through
her, this is real, decision-ready work but not yet signed off — Selly
had no `Agent`-tool access in this session to dispatch that review
herself. Route these five documents (and this index) to Missy for review
before treating any "Recommendation — needs Kiril's sign-off" item in
them as final, and before Kiril acts on the open questions collected at
the end of each document.

## Keeping these current

If the product changes in a way that invalidates part of a strategy
(a major `docs/backlog.md` item ships or gets cut, a pricing decision is
made, login/accounts change again), update the relevant section of the
relevant document — these five files don't need a full rewrite for a
single changed fact.
