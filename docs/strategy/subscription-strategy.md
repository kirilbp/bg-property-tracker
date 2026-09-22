# Subscription strategy

Owned by Selly. Companion to `docs/strategy/launch-strategy.md`,
`docs/strategy/marketing-strategy.md`, and
`docs/strategy/customer-service-ai-strategy.md` — read
`docs/strategy/README.md` first for how these five fit together.

**Grounding:** `docs/property-filter-spec.md` section 0 (Property Filter's
own plan structure, observed directly from their Account Settings
screens), `docs/decisions.md`'s 2026-09-22 entry (login removed entirely,
by Kiril's explicit instruction), `docs/backlog.md` (current feature set
and what's still ahead), and the fact that imotenradar.com is currently a
static GitHub Pages site (`CNAME` file present) with **zero payment
infrastructure, zero accounts, and zero subscription logic today.** This
document is a build-from-zero plan, not a tune-up of something existing.

---

## 1. The central tension this strategy has to resolve

Kiril's explicit, recent, direct instruction was "I want login removed
completely," and it was removed — `index.html` now has no auth system at
all; saved listings, Lead Generators, and reminders are plain
`localStorage`, no accounts, no server round-trip (`docs/decisions.md`,
2026-09-22).

But **a subscription product cannot exist without some way to know who
has paid.** That is not optional — Stripe (or any payment processor)
needs an identity to attach a subscription to, and imotenradar needs a
way to check "does this visitor's session correspond to an active
subscription" before unlocking a gated feature. There is no way around
needing *some* identity token for paying users.

**Recommendation — needs Kiril's sign-off:** this is not a contradiction
of the login-removal decision if scoped correctly. The thing that was
removed was a **mandatory, account-gated front door** — every visitor,
free or not, had to log in to use core features (the two "log in to use
this" gate cards on Lead Generators and Dashboard). The subscription
system below does **not** bring that back:

- The **free tier stays exactly as it is today** — no login, no account,
  full `localStorage`-based Lead Generators/saved listings/reminders,
  available to every visitor with zero friction. This is the large
  majority of traffic and it should never see an account prompt.
- **Only the checkout flow for a paid tier** introduces an identity
  token, and it is the lightest one available: **Stripe Checkout**
  captures the paying customer's email itself (Stripe is the system of
  record for "who is a customer," not a rebuilt Supabase Auth system).
  imotenradar never needs to store a password. Post-checkout, the
  customer gets a **magic-link email** (passwordless, one click, no
  password to forget/reset/support) that sets a long-lived signed token
  in their browser, which the frontend checks client-side against a
  small serverless function (see §4) to unlock paid-tier UI.
- This is architecturally nothing like the removed system (no login
  modal, no blocking gate on free features, no password flow) — it only
  exists for the minority of visitors who choose to pay, and only at the
  moment they choose to.

If Kiril wants the free tier to remain the *only* tier indefinitely
(monetizing some other way, e.g. ads or a one-time report purchase
instead of recurring subscriptions), that changes this document
substantially — flagged as the first open question below.

---

## 2. Tier structure

