import {
  loadBacktestSnapshot,
  loadSnapshot,
  loadStateAggregates,
  readBacktestParam,
} from './data.js';
import { initMap, plotReservoirs, focusReservoir, setActivePin } from './map.js';
import { renderDetail, renderEmpty } from './detail.js';
import { renderHero } from './hero.js';
import { renderReservoirList } from './list.js';
import { renderStateBand } from './rollup.js';

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
  renderHero(snapshot, backtestCase);

  const stateAggregates = backtestCase ? null : await loadStateAggregates().catch(() => null);
  renderStateBand(document.getElementById('states-band'), snapshot, stateAggregates);

  const map = await initMap('map');

  const selectByReservoir = (reservoir, { fly = true } = {}) => {
    renderDetail(document.getElementById('detail-pane'), reservoir);
    setActivePin(reservoir.id);
    setActiveRow(reservoir.id);
    if (fly) focusReservoir(map, reservoir);
  };

  plotReservoirs(map, snapshot, {
    onSelect: (r) => selectByReservoir(r),
  });

  renderReservoirList(document.getElementById('reservoir-list'), snapshot, {
    onSelect: (r) => selectByReservoir(r),
  });

  const initial = pickDefaultReservoir(snapshot);
  if (initial) {
    // Render detail without flying — let the user see the full India view first.
    selectByReservoir(initial, { fly: false });
  } else {
    renderEmpty(document.getElementById('detail-pane'));
  }
}

function setActiveRow(reservoirId) {
  document.querySelectorAll('.reservoir-row').forEach((el) => {
    el.classList.toggle('is-active', el.dataset.id === reservoirId);
  });
}

function renderBacktestBanner(snapshot, caseId) {
  const banner = document.createElement('div');
  banner.className = 'backtest-banner';
  const generated = snapshot.generated_at
    ? new Date(snapshot.generated_at).toISOString().slice(0, 10)
    : 'unknown';
  banner.innerHTML = `
    <strong>Backtest mode</strong> — showing model as of <code>${generated}</code>
    for case <code>${caseId}</code>.
    <a href="${window.location.pathname}">Exit backtest</a>
  `;
  document.body.insertBefore(banner, document.body.firstChild);
}

function pickDefaultReservoir(snapshot) {
  if (!snapshot.reservoirs?.length) return null;
  const tierOrder = { critical: 0, warning: 1, watch: 2, stable: 3 };
  const observed = snapshot.reservoirs.filter(
    (r) => !(r.flags ?? []).includes('awaiting_first_observation'),
  );
  const pool = observed.length ? observed : snapshot.reservoirs;
  return [...pool].sort((a, b) => {
    const dt = (tierOrder[a.tier] ?? 9) - (tierOrder[b.tier] ?? 9);
    if (dt !== 0) return dt;
    const da = a.projection?.neutral_monsoon?.days_to_dead_storage ?? 99999;
    const db = b.projection?.neutral_monsoon?.days_to_dead_storage ?? 99999;
    return da - db;
  })[0];
}

boot();
