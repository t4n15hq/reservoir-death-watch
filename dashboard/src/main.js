import {
  loadBacktestSnapshot,
  loadDataProvenance,
  loadSnapshot,
  loadStateAggregates,
  readBacktestParam,
} from './data.js';
import { initMap, plotReservoirs, focusReservoir, fitReservoirs, setActivePin } from './map.js';
import { renderDetail, renderEmpty } from './detail.js';
import { renderHero } from './hero.js';
import { renderReservoirList } from './list.js';
import { renderStateBand } from './rollup.js';
import { renderDataQuality } from './quality.js';

async function boot() {
  const backtestCase = readBacktestParam();
  if (backtestCase) document.body.classList.add('is-backtest');
  let snapshot;
  try {
    snapshot = backtestCase ? await loadBacktestSnapshot(backtestCase) : await loadSnapshot();
  } catch (err) {
    document.getElementById('generated-meta').textContent = `Failed to load data: ${err.message}`;
    return;
  }

  if (backtestCase) renderBacktestBanner(snapshot, backtestCase);
  renderHero(snapshot, backtestCase);
  if (backtestCase && snapshot.backtest) {
    // The backtest payload carries the case's pass/fail verdict — surface
    // it in the hero so reviewers don't have to dig through flags.
    renderBacktestVerdict(snapshot.backtest);
  }

  const [stateAggregates, provenance] = await Promise.all([
    backtestCase ? Promise.resolve(null) : loadStateAggregates().catch(() => null),
    backtestCase ? Promise.resolve(null) : loadDataProvenance().catch(() => null),
  ]);
  renderStateBand(document.getElementById('states-band'), snapshot, stateAggregates);
  const filters = {
    scope: 'all',
    state: 'all',
    query: '',
  };
  renderDataQuality(
    document.getElementById('quality-section'),
    provenance,
    filterReservoirs(snapshot.reservoirs ?? [], filters),
    filters,
  );

  let map = null;
  let mapReady = false;
  let selectedReservoir = null;
  let hasRenderedMap = false;

  const selectByReservoir = (reservoir, { fly = true } = {}) => {
    selectedReservoir = reservoir;
    renderDetail(document.getElementById('detail-pane'), reservoir);
    setActivePin(reservoir.id);
    setActiveRow(reservoir.id);
    if (fly && mapReady && map) focusReservoir(map, reservoir);
  };

  setupFilters(snapshot, filters, () => renderFilteredReservoirs());

  function renderFilteredReservoirs() {
    const filtered = filterReservoirs(snapshot.reservoirs ?? [], filters);
    updateListCount(filtered, snapshot.reservoirs ?? [], filters);
    renderDataQuality(document.getElementById('quality-section'), provenance, filtered, filters);

    if (mapReady && map) {
      plotReservoirs(map, filtered, {
        onSelect: (r) => selectByReservoir(r),
      });
      fitReservoirs(map, filtered, { animate: hasRenderedMap });
      hasRenderedMap = true;
    }

    renderReservoirList(document.getElementById('reservoir-list'), filtered, {
      onSelect: (r) => selectByReservoir(r),
    });

    if (selectedReservoir && filtered.some((r) => r.id === selectedReservoir.id)) {
      setActivePin(selectedReservoir.id);
      setActiveRow(selectedReservoir.id);
      return;
    }

    const initial = pickDefaultReservoir({ reservoirs: filtered });
    if (initial) {
      // Render detail without flying — let the user see the current map extent first.
      selectByReservoir(initial, { fly: false });
    } else {
      selectedReservoir = null;
      renderEmpty(document.getElementById('detail-pane'));
    }
  }

  renderFilteredReservoirs();
  initMap('map')
    .then((readyMap) => {
      map = readyMap;
      mapReady = true;
      renderFilteredReservoirs();
    })
    .catch((err) => {
      console.warn(`Map failed to initialize: ${err.message}`);
    });
}

function setActiveRow(reservoirId) {
  document.querySelectorAll('.reservoir-row').forEach((el) => {
    el.classList.toggle('is-active', el.dataset.id === reservoirId);
  });
}

function setupFilters(snapshot, filters, onChange) {
  const stateSelect = document.getElementById('state-filter');
  const search = document.getElementById('reservoir-search');
  const scopeButtons = document.querySelectorAll('.scope-toggle__button');

  if (stateSelect) {
    const states = [...new Set((snapshot.reservoirs ?? []).map((r) => r.state).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b));
    stateSelect.innerHTML = [
      '<option value="all">All states</option>',
      ...states.map((state) => `<option value="${escapeAttr(state)}">${state}</option>`),
    ].join('');
    stateSelect.addEventListener('change', () => {
      filters.state = stateSelect.value;
      onChange();
    });
  }

  if (search) {
    search.addEventListener('input', () => {
      filters.query = search.value.trim().toLowerCase();
      onChange();
    });
  }

  scopeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      filters.scope = button.dataset.scope ?? 'core_city';
      scopeButtons.forEach((b) => b.classList.toggle('is-active', b === button));
      onChange();
    });
  });
}

function filterReservoirs(reservoirs, filters) {
  const query = filters.query;
  return reservoirs.filter((reservoir) => {
    if (filters.scope !== 'all' && (reservoir.scope ?? 'core_city') !== filters.scope) {
      return false;
    }
    if (filters.state !== 'all' && reservoir.state !== filters.state) {
      return false;
    }
    if (!query) return true;
    const haystack = [
      reservoir.name,
      reservoir.city_served,
      reservoir.state,
      reservoir.river,
      reservoir.id,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
}

function updateListCount(filtered, reservoirs, filters) {
  const el = document.getElementById('list-count');
  if (!el) return;
  const scopeText = filters.scope === 'all'
    ? 'all scopes'
    : filters.scope === 'expanded_cwc'
      ? 'expanded CWC'
      : 'core city';
  const observed = filtered.filter((r) => !(r.flags ?? []).includes('awaiting_first_observation')).length;
  el.textContent = `${filtered.length} of ${reservoirs.length} reservoirs · ${observed} observed · ${scopeText}`;
}

function escapeAttr(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function renderBacktestBanner(snapshot, caseId) {
  const banner = document.createElement('div');
  banner.className = 'backtest-banner';
  const meta = snapshot.backtest ?? {};
  const asOf = meta.as_of ?? (snapshot.generated_at?.slice?.(0, 10) ?? 'unknown');
  banner.innerHTML = `
    <strong>Backtest mode</strong> — model as of <code>${asOf}</code>
    for case <code>${caseId}</code>.
    <a href="${window.location.pathname}">Exit backtest</a>
  `;
  document.body.insertBefore(banner, document.body.firstChild);
}

function renderBacktestVerdict(bt) {
  const el = document.getElementById('hero-deck');
  if (!el) return;
  const expected = (bt.expected_tiers ?? []).join(' or ');
  const verdict = bt.passed
    ? `<span style="color:var(--stable);font-weight:600">PASS</span>`
    : `<span style="color:var(--critical);font-weight:600">FAIL</span>`;
  el.innerHTML = `
    Historical backtest of <strong>${bt.reservoir_id}</strong> at <strong>${bt.as_of}</strong>.
    Expected tier: <strong>${expected || 'unknown'}</strong>. Model said:
    <strong>${bt.actual_tier}</strong>. ${verdict}
  `;
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
