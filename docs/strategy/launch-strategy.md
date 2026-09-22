# Launch strategy

Owned by Selly. See `docs/strategy/README.md` for how this ties together
`docs/strategy/beta-testing-strategy.md`,
`docs/strategy/marketing-strategy.md`,
`docs/strategy/subscription-strategy.md`, and
`docs/strategy/customer-service-ai-strategy.md` — this document is the
sequencing/rollout plan that depends on all four of the others, and
should be read last, not first.

---

## 1. What "launch" means here — this is a re-launch, not a launch

imotenradar.com is already live in production (`CNAME` points the
GitHub Pages site at the domain) with real, working functionality:
multi-portal search/browse, saved listings, Lead Generators, reminders
(`docs/decisions.md`). "Launch" in this document means the coordinated
rollout of three things that don't exist yet, layered onto that live
product without ever taking it offline:

1. The redesigned, information-denser product (`docs/backlog.md` items
   8-16 — listing detail redesign, comparables/area data, market data
   hub, the premium visual refresh).
2. Self-serve paid subscription tiers
   (`docs/strategy/subscription-strategy.md`).
3. AI-run support and automated marketing running underneath both
   (`docs/strategy/customer-service-ai-strategy.md`,
   `docs/strategy/marketing-strategy.md`).

Because the free product is already live and already has organic
traffic, there is **no "launch day" risk of zero users** — this
materially de-risks the whole plan relative to a from-scratch launch,
and argues for a staged rollout over a single big-bang date.

---

## 2. Readiness gates — what has to be true before each stage, not a
fixed calendar

**Recommendation — needs Kiril's sign-off** on treating these as hard
gates rather than target dates. Given the founder's own AI-first
constraint, shipping a stage before its automation is real (support,
billing, marketing) just recreates the manual-founder-bottleneck problem
this whole strategy exists to avoid — so gate on readiness, not time.

### Stage 0 → Stage 1 gate (start the redesign beta)
- `docs/backlog.md` items 8 and 9 (listing detail redesign,
  Lead Generators/dashboard/pipeline) shipped and reviewed by Missy per
  the repo's standing rule.
- Item 5 (imoti.net miscategorization fix) merged — a correctness bug
  this visible should not be live during a beta that's actively
  recruiting new eyes on the product; per `docs/backlog.md` it's already
  fixed and verified, only Missy's review/merge is outstanding as of
  this writing.
- The AI customer-service knowledge base (§3 of
  `docs/strategy/customer-service-ai-strategy.md`) is live, even in a
  minimal first version — a beta actively recruiting testers must not
  route feedback into a channel Kiril has to personally monitor.

### Stage 1 → Stage 2 gate (open the redesign to all traffic / end
Phase 1 beta)
- `docs/strategy/beta-testing-strategy.md`'s Phase 1 exit criteria are
  met (150+ testers, no open high-severity bug >5 days, ≥4.0/5 design
  signal, ≥30% 7-day Lead-Generator-creator return rate).
- Programmatic SEO content generation (`docs/strategy/marketing-strategy.md`
  §2) is live and running on its own cadence — this should be turned on
  *during* Stage 1, not held for Stage 2, since it compounds with time
  and costs nothing to run early once built.

### Stage 2 → Stage 3 gate (turn on paid subscription tiers publicly)
- `docs/strategy/subscription-strategy.md`'s Stripe Checkout → magic-link
  → Customer Portal flow is built and has passed
  `docs/strategy/beta-testing-strategy.md`'s Phase 2 exit criteria
  (10-15 real voluntary beta upgrades, zero end-to-end flow failures
  across 2+ browsers, no unresolved billing issue >48h).
- The AI support agent's escalation path (§4 of
  `docs/strategy/customer-service-ai-strategy.md`) has been exercised for
  real during Phase 2 of the beta — i.e. at least one real billing/
  account question has gone through the actual escalation flow and been
  handled, not just designed on paper.
- **Legal/VAT setup is confirmed complete** (see
  `docs/strategy/subscription-strategy.md`'s open question #2) — this is
  a hard blocker on taking real payments, not a soft target, and it's
  entirely Kiril's/his accountant's task, not something this rollout
  plan can sequence around.

### Stage 3 → Stage 4 gate (referral program + full marketing automation
live)
- Paid tiers have run for at least one full billing cycle with dunning/
  renewal automation observed working on a real failed payment or real
  renewal (not just tested synthetically).
