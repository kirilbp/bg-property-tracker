// Node-runnable correctness check for the detail-fields retry loop added
// to showListingDetail() in index.html (2026-09-29 fix): the lazy by-id
// `merged_listings` fetch now asks for property_type_raw/agency_name/etc.
// (previously missing entirely - see docs/backlog.md item 73) plus three
// BRAND NEW columns (coords_checked/specs_checked/detail_checked) that
// don't exist on the live table until their own supabase/schema.sql
// migration is applied by hand. A plain, un-retried `.select()` naming a
// column Postgres doesn't have fails the WHOLE query - which would take
// description/photos/price_history (already working today) down with it
// too - so the fetch now loops, stripping one missing column at a time via
// the REAL, unmodified stripMissingSelectColumn() (the same helper
// fetchAllRows() already uses and tests/fetch_all_rows_concurrency.js
// already covers for a single missing column) until the query succeeds.
//
// This test exercises the SEQUENCE this fetch can hit in practice - up to
// three of its own new columns missing at once, stripped one at a time -
// rather than re-testing stripMissingSelectColumn() itself in isolation
// (already covered elsewhere).
//
// Run with: node tests/detail_fields_missing_column_retry.js

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

function loadStripMissingSelectColumn() {
  const html = fs.readFileSync(INDEX_HTML_PATH, 'utf8');
  const src = extractBetween(
    html,
    'const _MISSING_SELECT_COLUMN_RE',
    'function computeUnverified(l) {',
    'stripMissingSelectColumn()'
  );
  const context = {};
  vm.createContext(context);
  vm.runInContext(src, context, { filename: 'index.html (extracted stripMissingSelectColumn block)' });
  assert.strictEqual(typeof context.stripMissingSelectColumn, 'function', 'stripMissingSelectColumn() not found - extraction markers moved?');
  return context.stripMissingSelectColumn;
}

const stripMissingSelectColumn = loadStripMissingSelectColumn();

// Mirrors the exact retry-loop shape now in showListingDetail()'s
// _detailFieldsFetched block - real stripMissingSelectColumn(), a mock
// query function standing in for `sb.from('merged_listings').select(...)
// .eq(...).maybeSingle()`.
async function fetchWithRetry(queryFn, initialColumns) {
  let detailColumns = initialColumns;
  for (;;) {
    const { data, error } = await queryFn(detailColumns);
    if (!error) return { data, columnsUsed: detailColumns };
    const narrowed = stripMissingSelectColumn('merged_listings', detailColumns, error.message);
    if (!narrowed) return { data: null, columnsUsed: detailColumns, gaveUp: true };
    detailColumns = narrowed;
  }
}

let failures = 0;
function check(name, cond, detail) {
  if (!cond) {
    failures++;
    console.error(`FAIL: ${name}${detail ? '\n  ' + detail : ''}`);
  } else {
    console.log(`PASS: ${name}`);
  }
}

const FULL_COLUMNS =
  'description,photos,price_history,property_type_raw,construction_type,' +
  'coords_checked,specs_checked,detail_checked';

function missingColumnError(col) {
  return { data: null, error: { message: `column merged_listings.${col} does not exist` } };
}

(async () => {
  // All three new columns missing at once (the real pre-migration
  // production shape) - must strip all three, one retry per column, and
  // still return the real row's other fields once the query finally
  // succeeds.
  {
    let calls = 0;
    const result = await fetchWithRetry(async (columns) => {
      calls++;
      if (columns.includes('coords_checked')) return missingColumnError('coords_checked');
      if (columns.includes('specs_checked')) return missingColumnError('specs_checked');
      if (columns.includes('detail_checked')) return missingColumnError('detail_checked');
      return { data: { description: 'real description text', property_type_raw: '2-стаен' }, error: null };
    }, FULL_COLUMNS);
    check('all 3 new columns missing -> stripped one at a time, real data still returned',
      result.data && result.data.description === 'real description text' && result.data.property_type_raw === '2-стаен',
      `got: ${JSON.stringify(result)}`);
    check('exactly 4 attempts made (3 failures + 1 success), not unbounded', calls === 4, `calls=${calls}`);
    check('final columnsUsed has none of the 3 new columns left',
      !/coords_checked|specs_checked|detail_checked/.test(result.columnsUsed),
      result.columnsUsed);
  }

  // No columns missing at all (migration already applied) - succeeds on
  // the first attempt, no retries wasted.
  {
    let calls = 0;
    const result = await fetchWithRetry(async () => {
      calls++;
      return { data: { description: 'ok', coords_checked: true }, error: null };
    }, FULL_COLUMNS);
    check('migration already applied -> succeeds on first attempt', calls === 1, `calls=${calls}`);
    check('real coords_checked value passed through', result.data.coords_checked === true);
  }

  // A real, different error (not a missing-column shape) must NOT loop
  // forever - stripMissingSelectColumn() returns null immediately and the
  // fetch gives up gracefully instead of retrying with the same columns.
  {
    let calls = 0;
    const result = await fetchWithRetry(async () => {
      calls++;
      return { data: null, error: { message: 'JWT expired' } };
    }, FULL_COLUMNS);
    check('unrelated real error -> gives up after exactly 1 attempt, no infinite loop',
      calls === 1 && result.gaveUp === true, `calls=${calls}, result=${JSON.stringify(result)}`);
  }

  if (failures > 0) {
    console.error(`\n${failures} check(s) failed.`);
    process.exit(1);
  }
  console.log('\nAll checks passed.');
})();
