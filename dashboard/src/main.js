import {
  loadBacktestSnapshot,
  loadSnapshot,
  loadStateAggregates,
  readBacktestParam,
} from './data.js';
import { initMap, plotReservoirs, focusReservoir } from './map.js';
import { renderDetail, renderEmpty } from './detail.js';
import { renderRollup } from './rollup.js';

async function boot() {
  const backtestCase = readBacktestParam();
  let snapshot;
  try {
    snapshot = backtestCase ? await loadBacktestSnapshot(backtestCase) : await loadSnapshot();
  } catch (err) {
    document.getElementById('generated-meta').textContent = `Failed to load data: ${err.message}`;
    return;
  }

  if (backtestCase) renderBacktestBanner(snapshot, backtestCase);
  document.getElementById('generated-meta').innerHTML = formatGenerated(snapshot);

  // State aggregates are optional — if they're missing we just hide the strip.
  const stateAggregates = backtestCase ? null : await loadStateAggregates().catch(() => null);
  renderRollup(document.getElementById('national-rollup'), snapshot, stateAggregates);

  const map = await initMap('map');
  plotReservoirs(map, snapshot, {
    onSelect: (reservoir) => {
      renderDetail(document.getElementById('detail-pane'), reservoir);
      focusReservoir(map, reservoir);
    },
  });

  const initial = pickDefaultReservoir(snapshot);
  if (initial) {
    // Render the default detail panel without flying the map — that would zoom in
    // before the user has even seen the full India view.
    renderDetail(document.getElementById('detail-pane'), initial);
  } else {
    renderEmpty(document.getElementById('detail-pane'));
  }
}

function formatGenerated(snapshot) {
  const generated = snapshot.generated_at ? new Date(snapshot.generated_at) : null;
  const generatedLabel = generated
    ? generated.toISOString().slice(0, 10)
    : 'unknown';
  const enso = snapshot.enso?.state ?? 'unavailable';
  return `
    <span><strong>Generated</strong> ${generatedLabel}</span>
    <span><strong>ENSO</strong> ${enso.replaceAll('_', ' ')}</span>
    <span><strong>Model</strong> ${snapshot.model_version ?? 'unknown'}</span>
  `;
}

function renderBacktestBanner(snapshot, caseId) {
  const banner = document.createElement('div');
  banner.className = 'backtest-banner';
  const generated = snapshot.generated_at ? new Date(snapshot.generated_at).toISOString().slice(0, 10) : 'unknown';
  banner.innerHTML = `
    <strong>Backtest mode:</strong> showing model as of <code>${generated}</code> for case
    <code>${caseId}</code>. <a href="${window.location.pathname}">Exit backtest</a>
  `;
  document.body.insertBefore(banner, document.body.firstChild);
}

function pickDefaultReservoir(snapshot) {
  if (!snapshot.reservoirs?.length) return null;
  const tierOrder = { critical: 0, warning: 1, watch: 2, stable: 3 };
  // Skip reservoirs we haven't observed yet — they have no real story to show.
  const observed = snapshot.reservoirs.filter(
    (r) => !(r.flags ?? []).includes('awaiting_first_observation'),
  );
  const pool = observed.length ? observed : snapshot.reservoirs;
  return [...pool].sort((a, b) => (tierOrder[a.tier] ?? 9) - (tierOrder[b.tier] ?? 9))[0];
}

boot();
