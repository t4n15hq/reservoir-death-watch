export function renderRollup(container, snapshot, stateAggregates = null) {
  const a = snapshot.national_aggregate ?? {};
  const enso = snapshot.enso?.state ?? 'unavailable';
  const reservoirs = snapshot.reservoirs ?? [];
  const total = reservoirs.length;
  const pending = reservoirs.filter((r) => (r.flags ?? []).includes('awaiting_first_observation')).length;
  const observed = total - pending;

  container.innerHTML = `
    <div class="stat">
      <div class="stat__label">Reservoirs in view</div>
      <div class="stat__value">${observed} <span class="stat__divisor">/ ${total}</span></div>
      <div class="stat__hint">${pending ? `${pending} awaiting first observation` : 'all observed'}</div>
    </div>
    <div class="stat">
      <div class="stat__label">Storage (observed only)</div>
      <div class="stat__value">${formatBcm(a.current_storage_bcm)} / ${formatBcm(a.total_capacity_bcm)} BCM</div>
      <div class="stat__hint">${formatPercent(a.percent_full)} of full across ${observed} reservoirs</div>
    </div>
    <div class="stat">
      <div class="stat__label">Critical / Warning</div>
      <div class="stat__value">${a.reservoirs_critical ?? 0} / ${a.reservoirs_warning ?? 0}</div>
      <div class="stat__hint">Watch ${a.reservoirs_watch ?? 0} · Stable ${a.reservoirs_stable ?? 0}</div>
    </div>
    <div class="stat">
      <div class="stat__label">ENSO state</div>
      <div class="stat__value">${enso.replaceAll('_', ' ')}</div>
      <div class="stat__hint">El Niño suppresses monsoon refill</div>
    </div>
    ${renderStateStrip(stateAggregates)}
  `;
}

function renderStateStrip(stateAggregates) {
  const states = stateAggregates?.states ?? [];
  if (!states.length) return '';
  const rows = states
    .map((s) => {
      const tiers = s.tier_counts ?? {};
      return `
        <li>
          <span class="state-row__name">${s.state}</span>
          <span class="state-row__pct">${formatPercent(s.percent_full)}</span>
          <span class="state-row__tiers">
            <span title="critical" class="tier-dot tier-dot--critical">${tiers.critical ?? 0}</span>
            <span title="warning" class="tier-dot tier-dot--warning">${tiers.warning ?? 0}</span>
            <span title="watch" class="tier-dot tier-dot--watch">${tiers.watch ?? 0}</span>
            <span title="stable" class="tier-dot tier-dot--stable">${tiers.stable ?? 0}</span>
          </span>
        </li>
      `;
    })
    .join('');
  return `
    <div class="state-strip">
      <div class="state-strip__label">State rollup</div>
      <ul>${rows}</ul>
    </div>
  `;
}

function formatBcm(value) {
  if (value == null) return '—';
  return value.toFixed(2);
}

function formatPercent(value) {
  if (value == null) return '—';
  return `${value.toFixed(1)}%`;
}
