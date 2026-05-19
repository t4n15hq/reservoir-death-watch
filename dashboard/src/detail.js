import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import annotationPlugin from 'chartjs-plugin-annotation';
import {
  awaitingFirstObservation,
  daysSince,
  isStale,
  loadReservoirHistory,
} from './data.js';

Chart.register(...registerables, annotationPlugin);

let activeChart = null;

export function renderEmpty(container) {
  container.innerHTML = '<div class="empty">Select a reservoir from the list or map.</div>';
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
      <div class="detail__crumb">${reservoir.river} basin · ${reservoir.state}</div>
      <h2 class="detail__title">
        ${reservoir.name}
        <span class="tier-pill tier-pill--${reservoir.tier}">${reservoir.tier}</span>
      </h2>
      <p class="detail__byline">
        ${reservoir.city_served ? `Supplies <strong>${reservoir.city_served}</strong>` : 'Drinking water reservoir'}${
          reservoir.population_served
            ? ` · roughly <strong>${formatPop(reservoir.population_served)}</strong> people`
            : ''
        }${
          current.as_of && !pending
            ? ` · last observed <strong>${current.as_of}</strong>${ageDays != null ? ` (${ageDays}d ago)` : ''}`
            : ''
        }.
      </p>

      ${pending ? '<div class="banner banner--pending">Awaiting first satellite observation. AOI not yet digitized for this reservoir.</div>' : ''}
      ${stale ? '<div class="banner banner--stale">Stale data — most recent observation is older than 14 days.</div>' : ''}
      ${!pending && flags.includes('current_only_no_history') ? '<div class="banner banner--info">Current observation only — no historical trace or depletion fit yet.</div>' : ''}

      ${pending ? '' : renderHeadlineProjection(neutral, elNino)}

      <h3>Snapshot</h3>
      <dl class="kv">
        <dt>Satellite area</dt>
        <dd>${pending ? '<span class="muted">no observation yet</span>' : `${formatArea(current.area_km2)} of ${formatArea(reservoir.full_pool_area_km2)} <span class="muted">(observed)</span>`}</dd>

        <dt>Estimated storage</dt>
        <dd>${pending ? '<span class="muted">no observation yet</span>' : `${formatBcm(current.estimated_storage_bcm)} of ${formatBcm(reservoir.full_pool_capacity_bcm)} BCM <span class="muted">(${storageDerivation(flags)})</span>`}</dd>

        <dt>Percent full</dt>
        <dd>${pending ? '—' : formatPct(current.percent_full)}</dd>

        <dt>CWC reference</dt>
        <dd>${
          current.cwc_reported_bcm != null
            ? `${formatBcm(current.cwc_reported_bcm)} BCM <span class="muted">as of ${current.cwc_as_of ?? '—'} (authoritative)</span>`
            : '<span class="muted">no CWC reading for this reservoir yet</span>'
        }</dd>

        <dt>Source</dt>
        <dd>${pending ? '—' : `<code>${current.data_source ?? '—'}</code>`}</dd>
      </dl>

      <h3>Surface area history</h3>
      <div class="chart-wrap"><canvas id="history-chart"></canvas></div>

      ${pending ? '' : `
        <p class="detail__download">
          <a href="data/reservoirs/${reservoir.id}.csv" download>Download full history CSV</a>
          · 15+ years of monthly JRC + recent Sentinel observations,
          area in km², derived storage, source label per row.
        </p>
      `}

      ${flags.length ? `<details class="flags"><summary>Data caveats (${flags.length})</summary><ul>${flags.map((f) => `<li><code>${f}</code></li>`).join('')}</ul></details>` : ''}
    </div>
  `;

  if (pending) {
    const wrap = container.querySelector('.chart-wrap');
    if (wrap) wrap.innerHTML = '<p class="muted" style="padding:1rem 0">No history yet — pipeline has not run for this reservoir.</p>';
  } else {
    try {
      const history = await loadReservoirHistory(reservoir.id);
      drawHistoryChart(history, reservoir);
    } catch (err) {
      const wrap = container.querySelector('.chart-wrap');
      if (wrap) wrap.textContent = `History unavailable: ${err.message}`;
    }
  }
}

function renderHeadlineProjection(neutral, elNino) {
  const neutralDays = neutral?.days_to_dead_storage;
  const elNinoDays = elNino?.days_to_dead_storage;
  const neutralCls = daysClass(neutralDays);
  const elNinoCls = daysClass(elNinoDays);
  return `
    <div class="detail__headline">
      <div class="detail__headline__label">Days to dead storage</div>
      <div class="detail__headline__row">
        <div>
          <div class="detail__headline__scenario">Neutral monsoon</div>
          <div class="detail__headline__days ${neutralCls}">${formatDays(neutralDays)}</div>
          <div class="detail__headline__hint">${formatTarget(neutral)}</div>
        </div>
        <div>
          <div class="detail__headline__scenario">El Niño monsoon</div>
          <div class="detail__headline__days ${elNinoCls}">${formatDays(elNinoDays)}</div>
          <div class="detail__headline__hint">${formatTarget(elNino)}</div>
        </div>
      </div>
    </div>
  `;
}

function daysClass(days) {
  if (days == null) return '';
  if (days < 60) return 'detail__headline__days--critical';
  if (days < 120) return 'detail__headline__days--warning';
  return '';
}

function drawHistoryChart(history, reservoir) {
  const canvas = document.getElementById('history-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }
  const points = history
    .filter((row) => row.area_km2 != null && row.area_km2 > 0 && row.date)
    .map((row) => ({ x: row.date.getTime(), y: row.area_km2, source: row.data_source }));

  const jrc = points.filter((p) => p.source === 'jrc');
  const s2 = points.filter((p) => p.source === 'sentinel_2');
  const s1 = points.filter((p) => p.source === 'sentinel_1');

  const datasets = [];
  if (jrc.length) {
    datasets.push({ label: 'JRC monthly', data: jrc, borderColor: '#3a5a78', pointRadius: 0, borderWidth: 1.2, tension: 0.15 });
  }
  if (s2.length) {
    datasets.push({ label: 'Sentinel-2', data: s2, borderColor: '#2f7a4f', pointRadius: 1.8, borderWidth: 1.2, tension: 0.1 });
  }
  if (s1.length) {
    datasets.push({ label: 'Sentinel-1', data: s1, borderColor: '#8d5d9c', pointRadius: 1.8, borderWidth: 1.2, tension: 0.1 });
  }

  // Reference lines: FRL (full pool area) + dead-storage area
  // Plus a shaded last-90-days region indicating what the depletion fit was computed from.
  const annotations = {};
  if (reservoir.full_pool_area_km2) {
    annotations.frl = {
      type: 'line',
      yMin: reservoir.full_pool_area_km2,
      yMax: reservoir.full_pool_area_km2,
      borderColor: 'rgba(58, 90, 120, 0.35)',
      borderWidth: 1,
      borderDash: [4, 3],
      label: {
        display: true,
        content: 'FRL',
        position: 'end',
        backgroundColor: 'transparent',
        color: '#3a5a78',
        font: { family: "'Inter', sans-serif", size: 10, weight: '500' },
        padding: { top: 0, bottom: 0, left: 4, right: 0 },
        yAdjust: -6,
      },
    };
  }
  // Dead storage area: derived the same way the model does, so the chart
  // reflects what the projection is using.
  const deadCapacity = reservoir.dead_storage_capacity_bcm;
  const fullCapacity = reservoir.full_pool_capacity_bcm;
  const fullArea = reservoir.full_pool_area_km2;
  if (deadCapacity && fullCapacity && fullArea) {
    const deadArea = fullArea * Math.pow(deadCapacity / fullCapacity, 1 / 2.0);
    annotations.dead = {
      type: 'line',
      yMin: deadArea,
      yMax: deadArea,
      borderColor: 'rgba(182, 50, 42, 0.4)',
      borderWidth: 1,
      borderDash: [4, 3],
      label: {
        display: true,
        content: 'dead storage',
        position: 'end',
        backgroundColor: 'transparent',
        color: '#b6322a',
        font: { family: "'Inter', sans-serif", size: 10, weight: '500' },
        padding: { top: 0, bottom: 0, left: 4, right: 0 },
        yAdjust: 8,
      },
    };
  }
  // Shaded region: the 90-day depletion-fit window, ending at the latest observation.
  const latest = points.length ? points[points.length - 1] : null;
  if (reservoir.fit && latest) {
    const winEnd = latest.x;
    const winStart = winEnd - 90 * 24 * 60 * 60 * 1000;
    annotations.fitWindow = {
      type: 'box',
      xMin: winStart,
      xMax: winEnd,
      backgroundColor: 'rgba(196, 122, 29, 0.06)',
      borderWidth: 0,
    };
  }

  activeChart = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      animation: false,
      plugins: {
        annotation: { annotations },
        legend: {
          labels: { color: '#4a4a48', font: { family: "'Inter', sans-serif", size: 11 }, usePointStyle: true, pointStyle: 'line' },
        },
        tooltip: {
          callbacks: {
            title: (items) => new Date(items[0].parsed.x).toISOString().slice(0, 10),
            label: (item) => `${item.dataset.label}: ${item.parsed.y.toFixed(1)} km²`,
          },
        },
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'year' },
          ticks: { color: '#8a8579', font: { family: "'JetBrains Mono', monospace", size: 10 } },
          grid: { color: 'rgba(0,0,0,0.04)' },
        },
        y: {
          title: { display: true, text: 'km²', color: '#8a8579', font: { family: "'Inter', sans-serif", size: 11 } },
          ticks: { color: '#8a8579', font: { family: "'JetBrains Mono', monospace", size: 10 } },
          grid: { color: 'rgba(0,0,0,0.04)' },
        },
      },
    },
  });
}

function storageDerivation(flags) {
  if (flags.includes('cwc_calibrated_single_point')) return 'CWC-calibrated curve';
  if (flags.includes('volume_area_ratio_proxy')) return 'area-ratio proxy';
  return 'derived';
}

function formatPop(n) {
  if (n >= 1e7) return `${(n / 1e7).toFixed(1)} crore`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)} lakh`;
  return n.toLocaleString();
}

function formatArea(value) {
  if (value == null) return '—';
  return `${value.toFixed(1)} km²`;
}

function formatBcm(value) {
  if (value == null) return '—';
  return value.toFixed(3);
}

function formatPct(value) {
  if (value == null) return '—';
  return `${value.toFixed(1)}%`;
}

function formatDays(value) {
  if (value == null) return '—';
  return `${value}<span class="stat__suffix">d</span>`;
}

function formatTarget(projection) {
  if (!projection?.dead_storage_date) return '—';
  const ci = projection.confidence_interval_days;
  if (Array.isArray(ci) && ci.length === 2) {
    return `est. ${projection.dead_storage_date} · ±[${ci[0]}–${ci[1]}] d`;
  }
  return `est. ${projection.dead_storage_date}`;
}