**Recommendation — needs Kiril's sign-off.** `docs/property-filter-spec.md`
section 0 documents Property Filter itself gating *quantities*, not
*features* (Nosy's spec calls this "a generic SaaS pattern, not
UK-specific data," i.e. safe to reuse in principle) — but that pattern
assumes Property Filter's tiers sit behind its own account system.
imotenradar's free tier deliberately has none (§1), and that changes
which gate mechanism actually works here:

| Tier | Price (rec.) | Gate mechanism |
|---|---|---|
| **Free** | €0 | Full current feature set, **unchanged**: search, filters, city/oblast browse, unlimited saved listings, unlimited Lead Generators, unlimited reminders — exactly as it works today, no new caps. Not included: CSV/export, full Comparables + Area Data (item 10), Market Data hub (item 11), Send Letters (item 12), Deal Calculator (item 13), the email digest below (once it's actually scoped), ads/no-ads is Kiril's call (see open questions) |
| **Investor** (mid, default recommended tier) | €14.99/mo or €149/yr | Everything in Free, plus: full Comparables + Area Data access (item 10), CSV export |
| **Deal Maker** (top) | €39.99/mo or €399/yr | Everything in Investor, plus Market Data hub (item 11) full access, Send Letters campaigns (item 12, once shipped), Deal Calculator (item 13, once shipped), priority position in the AI support escalation queue (see `docs/strategy/customer-service-ai-strategy.md`) |

**Why feature-gating instead of quantity-gating, despite Property
Filter's own precedent:** an earlier draft of this table capped the free
tier's Lead Generators/saved listings (3 / 20) the way Property Filter
does. That's dropped here for two compounding reasons, not just
tidiness:

1. **It would contradict §1's own load-bearing claim** that the free
   tier "stays exactly as it is today" — a cap that doesn't exist in the
   product today is a real product change, not a description of the
   status quo, and §1 is the paragraph this whole document leans on to
   argue the subscription system doesn't quietly reintroduce the
   friction Kiril explicitly removed.
2. **It wouldn't actually function as a paywall.** The free tier has no
   accounts and no login (`docs/decisions.md`, 2026-09-22) — Lead
   Generators and saved listings live in plain, unauthenticated
   `localStorage`. A visitor who hits a "3 Lead Generators" cap can
   clear site data, open a private window, or use a second browser and
   get another 3 for free, with zero friction and nothing to detect
   server-side. A quantity cap only works once there's an identity to
   count against — exactly the account infrastructure §1 argues this
   document avoids building for the free majority.

Feature-gating avoids both problems: it never touches the free tier's
existing unlimited local storage, and it gates things that are
inherently server-side (Comparables/Area Data aggregation, CSV export,
Market Data hub, campaign tooling) where "who has access" is already
something the paid checkout flow (§3-4) has to resolve regardless —
there's no separate enforcement problem to solve.

**Email digest — Recommendation, not yet scoped, needs Kiril's
sign-off:** a periodic (daily or weekly) email digest of new/changed
matches for a user's saved Lead Generators would be a strong
Investor-tier value-add, but it is **new, unscoped build work**, not
something `docs/backlog.md` item 9 already covers. Item 9 builds the
in-app "new since last check" badge only — an in-app notification, no
outbound email. `docs/backlog.md`'s "Gaps in Nosy's spec" section
explicitly lists "alert-email behavior (vs. in-app notifications)" as an
open, unspecified gap needing its own follow-up capture, not confirmed
scope. Before this can be promised at a price point it needs: (a) its
own scoping pass (frequency, content, unsubscribe handling), (b) the
outbound-email sending infrastructure §4 below already specs for
transactional email (Resend/Postmark), extended from one-off
transactional sends to a scheduled/triggered digest job, and (c) a
decision on whether it ships at Investor-tier launch or as a fast-follow.
Recommend treating it as a near-term roadmap item rather than a
launch-blocking one — the Investor tier is still viable on Comparables +
Area Data access and CSV export alone. See
`docs/strategy/marketing-strategy.md` §3, which flags this exact same
gap for the same feature — the two documents describe one shared,
not-yet-scoped build item, not two independent ones.

**Do not gate the core listing data itself** (search, filters, browse) —
per the design-guidelines' positioning as a serious investor tool, the
value proposition is workflow (saved searches, alerts, comparables,
campaigns), not access to listings that are, after all, aggregated from
public portals. Gating the underlying data would also cut against SEO
(see `docs/strategy/marketing-strategy.md` §2) since indexable listing
pages need to be crawlable by Google, not paywalled.

**Currency: price in EUR, not BGN.** Bulgaria adopted the euro on 1
January 2026, and it has been the sole legal currency since 1 February
2026 (dual BGN/EUR price display was only a transitional requirement
through 8 August 2026, which has already passed as of this document).
Pricing, invoicing, and Stripe's account currency should all be EUR
outright — no dual-currency complexity needed. (Source: Council of the
EU / ECB confirmations of the 1 January 2026 adoption date.)

---

## 3. Self-serve signup, upgrade, downgrade, cancel

All of this should run through **Stripe Checkout + Stripe Customer
Portal** — Stripe's own hosted, no-code-required flows — rather than
building any of it in `index.html` or a custom backend:

- **Signup/upgrade:** a "Go Investor" / "Go Deal Maker" button opens a
  Stripe Checkout session (hosted by Stripe, PCI compliance is Stripe's
  problem, not imotenradar's). On success, Stripe's webhook fires to a
  small serverless function (§4) that (a) sends the magic-link email and
  (b) writes the subscription status to a minimal database.
- **Downgrade/cancel:** the Stripe **Customer Portal** (a hosted page
  Stripe provides, linked from the account/billing area) lets the
  customer change plan, update card, or cancel with zero custom UI
  needed. This is a checkbox-configuration in the Stripe dashboard, not
  a build task.
- **Failed payments / dunning:** Stripe's built-in **Smart Retries** plus
  its automated dunning emails (configurable in Stripe dashboard, no
  code) handle failed-card recovery — retries on a schedule, automatic
  emails to update payment info, automatic downgrade-to-free (not
  cancellation of the account) after N failed retries so a lapsed payer
  doesn't lose their saved data, just paid-tier access.
- **Manual account admin Kiril should never have to do:** issuing
  refunds for edge cases (partial month, etc.) — Stripe dashboard handles
  this in one click when it does come up; plan changes; cancellations;
  failed-payment follow-up. All of the above is self-serve or
  Stripe-automated by design.

## 4. Minimal technical shape (for whoever builds this — not a request
for Bossy/Dessy to act on now, since this doc doesn't touch code)

Given imotenradar is a static GitHub Pages site today, the lightest
architecture that avoids standing up a full backend:

1. **Stripe Checkout** (hosted) for payment collection.
2. **One small serverless function** (Cloudflare Worker or a Vercel/
   Netlify function — pick whichever is free-tier-friendly, this is an
   implementation detail) that: receives Stripe webhooks, writes
   `{email, tier, status, current_period_end}` to a lightweight store,
   and sends the magic-link email (e.g. via Resend or Postmark's
   transactional API — cheap, simple, good deliverability).
3. **Where to store subscription status:** Supabase is already paid for
   (Pro plan per `docs/backlog.md` item 6) and already has a schema with
   `auth.users`-based RLS that's currently dormant (per the 2026-09-22
   login-removal decision) — reusing Supabase here (a new
   `subscriptions` table keyed by email, *not* reviving the old
   `auth.users`-gated login flow) avoids paying for a second database
   and reuses infrastructure Kiril already has. This is a build detail
   for whoever picks it up, flagged here only so it isn't rebuilt from
   scratch unnecessarily.
4. **Frontend check:** on page load, if a magic-link token is present in
   `localStorage`, one lightweight fetch to the serverless function
   confirms tier + status and unlocks the relevant UI. No token, no
   fetch — the free-tier majority of visitors never touch this path,
   preserving today's fast, backend-free experience for them.

This is intentionally the smallest possible build — no rebuilt login
modal, no password reset flow, no session management beyond a single
signed token Stripe/the magic link already handles.

---

## 5. What stays manual (and why it's small)

- **Kiril approving Stripe account setup and connecting a Bulgarian/EU
  bank account** — one-time, not recurring; needs his legal entity
  details (see open questions).
- **Occasional refund judgment calls** that fall outside a standard
  policy (e.g. a dispute) — the AI support agent should have a clear,
  narrow written refund policy it can apply automatically for the common
  case (e.g. "any cancellation within 14 days, full refund, no
  questions") per `docs/strategy/customer-service-ai-strategy.md`, with
  only genuine disputes escalated.
- Everything else in this document is self-serve or Stripe-automated by
  design — there is no recurring manual billing/account-admin task
  planned here.

---

## Open questions for Kiril

1. **Exact price points.** €14.99/€39.99 above are reasoned placeholders
   (roughly mid-market for a niche B2B SaaS investor tool, well under
   Property Filter's £99+VAT since imotenradar is a newer, single-market
   product) — needs your real sign-off, ideally validated against beta
   testers' actual willingness-to-pay (see
   `docs/strategy/beta-testing-strategy.md`).
2. **Legal entity and VAT.** Selling a recurring SaaS subscription to EU
   consumers/businesses triggers VAT-on-digital-services obligations
   (potentially OSS/MOSS registration) and needs a registered entity to
   contract through and receive payouts — this is a legal/accounting
   question outside Selly's scope; flagging it as a hard blocker on
   taking real payments, not something to hand-wave past.
3. **Does the free tier stay free forever, or is this a freemium
   funnel toward eventually requiring payment for more?** Assumed
   freemium-forever above (free tier is the SEO/marketing engine per
   `docs/strategy/marketing-strategy.md`) — confirm.
4. **Ads on the free tier?** Not recommended by Selly (clashes hard with
   the "classy/luxurious" positioning in `docs/design-guidelines.md` —
   ad units are visually the opposite of restraint) but flagged since
   it's a real alternative/supplementary revenue lever some free-tier
   products use.
5. **Should paid tiers launch at the same time as the redesign
   (`docs/backlog.md` items 8-16), or after, once there's a larger free
   user base to convert?** Recommendation is in
   `docs/strategy/launch-strategy.md` §3 (paid tier launches after the
   beta and after the core redesign ships, not simultaneously) — confirm
   you agree with that sequencing.
6. **Annual-plan discount size** (proposed ~17% off, i.e. 2 months free,
   a common SaaS default) — confirm or adjust.
