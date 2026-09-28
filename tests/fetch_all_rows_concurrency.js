// Node-runnable correctness + speed check for index.html's fetchAllRows()
// bounded-concurrency rewrite (backlog item 71: merged_listings bulk load
// was ~215-290 sequential round trips, 3-5 real minutes end to end).
//
// Run with: node tests/fetch_all_rows_concurrency.js
//
// There is no existing JS test harness anywhere in this repo (checked:
// no package.json, no *.test.js/*.spec.js, no committed Playwright/jsdom
// setup - grep confirms it) - every other test is Python (pytest, see
// tests/test_*.py) against Python scraper/sync code, and index.html has
// no test coverage of its own at all. This is a plain Node script with a
// hand-rolled mock of the one bit of supabase-js's chainable query builder
// this code actually uses (.select/.order/.gte/.gt/.lt/.limit + an
// awaitable {data, error} result) - no dependencies, no npm install
// needed, matches this repo's own existing pattern of small standalone
// diagnostic scripts (measure_listings_payload.py, verify_price_history_
// in_supabase.py) rather than inventing a test framework for one file.
//
// It does NOT re-implement fetchAllRows() by hand - it extracts the real,
// unmodified function source straight out of index.html's inline <script>
// (same "test the actual shipped code" principle as this project's other
// Node vm harnesses referenced in docs/backlog.md item 6, none of which
// were themselves committed to the repo) and runs it inside a vm context,
// so a regression in the real file is what this test would actually catch.
//
// Two things are verified, both with real numbers printed, not asserted
// blind:
//   1. Correctness: a synthetic ~6,000-row mock table (with real-shaped
//      "m_"+sha256-hex ids, exactly like merged_id_for() in
//      sync_to_supabase.py produces) is fetched through the real
//      fetchAllRows() and the result is checked for exactly the right
//      count, no duplicate ids, no missing ids, and the same id-ascending
//      order a sequential fetch would have produced. A missing-select-
//      column scenario (stripMissingSelectColumn()'s own job) is exercised
//      too, under real concurrency, to confirm that retry path still works
//      when several shards can hit it at once.
//   2. Speed: the same real fetchAllRows() and a hardcoded copy of the
//      OLD single-cursor sequential algorithm (labelled clearly below,
//      kept only for this comparison) are run against equivalent mock
//      datasets with a fixed simulated per-request latency, and the real
//      wall-clock times are printed and compared.

'use strict';

const vm = require('vm');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const INDEX_HTML_PATH = path.join(__dirname, '..', 'index.html');

// --- Extract the real, unmodified source from index.html -------------------

function extractRealSource() {
  const html = fs.readFileSync(INDEX_HTML_PATH, 'utf8');
  const startMarker = 'const _MISSING_SELECT_COLUMN_RE';
  const endMarker = 'function computeUnverified(l) {';
  const start = html.indexOf(startMarker);
  const end = html.indexOf(endMarker);
  if (start === -1 || end === -1 || end <= start) {
    throw new Error(
      'Could not locate fetchAllRows()/stripMissingSelectColumn()/' +
      'hexIdPartitionBoundaries() source in index.html - markers moved? ' +
      `(start=${start}, end=${end})`
    );
  }
  return html.slice(start, end);
}

// --- Mock "supabase-js on merged_listings" ----------------------------------
//
// Simulates just enough of the real chainable query builder for this code
// path: .select(cols).order('id')[.gte/.gt/.lt('id', v)].limit(n), awaited
// to {data, error}. Backed by an in-memory, id-sorted array. `latencyMs`
// simulates real network + query time per request; `columns` is the set of
// columns the mock table actually "has" (anything else in a select list
// triggers the same 42703-shaped error real Postgres/PostgREST returns, to
// exercise stripMissingSelectColumn() for real).
function bisectLeft(arr, id) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid].id < id) lo = mid + 1; else hi = mid;
  }
  return lo;
}
function bisectRight(arr, id) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (arr[mid].id <= id) lo = mid + 1; else hi = mid;
  }
  return lo;
}

