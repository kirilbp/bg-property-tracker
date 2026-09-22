# Customer service AI strategy

Owned by Selly. See `docs/strategy/README.md` for how this fits against
the other four documents. This is the strategy that has to exist before
`docs/strategy/subscription-strategy.md`'s paid tiers or
`docs/strategy/launch-strategy.md`'s public launch can go live without
requiring Kiril personally in the loop for routine support.

**Grounding:** imotenradar.com is a static GitHub Pages site today, no
backend server of its own beyond GitHub Actions workflows and a mostly-
dormant Supabase project (`docs/backlog.md`, `docs/decisions.md`). There
is no support channel of any kind today. This is a build-from-zero plan.

---

## 1. What support volume will actually look like, and why AI-first is
realistic here

The product surface is narrow and well-documented: a listings
aggregator with saved searches, a (planned) pipeline, comparables, and
eventually subscriptions. The realistic support-ticket taxonomy, in
descending expected volume:

1. **"A listing looks wrong"** (stale price, marked removed but still
   live, wrong category, wrong location) — this is the single largest
   expected category, precisely *because* the product scrapes 8 portals
   and Missy's own audits (`docs/missy-findings/`) confirm real,
   ongoing data-quality issues are a normal, expected feature of this
   kind of product, not an edge case.
2. **"How do I..."** FAQ (how do Lead Generators work, what does the
   motivation score mean, how to filter by area) — fully answerable from
   the product's own existing feature set (`docs/property-filter-spec.md`,
   `docs/backlog.md`) and requires no human judgment at all.
3. **Account/subscription issues** (payment failed, want to
   upgrade/downgrade/cancel, didn't receive magic-link email) — the large
   majority of this volume should never reach a support channel at all,
   because `docs/strategy/subscription-strategy.md` routes it through
   Stripe's self-serve Customer Portal and automated dunning emails. What
   *does* reach support here is mostly "I'm confused/it's not working,"
   not "please do X for me manually."
4. **Bug reports** (UI broken, filter not working, etc.) — structured
   intake feeds directly into the same pipeline as beta feedback (see
   `docs/strategy/beta-testing-strategy.md` §3), not a separate flow.
5. **Genuinely novel problems, refund disputes, legal/GDPR complaints** —
   low volume by nature, and the only category that should reach Kiril.

This taxonomy is narrow enough, and #1/#2 are answerable enough from
data the product already has, that an AI agent handling "the large
majority" of volume (per the founder's brief) is a realistic target from
day one, not an aspirational one.

---

## 2. Architecture

**Recommendation — needs Kiril's sign-off** on the build-vs-buy choice
below.

### Option A (recommended to start): a hosted AI helpdesk tool

Use a vendor that already ships an LLM-powered support agent trained on
a knowledge base, rather than building a custom RAG pipeline against a
static site with no backend. Concretely: **Crisp (with its AI agent
add-on) or Intercom Fin** — both let you feed a knowledge base (FAQ
articles, written once, covering the "How do I..." category above) and
answer chat/email questions against it, with a clean escalation path to
a human inbox when the AI can't answer confidently.

- **Why buy over build:** imotenradar has no backend today beyond
  GitHub Actions + Supabase — standing up a custom Claude-API-backed
  support widget (auth, rate limiting, conversation storage, abuse
  handling) is real engineering scope that competes with the
  `docs/backlog.md` roadmap for Bossy/Dessy's time. A hosted tool gets
  to "AI handles most tickets" in days, not weeks, for a low monthly
  fee that scales with ticket volume (i.e. costs little pre-launch).
- **Why Crisp specifically as the lead recommendation:** meaningfully
  cheaper than Intercom at low volume (relevant pre-revenue/early-paid),
  has a chat widget that can be styled to match the
  `docs/design-guidelines.md` restrained aesthetic (no default bright
  SaaS-blue chat bubble), and supports the knowledge-base-grounded AI
  agent pattern needed here. Intercom Fin is the stronger option if
  budget stops being a constraint post-launch — flagged as the fallback,
  not a hard recommendation either way (needs Kiril's own quick trial of
  both against the real FAQ content before committing).

### Option B (later, if ticket volume or cost justifies it): custom
agent on the Claude API

Once there's a backend anyway (the subscription serverless function in
`docs/strategy/subscription-strategy.md` §4), a custom support agent
using the Claude API with the FAQ + Missy's data-quality-issue patterns
as context becomes a natural next step — cheaper at higher volume than a
per-seat/per-resolution vendor fee, and can be given direct tool access
to check a user's actual subscription status or a listing's actual
scrape history (something a generic hosted tool can't do without deep
integration work). **Not recommended to start with** — it's strictly
more build effort for a launch that doesn't need it yet.

---

## 3. The knowledge base (what the AI answers from)

Write once, maintain as the product changes, source directly from
existing docs so nothing is invented:

- **FAQ articles** covering: what imotenradar does and doesn't do (it
  aggregates public listings, it does not itself list properties or
  represent sellers), how saved listings/Lead Generators/reminders work
  and that they're stored in-browser (`docs/decisions.md`'s 2026-09-22
  entry — this is genuinely important to document clearly, since
  `localStorage`-only storage means **switching browsers/devices loses
  saved data**, a real, foreseeable point of confusion worth answering
  proactively rather than waiting for it to become a ticket), what the
  motivation score means (`docs/backlog.md` item 7's 5-component
  formula, translated into plain language), subscription tier
  differences and how to upgrade/downgrade/cancel (links straight to the
  Stripe Customer Portal).