- Email drip automation (`docs/strategy/marketing-strategy.md` §3) is
  live and its first automated sends have gone out without requiring
  manual intervention.

---

## 3. Why paid tiers don't launch simultaneously with the redesign

**Recommendation — needs Kiril's sign-off.** Launching new paid pricing
at the exact same moment as a visual/workflow redesign conflates two
different pieces of user feedback (is the new product good? vs. is it
worth paying for?) and risks a redesign-related bug being read as "the
paid product is broken," which is reputationally worse than the same bug
in a free product. Sequencing paid tiers after the redesign beta's exit
criteria are met means the product is already validated as good before
money changes hands — a materially lower-risk order.

---

## 4. Rollout checklist (the "nothing launches still needing Kiril
personally in the loop" test, made concrete)

Before Stage 3 (paid tiers go live), every item below must be true —
this is the direct operationalization of the founder's core constraint,
turned into a checklist rather than a principle:

- [ ] A support ticket can be filed, answered by the AI agent, and
      (for the narrow escalation categories only) routed to Kiril
      **without Kiril having built or triggered anything by hand** in
      the loop (`docs/strategy/customer-service-ai-strategy.md`).
- [ ] A new visitor can sign up for a paid tier, get billed, and later
      cancel or have a failed payment retried **with zero manual account
      administration** (`docs/strategy/subscription-strategy.md` §3-4).
- [ ] New SEO content pages are being generated on a schedule with **no
      manual publishing step** (`docs/strategy/marketing-strategy.md`
      §2).
- [ ] A beta/user bug report reaches the engineering backlog as a
      labeled, triaged GitHub issue **without Kiril manually relaying
      an email** (`docs/strategy/beta-testing-strategy.md` §3).
- [ ] The one deliberately-human step that remains — refund/legal
      disputes and community-seeding posts — is explicitly bounded and
      small, not open-ended (see the "what stays manual" sections in the
      subscription and marketing documents).

If any box isn't checked, that's a real reason to hold Stage 3, not a
reason to quietly ship anyway and absorb the manual burden — this is the
whole point of gating on readiness rather than a date (§2).

---

## 5. Rollback / kill-switch posture

**Recommendation — needs Kiril's sign-off.** Because the free product
stays live and untouched by every stage above (per §1, this is a
re-launch layered onto an already-live product, not a cutover), the
rollback story for each stage is simple and low-risk:

- **Stage 1-2 (redesign/beta) rollback:** the redesign ships as normal
  frontend changes to `index.html` through the existing Bossy/Missy
  review-and-merge process — if a serious issue surfaces, it reverts
  like any other change, with no subscriber-facing consequence since no
  paid tier exists yet.
- **Stage 3 (paid tiers) rollback:** because billing runs entirely
  through Stripe (`docs/strategy/subscription-strategy.md` §3-4), a
  serious problem can be contained by pausing new checkouts in the
  Stripe dashboard (one click, no code change) without touching the free
  product at all — existing subscribers are unaffected, and the "how do
  I get help" support path stays live throughout.

---

## Open questions for Kiril

1. **Whether the readiness-gates-not-dates approach (§2) is acceptable**,
   given it means no committed launch date can be given up front — this
   is the direct consequence of gating on the AI-first automation
   actually existing before scaling up, per the founder's own brief, but
   it's worth confirming explicitly since it trades a firm date for
   lower operational risk.
2. **Legal/VAT completion timeline** (Stage 2→3 gate) — this sits
   entirely outside Selly's scope and this plan can't estimate it; it's
   worth Kiril starting this in parallel with Stage 1 (the redesign
   beta) rather than after, since it's the one gate with a long,
   externally-controlled lead time.
3. Confirm the **Stage 0→1 gate's list of backlog items** is the right
   minimum bar — Selly picked items 8/9 (and the already-fixed item 5)
   as "enough redesign to meaningfully beta-test," not the full 8-16
   range, to avoid delaying the beta behind every planned feature;
   confirm this trade-off is right or whether a larger minimum feature
   set is wanted before opening to testers.
