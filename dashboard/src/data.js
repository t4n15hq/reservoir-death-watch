// Vite serves files in dashboard/public/ at the site root, so the on-disk
// path `dashboard/public/data/reservoirs.json` resolves to the URL
// `/data/reservoirs.json`. We use a relative form so the same code also
// works when the built bundle is hosted at a subpath (e.g. GH Pages).
const DATA_PATH = 'data/reservoirs.json';

export function readBacktestParam() {
  const url = new URL(window.location.href);
  const value = url.searchParams.get('backtest');
  if (!value) return null;
  // Sanitize — the value gets interpolated into a fetch path.
  if (!/^[a-z0-9_]+$/i.test(value)) return null;
  return value;
}

export async function loadSnapshot(path = DATA_PATH) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} loading ${path}`);
  }
  return response.json();
}

export async function loadStateAggregates() {
  const path = 'data/state_aggregates.json';
  const response = await fetch(path);
  if (!response.ok) return null; // optional file; ok to miss
  return response.json();
}

export async function loadBacktestSnapshot(caseId) {
  const path = `data/backtest_${caseId}.json`;
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`No backtest snapshot for "${caseId}" (HTTP ${response.status})`);
  }
  return response.json();
}

export async function loadReservoirHistory(reservoirId) {
  const path = `data/reservoirs/${reservoirId}.csv`;
  // One retry — Vite HMR can briefly drop connections during file edits.
  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(path, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status} for ${path}`);
      return parseCsv(await response.text());
    } catch (err) {
      lastError = err;
      if (attempt === 0) {
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
    }
  }
  throw lastError ?? new Error(`Unknown error loading ${path}`);
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  if (!lines.length) return [];
  const header = lines.shift().split(',');
  return lines.map((line) => {
    const cells = splitCsvLine(line);
    const row = {};
    header.forEach((column, i) => {
      const value = cells[i];
      row[column] = value === '' ? null : value;
    });
    if (row.date) row.date = new Date(`${row.date}T00:00:00Z`);
    if (row.area_km2 != null) row.area_km2 = Number(row.area_km2);
    if (row.estimated_storage_bcm != null) {
      row.estimated_storage_bcm = Number(row.estimated_storage_bcm);
    }
    if (row.percent_full != null) row.percent_full = Number(row.percent_full);
    return row;
  });
}

function splitCsvLine(line) {
  const out = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      out.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  out.push(current);
  return out;
}

export function daysSince(iso) {
  if (!iso) return null;
  const then = new Date(`${iso}T00:00:00Z`).getTime();
  const now = Date.now();
  return Math.floor((now - then) / (1000 * 60 * 60 * 24));
}

// `1900-01-01` is the sentinel the pipeline writes for reservoirs in the
// master list that don't have an observation yet. Treat it as "never observed"
// rather than "extremely stale" so the UI can say so honestly.
export function awaitingFirstObservation(reservoir) {
  const flags = reservoir?.flags ?? [];
  if (flags.includes('awaiting_first_observation')) return true;
  const asOf = reservoir?.current?.as_of;
  return asOf === '1900-01-01';
}

export function tierColor(tier) {
  switch (tier) {
    case 'critical':
      return '#c0392b';
    case 'warning':
      return '#e67e22';
    case 'watch':
      return '#f1c40f';
    case 'stable':
      return '#27ae60';
    default:
      return '#7f8c8d';
  }
}

export function isStale(reservoir, thresholdDays = 14) {
  const asOf = reservoir?.current?.as_of;
  const age = daysSince(asOf);
  if (age == null) return true;
  return age > thresholdDays;
}