- **A living "known data quirks" article**, auto-updatable: since Missy's
  own daily audit process already produces `docs/missy-findings/<date>.md`
  and files GitHub issues for real data-quality problems
  (`docs/decisions.md`'s 2026-09-21 entry), the AI agent's knowledge base
  should be able to say "yes, we know about X, it's being worked on" for
  any issue already filed, rather than treating every "this listing looks
  wrong" report as novel. Concretely: a short script (someone on the
  engineering side, not Selly, would build this) that summarizes open
  `missy-finding` and `data quality` labeled GitHub issues into a
  knowledge-base article the helpdesk tool re-ingests periodically. This
  turns an existing internal QA pipeline into a customer-facing "we know,
  we're on it" answer with no new manual step for Kiril.

---

## 4. Escalation path — narrow, and explicit about why each item needs
a human

**Recommendation — needs Kiril's sign-off** on exactly how these route
and how much of his own time he wants to commit even to this narrow
list (see open questions).

Escalate to Kiril (or a queue he checks on his own schedule, not live
chat) only for:

1. **Refund disputes that fall outside the standard policy** (see
   `docs/strategy/subscription-strategy.md` §5's proposed "14-day,
   automatic, no questions" policy — anything outside that window or
   circumstance).
2. **Legal/GDPR/data-removal complaints** — e.g. someone asking for
   their scraped listing data removed, or a formal complaint. These
   have real legal weight and a wrong automated response is worse than
   a slow correct one.
3. **A genuinely novel bug** the knowledge base has no answer for and
   that isn't already a known Missy finding — the AI's job here is not
   to guess, but to acknowledge, collect structured detail (screenshot,
   URL, browser), and file it the same way beta bug reports are filed
   (`docs/strategy/beta-testing-strategy.md` §3), not to leave the user
   hanging.
4. **Security reports** (e.g. someone reporting a vulnerability) — always
   human, always fast-tracked, never left to the AI to triage.
5. **Anything the AI's own confidence is low on** — both Crisp's and
   Intercom's AI agents support a "hand off to human if uncertain"
   threshold; set it conservatively at first (escalate more than strictly
   necessary) and tighten it once real ticket data shows what's safe to
   automate further.

**Explicit non-automatable item:** #2 above (legal/GDPR complaints) is
the one category in this whole strategy set that should **not** be
pushed toward automation even as tooling improves — this is a
compliance/liability judgment call, not a knowledge gap an AI will
eventually close. Named plainly per the founder's brief rather than
hand-waved.

---

## 5. Bug report and data-issue intake

Reuse, don't rebuild: the "Report a bug for this advert" pattern already
speced (`docs/property-filter-spec.md` section 5, "flagged as
replicable... useful given imotenradar is scraper-based and will have
data-quality issues too") should feed the **same** structured-intake →
auto-triage → GitHub issue pipeline the beta program uses (see
`docs/strategy/beta-testing-strategy.md` §3) — one pipeline for both
beta feedback and ongoing post-launch bug reports, not two. This keeps
Kiril's review surface to a single place (`docs/backlog.md`'s standing
GitHub-issue flow, already the team's real working pattern per
`docs/decisions.md`) rather than a separate customer-service ticket
queue that never talks to engineering.

---

## 6. Metrics to watch (so "AI handles most volume" is measured, not
assumed)

- **AI resolution rate**: % of tickets closed without human escalation.
  Target 80%+ within the first two months of the beta (see
  `docs/strategy/beta-testing-strategy.md` for the exit criteria this
  feeds into) — both Crisp and Intercom report this out of the box.
- **Escalation queue size/week** — should stay small and roughly flat as
  volume grows if the knowledge base is doing its job; a rising trend
  means the KB needs updating, not that more human hours are needed.
- **Time-to-first-response** on the AI side should be near-instant by
  construction; track time-to-resolution on the escalated queue
  separately, since that's the number that reflects Kiril's actual time
  cost.

---

## Open questions for Kiril

1. **Crisp vs Intercom Fin vs building custom** — Selly's lead
   recommendation is Crisp to start (§2), but this is a real spend
   decision and a short hands-on trial of both against real FAQ content
   would settle it faster than more analysis here.
2. **How much of his own time is he willing to spend even on the narrow
   escalation path** (§4)? This shapes whether escalations go to a live
   channel (Slack/email, checked reactively) or a batched daily digest —
   Selly's default assumption is a daily/twice-weekly digest, not live
   chat, to protect his time, but that's his call to make explicitly.
3. **Refund policy specifics** (14-day window proposed in
   `docs/strategy/subscription-strategy.md` §5) — needs his sign-off
   since it's a real financial policy, not just a support-flow detail.
4. **Language.** The product and its users are Bulgarian-market; should
   the AI agent support Bulgarian-language chat from day one, or
   English-only initially with Bulgarian added once volume justifies the
   extra knowledge-base translation work? Recommendation — needs Kiril's
   sign-off: **Bulgarian from day one** given the target market, since
   both Crisp and Intercom Fin support multilingual knowledge bases and
   the FAQ content is short enough that translating it once is a small,
   one-time cost, not an ongoing manual burden.