function makeMockSupabase(rows, { latencyMs = 0, tableColumns = null, batchCap = 1000 } = {}) {
  const sorted = rows.slice().sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  let requestCount = 0;
  let inFlight = 0;
  let maxInFlight = 0;

  function from(table) {
    const state = { table, cols: null, filters: [], lim: null };
    const builder = {
      select(cols) { state.cols = cols; return builder; },
      order() { return builder; }, // only ever ordered by id in this code path
      gte(col, val) { state.filters.push(['gte', val]); return builder; },
      gt(col, val) { state.filters.push(['gt', val]); return builder; },
      lt(col, val) { state.filters.push(['lt', val]); return builder; },
      limit(n) { state.lim = n; return builder; },
      then(resolve) {
        requestCount++;
        inFlight++;
        maxInFlight = Math.max(maxInFlight, inFlight);
        const run = async () => {
          if (latencyMs > 0) await new Promise((r) => setTimeout(r, latencyMs));
          try {
            if (tableColumns) {
              const requested = state.cols.split(',');
              const missing = requested.find((c) => !tableColumns.includes(c));
              if (missing) {
                resolve({ data: null, error: { message: `column ${table}.${missing} does not exist` } });
                return;
              }
            }
            // Binary-search the [lo, hi) index range instead of a linear
            // .filter() scan - real Postgres does this in O(log n) via its
            // btree index on `id`, and a naive O(n) scan here would let
            // this mock's own CPU cost (not the simulated network latency)
            // dominate the speed comparison below once many shards are
            // resolving "at once" on Node's single thread.
            let lo = 0, hi = sorted.length;
            for (const [op, val] of state.filters) {
              if (op === 'gte') lo = Math.max(lo, bisectLeft(sorted, val));
              else if (op === 'gt') lo = Math.max(lo, bisectRight(sorted, val));
              else if (op === 'lt') hi = Math.min(hi, bisectLeft(sorted, val));
            }
            const limit = Math.min(state.lim || (hi - lo), batchCap, hi - lo);
            const page = sorted.slice(lo, lo + limit).map((r) => {
              const projected = {};
              for (const c of state.cols.split(',')) projected[c] = r[c];
              return projected;
            });
            resolve({ data: page, error: null });
          } finally {
            inFlight--;
          }
        };
        run();
      },
    };
    return builder;
  }

  return {
    from,
    stats: () => ({ requestCount, maxInFlight }),
  };
}

function makeRealShapedId(n) {
  // Mirrors merged_id_for() in sync_to_supabase.py exactly: "m_" + first 16
  // hex chars of a sha256 digest - using a real digest (not a hand-picked
  // fake) so the partitioning-by-hex-range logic is tested against genuinely
  // uniformly-distributed ids, the same property the real fix relies on.
  const digest = crypto.createHash('sha256').update(`fixture-member-${n}`).digest('hex');
  return 'm_' + digest.slice(0, 16);
}

function buildFixtureRows(n, extraCols = {}) {
  const rows = [];
  const seen = new Set();
  let i = 0;
  while (rows.length < n) {
    const id = makeRealShapedId(i++);
    if (seen.has(id)) continue; // sha256 collision practically impossible, guard anyway
    seen.add(id);
    rows.push({ id, portal: 'imot.bg', price_eur: 100000 + rows.length, ...extraCols });
  }
  return rows;
}

// --- vm harness: run the REAL extracted source, call fetchAllRows() --------

async function runRealFetchAllRows(source, sb, table, columns) {
  return new Promise((resolve, reject) => {
    const sandbox = {
      console,
      setTimeout,
      sb,
      __done: (err, result) => (err ? reject(err) : resolve(result)),
    };
    vm.createContext(sandbox);
    const driver = `
      ${source}
      fetchAllRows(${JSON.stringify(table)}, ${JSON.stringify(columns)})
        .then((r) => __done(null, r))
        .catch((e) => __done(e && e.message ? e.message : String(e)));
    `;
    vm.runInContext(driver, sandbox, { filename: 'index.html (extracted)' });
  });
}

// Calls the real, unmodified hexIdPartitionBoundaries() (same extracted
// source as fetchAllRows() above) so a boundary-exact fixture row below is
// built from the shard math actually shipped, not a hand-guessed value that
// could silently drift out of sync with it.
function runRealHexIdPartitionBoundaries(source, count) {
  return new Promise((resolve, reject) => {
    const sandbox = { __done: (err, result) => (err ? reject(err) : resolve(result)) };
    vm.createContext(sandbox);
    const driver = `
      ${source}
      __done(null, hexIdPartitionBoundaries(${JSON.stringify(count)}));
    `;
    try {
      vm.runInContext(driver, sandbox, { filename: 'index.html (extracted)' });
    } catch (e) {
      reject(e);
    }
  });
}

