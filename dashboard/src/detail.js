import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import {
  awaitingFirstObservation,
  daysSince,
  isStale,
  loadReservoirHistory,
  tierColor,
} from './data.js';

Chart.register(...registerables);

let activeChart = null;

export function renderEmpty(container) {
  container.innerHTML = '<div class="empty">Select a reservoir to see its detail.</div>';
}

export async function renderDetail(container, reservoir) {
  const current = reservoir.current ?? {};
  const projection = reservoir.projection ?? {};
  const neutral = projection.neutral_monsoon ?? {};
  const elNino = projection.el_nino_monsoon ?? {};
  const pending = awaitingFirstObservation(reservoir);
  const stale = !pending && isStale(reservoir);
  const ageDays = pending ? null : daysSince(current.as_of);
  const flags = reservoir.flags ?? [];

  container.innerHTML = `
    <div class="detail">
      <div class="detail__header">
        <div>
          <h2>${reservoir.name}</h2>
          <p class="meta">${reservoir.river} · ${reservoir.state}${
    reservoir.city_served ? ` · serves ${reservoir.city_served}` : ''
  }</p>
        </div>
        <span class="tier-pill" style="background:${tierColor(reservoir.tier)}">${reservoir.tier}</span>
      </div>

      ${pending ? '<div class="banner banner--pending">Awaiting first satellite observation. AOI not yet digitized for this reservoir. Run <code>scripts/seed_aois.py</code> and the pipeline to populate.</div>' : ''}
      ${stale ? '<div class="banner banner--stale">Stale data: most recent observation is older than 14 days.</div>' : ''}
      ${!pending && flags.includes('current_only_no_history') ? '<div class="banner banner--info">Current observation only — no historical trace or depletion fit yet.</div>' : ''}

      <dl class="kv">
        <dt>As of</dt>
        <dd>${pending ? '<span class="muted">no observation yet</span>' : `${current.as_of ?? '—'} ${ageDays != null ? `<span class="muted">(${ageDays} d)</span>` : ''}`}</dd>

        <dt>Satellite area</dt>
        <dd>${pending ? '<span class="muted">no observation yet</span>' : `${formatArea(current.area_km2)} of ${formatArea(reservoir.full_pool_area_km2)} <span class="muted">(observed)</span>`}</dd>

        <dt>Estimated storage</dt>
        <dd>${pending ? '<span class="muted">no observation yet</span>' : `${formatBcm(current.estimated_storage_bcm)} of ${formatBcm(reservoir.full_pool_capacity_bcm)} BCM <span class="muted">(${storageDerivation(flags)})</span>`}</dd>

        <dt>CWC reported</dt>
        <dd>${
          current.cwc_reported_bcm != null
            ? `${formatBcm(current.cwc_reported_bcm)} BCM as of ${current.cwc_as_of ?? '—'} <span class="muted">(authoritative)</span>`
            : '<span class="muted">no recent CWC reading</span>'
        }</dd>

        <dt>Percent full</dt>
        <dd>${formatPercent(current.percent_full)}</dd>

        <dt>Source</dt>
        <dd>${current.data_source ?? '—'}</dd>
      </dl>

      <h3>Days to dead storage</h3>
      <div class="projection">
        <div class="projection__scenario">
          <div class="projection__label">Neutral monsoon</div>
          <div class="projection__value">${formatDays(neutral.days_to_dead_storage)}</div>
          <div class="projection__hint">${
            neutral.dead_storage_date ? `est. ${neutral.dead_storage_date}` : ''
          }</div>
          <div class="projection__ci">${formatCi(neutral.confidence_interval_days)}</div>
        </div>
        <div class="projection__scenario">
          <div class="projection__label">El Niño monsoon</div>
          <div class="projection__value">${formatDays(elNino.days_to_dead_storage)}</div>
          <div class="projection__hint">${
            elNino.dead_storage_date ? `est. ${elNino.dead_storage_date}` : ''
          }</div>
          <div class="projection__ci">${formatCi(elNino.confidence_interval_days)}</div>
        </div>
      </div>

      <h3>Surface area history</h3>
      <div class="chart-wrap"><canvas id="history-chart"></canvas></div>

      ${flags.length ? `<details class="flags"><summary>${flags.length} flag${flags.length === 1 ? '' : 's'}</summary><ul>${flags.map((f) => `<li><code>${f}</code></li>`).join('')}</ul></details>` : ''}
    </div>
  `;

  if (pending) {
    const wrap = container.querySelector('.chart-wrap');
    if (wrap) wrap.innerHTML = '<p class="muted" style="padding:1rem 0">No history yet — pipeline has not run for this reservoir.</p>';
  } else {
    try {
      const history = await loadReservoirHistory(reservoir.id);
      drawHistoryChart(history);
    } catch (err) {
      const wrap = container.querySelector('.chart-wrap');
      if (wrap) wrap.textContent = `History unavailable: ${err.message}`;
    }
  }
}

function drawHistoryChart(history) {
  const canvas = document.getElementById('history-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }
  const points = history
    .filter((row) => row.area_km2 != null && row.area_km2 > 0 && row.date)
    .map((row) => ({ x: row.date, y: row.area_km2, source: row.data_source }));

  const jrc = points.filter((p) => p.source === 'jrc');
  const s2 = points.filter((p) => p.source === 'sentinel_2');
  const s1 = points.filter((p) => p.source === 'sentinel_1');

  activeChart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [
        { label: 'JRC monthly', data: jrc, borderColor: '#2980b9', pointRadius: 0, borderWidth: 1 },
        { label: 'Sentinel-2', data: s2, borderColor: '#16a085', pointRadius: 2, borderWidth: 1 },
        { label: 'Sentinel-1', data: s1, borderColor: '#8e44ad', pointRadius: 2, borderWidth: 1 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      scales: {
        x: { type: 'time', time: { unit: 'year' }, ticks: { color: '#555' } },
        y: { title: { display: true, text: 'Area (km²)' }, ticks: { color: '#555' } },
      },
      plugins: {
        legend: { labels: { color: '#333' } },
      },
    },
  });
}

function storageDerivation(flags) {
  if (flags.includes('cwc_calibrated_single_point')) return 'derived from CWC-calibrated curve';
  if (flags.includes('volume_area_ratio_proxy')) return 'derived via area-ratio proxy';
  return 'derived';
}

function formatArea(value) {
  if (value == null) return '—';
  return `${value.toFixed(1)} km²`;
}

function formatBcm(value) {
  if (value == null) return '—';
  return value.toFixed(3);
}

function formatPercent(value) {
  if (value == null) return '—';
  return `${value.toFixed(1)}%`;
}

function formatDays(value) {
  if (value == null) return '—';
  return `${value} d`;
}

function formatCi(ci) {
  if (!ci || ci.length !== 2) return '';
  return `±[${ci[0]} – ${ci[1]}] d`;
}
