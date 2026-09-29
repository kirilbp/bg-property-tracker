// Node-runnable correctness check for index.html's specsSellerEmptyMessage()
// (2026-09-29 fix: renderSpecsPanel()/renderSellerPanel()'s previous
// "${portal} doesn't publish ... yet" wording unconditionally blamed the
// portal for every empty case - a live data audit against the real
// committed data/history_bazar.json.gz found that's usually one of two
// very different, non-portal causes instead: no extractor exists for this
// portal at all, or this listing's own page just hasn't been (re)checked
// yet under a working one - see backfill_detail_bazar.py's own module
// docstring and sync_to_supabase.py's SOURCE_FIELDS comment for the real
// numbers behind this).
//
// Run with: node tests/specs_seller_empty_message.js
//
// Same "extract the real, unmodified source out of index.html and run it
// in a vm context" approach as tests/fetch_all_rows_concurrency.js (see
// that file's own comment for why - no JS test harness/dependency exists
// in this repo). escapeHtml() (a one-line const, defined far earlier in
// the file, with no dependency of its own) is extracted separately rather
// than pulling everything in between, which would drag in large amounts
// of top-level app code that assumes a real DOM/window - the actual
// specsSellerEmptyMessage() region is small and self-contained (only
// const/Set/function declarations, no top-level DOM calls), unlike the
// multi-thousand-line span between the two.

'use strict';

const vm = require('vm');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const INDEX_HTML_PATH = path.join(__dirname, '..', 'index.html');

function extractBetween(html, startMarker, endMarker, label) {
  const start = html.indexOf(startMarker);
  const end = html.indexOf(endMarker, start);
  if (start === -1 || end === -1 || end <= start) {
    throw new Error(`Could not locate ${label} in index.html - markers moved? (start=${start}, end=${end})`);
  }
  return html.slice(start, end);
}

function loadRealSource() {
  const html = fs.readFileSync(INDEX_HTML_PATH, 'utf8');
  const escapeHtmlLine = extractBetween(html, 'const escapeHtml =', '\n', 'escapeHtml').trim();
  const specsBlock = extractBetween(
    html,
    'const SPECS_CAPABLE_PORTALS',
    'function renderSpecsPanel(l) {',
    'SPECS_CAPABLE_PORTALS/SPECS_CHECKED_FIELD_BY_PORTAL/specsSellerEmptyMessage'
  );
  return `${escapeHtmlLine}\n${specsBlock}`;
}

const context = {};
vm.createContext(context);
vm.runInContext(loadRealSource(), context, { filename: 'index.html (extracted specs-empty-message block)' });
const { specsSellerEmptyMessage } = context;
assert.strictEqual(typeof specsSellerEmptyMessage, 'function', 'specsSellerEmptyMessage() not found - extraction markers moved?');

let failures = 0;
function check(name, actual, expectedSubstring) {
  if (typeof actual !== 'string' || !actual.includes(expectedSubstring)) {
    failures++;
    console.error(`FAIL: ${name}\n  expected to include: ${JSON.stringify(expectedSubstring)}\n  got: ${JSON.stringify(actual)}`);
  } else {
    console.log(`PASS: ${name}`);
  }
}

// 1. A portal with no specs/contact extractor at all (homes.bg) must
// never get the portal-blaming "doesn't publish" claim, checked or not -
// this is our own coverage gap, stated as such, regardless of any
// checked-flag value.
check(
  'homes.bg (no extractor at all) -> coverage-gap wording, not portal blame',
  specsSellerEmptyMessage({ portal: 'homes.bg', detail_checked: true }, 'property type, construction, or floor details'),
  "aren't tracked for homes.bg listings yet"
);
check(
  'homes.bg never claims "doesn\'t publish"',
  (() => {
    const msg = specsSellerEmptyMessage({ portal: 'homes.bg' }, 'agency or contact details');
    return msg.includes("doesn't publish") ? 'CONTAINS BLAME CLAIM: ' + msg : 'no blame claim';
  })(),
  'no blame claim'
);

// 2. bazar.bg (capable, has a synced specs_checked marker) with
// specs_checked missing/false -> "not checked yet" wording, not a claim
// the portal itself lacks the data.
check(
  'bazar.bg, specs_checked missing -> "not checked yet" wording',
  specsSellerEmptyMessage({ portal: 'bazar.bg' }, 'property type, construction, or floor details'),
  "hasn't been checked"
);
check(
  'bazar.bg, specs_checked: false -> "not checked yet" wording',
  specsSellerEmptyMessage({ portal: 'bazar.bg', specs_checked: false }, 'agency or contact details'),
  "hasn't been checked"
);

// 3. bazar.bg with specs_checked: true and still nothing found -> the
// portal-level claim is now actually justified.
check(
  'bazar.bg, specs_checked: true -> justified "doesn\'t publish" claim',
  specsSellerEmptyMessage({ portal: 'bazar.bg', specs_checked: true }, 'property type, construction, or floor details'),
  "bazar.bg doesn't publish property type, construction, or floor details"
);

// 4. alo.bg/imoti.bg (capable, but no synced checked-marker for this
// portal yet) fall straight through to the "doesn't publish" branch,
// unconditionally - same behavior as before this fix, not a regression.
check(
  'alo.bg (capable, no synced checked-field) -> falls through unconditionally',
  specsSellerEmptyMessage({ portal: 'alo.bg' }, 'agency or contact details'),
  "alo.bg doesn't publish agency or contact details"
);
check(
  'imoti.bg (capable, no synced checked-field) -> falls through unconditionally',
  specsSellerEmptyMessage({ portal: 'imoti.bg' }, 'property type, construction, or floor details'),
  "imoti.bg doesn't publish property type, construction, or floor details"
);

if (failures > 0) {
  console.error(`\n${failures} check(s) failed.`);
  process.exit(1);
}
console.log('\nAll checks passed.');