// --- OLD algorithm, kept ONLY for this benchmark comparison -----------------
// Hand-copied from index.html as it stood before backlog item 71 (single
// keyset cursor, fully sequential) - not the code under test, just the
// "before" baseline so the speedup claim below is a real measurement
// against an equivalent implementation, not a guess.
async function oldSequentialFetchAllRows(sb, table, columns) {
  const batchSize = 1000;
  let select = columns || '*';
  async function fetchBatch(cursor) {
    let query = sb.from(table).select(select).order('id').limit(batchSize);
    if (cursor !== null) query = query.gt('id', cursor);
    const { data, error } = await query;
    if (error) throw new Error(error.message);
    return data;
  }
  let all = [];
  let cursor = null;
  let done = false;
  while (!done) {
    const data = await fetchBatch(cursor);
    all = all.concat(data);
    if (data.length < batchSize) done = true;
    else cursor = data[data.length - 1].id;
  }
  return all;
}

function assertEqual(actual, expected, msg) {
  if (actual !== expected) throw new Error(`FAIL: ${msg} - expected ${expected}, got ${actual}`);
}

function assertTrue(cond, msg) {
  if (!cond) throw new Error(`FAIL: ${msg}`);
}

async function main() {
  const source = extractRealSource();
  console.log('=== fetchAllRows() bounded-concurrency check (backlog item 71) ===\n');

  // --- Test 1: correctness (count, no dupes, no gaps, stable order) -------
  {
    const N = 6173; // deliberately not a round multiple of batchSize/shard count
    const fixture = buildFixtureRows(N);
    const columns = 'id,portal,price_eur';
    const sb = makeMockSupabase(fixture, { latencyMs: 1, tableColumns: ['id', 'portal', 'price_eur'] });

    const result = await runRealFetchAllRows(source, sb, 'merged_listings', columns);

    assertEqual(result.length, N, 'row count');
    const ids = result.map((r) => r.id);
    assertEqual(new Set(ids).size, N, 'no duplicate ids');
    const expectedIds = fixture.map((r) => r.id).sort();
    const gotSorted = ids.slice().sort();
    assertEqual(JSON.stringify(gotSorted), JSON.stringify(expectedIds), 'exact same id set (no gaps, no extras)');
    // Order: concatenating shards in order must reproduce plain ascending-id
    // order, identical to what the old single-cursor fetch produced.
    const expectedOrder = fixture.map((r) => r.id).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    assertEqual(JSON.stringify(ids), JSON.stringify(expectedOrder), 'id-ascending order preserved exactly');

    const { requestCount, maxInFlight } = sb.stats();
    assertTrue(maxInFlight <= 10, `bounded concurrency respected (max in-flight ${maxInFlight}, expected <= 10)`);
    console.log(`[correctness] ${N} rows, ${requestCount} total requests, max ${maxInFlight} concurrent in-flight - PASS`);
  }

  // --- Test 2: missing-column strip-and-retry survives concurrency --------
  {
    const N = 2500;
    const fixture = buildFixtureRows(N);
    // 'ghost_col' doesn't exist on the mock table - every shard's very first
    // request will hit it concurrently, exercising the exact race this
    // fix's own comment describes (one shard fixes `select`, the others
    // fall through to the ordinary transient-retry path and succeed next
    // attempt), not just the single-caller case the pre-existing code only
    // ever had to handle.
    const columns = 'id,portal,price_eur,ghost_col';
    const sb = makeMockSupabase(fixture, { latencyMs: 1, tableColumns: ['id', 'portal', 'price_eur'] });

    const result = await runRealFetchAllRows(source, sb, 'merged_listings', columns);
    assertEqual(result.length, N, 'row count after missing-column strip');
    assertEqual(new Set(result.map((r) => r.id)).size, N, 'no duplicate ids after missing-column strip');
    console.log(`[missing-column race] ${N} rows recovered correctly despite every shard racing the same ` +
      `missing 'ghost_col' - PASS`);
  }

  // --- Test 3: empty table doesn't hang or throw ---------------------------
  {
    const sb = makeMockSupabase([], { latencyMs: 1, tableColumns: ['id'] });
    const result = await runRealFetchAllRows(source, sb, 'merged_listings', 'id');
    assertEqual(result.length, 0, 'empty table returns empty array');
    console.log('[empty table] 0 rows - PASS');
  }

  // --- Test 3b: a row landing exactly ON a real shard boundary is counted
  // exactly once (Missy's review of the first version of this test found a
  // real coverage gap: a random sha256-derived id essentially never lands
  // exactly on a computed boundary - 1-in-2^64 odds - so Test 1's own
  // random fixture could never actually exercise the >=/< split at
  // fetchPartition()'s shard edges, meaning a real off-by-one there
  // (e.g. `.gt` instead of `.gte` on a shard's lower bound) would pass
  // Test 1 silently while still dropping real rows in production whenever
  // one happened to hash onto a boundary. This test builds a fixture with
  // a row deliberately pinned to a real boundary value (computed from the
  // actual shipped hexIdPartitionBoundaries(), not a hand-picked guess) and
  // confirms it's returned exactly once - verified against a deliberately
  // reintroduced `.gt`-not-`.gte` bug to confirm this test would actually
  // fail if that regression came back (see this file's own git history/PR
  // discussion for that verification - not re-run automatically here since
  // it requires mutating the extracted source, done once by hand during
  // review, not as part of every test run).
  {
    const boundaries = await runRealHexIdPartitionBoundaries(source, 10);
    assertEqual(boundaries.length, 11, 'hexIdPartitionBoundaries(10) returns 11 edges');
    const pinnedId = boundaries[5]; // an interior boundary, real non-null edge
    assertTrue(typeof pinnedId === 'string' && pinnedId.startsWith('m_'), 'pinned boundary id looks real');

    const N = 3000;
    const fixture = buildFixtureRows(N).filter((r) => r.id !== pinnedId);
    fixture.push({ id: pinnedId, portal: 'imot.bg', price_eur: 999999 });
    const columns = 'id,portal,price_eur';
    const sb = makeMockSupabase(fixture, { latencyMs: 1, tableColumns: ['id', 'portal', 'price_eur'] });

    const result = await runRealFetchAllRows(source, sb, 'merged_listings', columns);
    const matches = result.filter((r) => r.id === pinnedId);
    assertEqual(result.length, fixture.length, 'row count including the boundary-pinned row');
    assertEqual(matches.length, 1, `row exactly on shard boundary ${pinnedId} returned exactly once (got ${matches.length})`);
    console.log(`[boundary-exact] row pinned to real shard boundary ${pinnedId} counted exactly once - PASS`);
  }

  // --- Test 4: real measured speedup under simulated realistic latency ----
  {
    const N = 40000; // 40 sequential pages at batchSize=1000
    const LATENCY_MS = 60; // a stand-in for real Supabase REST + network round-trip time
    const fixture = buildFixtureRows(N);
    const columns = 'id,portal,price_eur';

    const sbOld = makeMockSupabase(fixture, { latencyMs: LATENCY_MS, tableColumns: ['id', 'portal', 'price_eur'] });
    const t0 = Date.now();
    const oldResult = await oldSequentialFetchAllRows(sbOld, 'merged_listings', columns);
    const oldMs = Date.now() - t0;

    const sbNew = makeMockSupabase(fixture, { latencyMs: LATENCY_MS, tableColumns: ['id', 'portal', 'price_eur'] });
    const t1 = Date.now();
    const newResult = await runRealFetchAllRows(source, sbNew, 'merged_listings', columns);
    const newMs = Date.now() - t1;

    assertEqual(oldResult.length, N, 'old baseline row count sanity check');
    assertEqual(newResult.length, N, 'new implementation row count sanity check');

    const oldStats = sbOld.stats();
    const newStats = sbNew.stats();
    const speedup = oldMs / newMs;

    console.log(`\n[speed] ${N} rows, ${LATENCY_MS}ms simulated latency/request:`);
    console.log(`  old sequential : ${oldMs}ms wall clock, ${oldStats.requestCount} requests, ` +
      `max ${oldStats.maxInFlight} concurrent in-flight`);
    console.log(`  new concurrent : ${newMs}ms wall clock, ${newStats.requestCount} requests, ` +
      `max ${newStats.maxInFlight} concurrent in-flight`);
    console.log(`  measured speedup: ${speedup.toFixed(2)}x`);

    assertTrue(newStats.maxInFlight <= 10, `new implementation stayed within the 10-shard concurrency bound (got ${newStats.maxInFlight})`);
    // Real round-trip count is unchanged (still ~rows/1000 total requests) -
    // only wall clock should improve, matching the fix's own stated goal.
    assertTrue(Math.abs(oldStats.requestCount - newStats.requestCount) <= 10,
      `total request count roughly unchanged by concurrency alone (old ${oldStats.requestCount}, new ${newStats.requestCount})`);
    assertTrue(speedup >= 5, `expected a meaningful (>=5x) real measured speedup, got ${speedup.toFixed(2)}x`);
    console.log('  PASS (meaningful real measured speedup, same total request count, bounded concurrency)');
  }

  console.log('\n=== all checks passed ===');
}

main().catch((e) => {
  console.error('\nTEST FAILED:', e && e.stack ? e.stack : e);
  process.exit(1);
});
