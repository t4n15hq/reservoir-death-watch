const TIER_ORDER = { critical: 0, warning: 1, watch: 2, stable: 3 };

export function renderReservoirList(container, snapshot, { onSelect }) {
  const sorted = [...(snapshot.reservoirs ?? [])].sort((a, b) => {
    const dt = (TIER_ORDER[a.tier] ?? 9) - (TIER_ORDER[b.tier] ?? 9);
    if (dt !== 0) return dt;
    const da = a.projection?.neutral_monsoon?.days_to_dead_storage ?? 99999;
    const db = b.projection?.neutral_monsoon?.days_to_dead_storage ?? 99999;
    if (da !== db) return da - db;
    return (a.current?.percent_full ?? 0) - (b.current?.percent_full ?? 0);
  });

  container.innerHTML = '';
  for (const reservoir of sorted) {
    const pending = (reservoir.flags ?? []).includes('awaiting_first_observation');
    const tier = pending ? 'stale' : reservoir.tier;
    const days = reservoir.projection?.neutral_monsoon?.days_to_dead_storage;
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'reservoir-row';
    row.dataset.id = reservoir.id;

    const city = reservoir.city_served || '—';
    const valueLabel = pending
      ? 'pending'
      : days != null
        ? `${days}<span class="reservoir-row__sub">days to dead</span>`
        : `${formatPct(reservoir.current?.percent_full)}<span class="reservoir-row__sub">of FRL</span>`;
    const valueClass = days != null && days < 60 ? 'reservoir-row__value reservoir-row__value--critical' : 'reservoir-row__value';

    row.innerHTML = `
      <span class="reservoir-row__bar reservoir-row__bar--${tier}"></span>
      <span class="reservoir-row__body">
        <span class="reservoir-row__name">${reservoir.name}</span>
        <span class="reservoir-row__city">${city}</span>
      </span>
      <span class="${valueClass}">${valueLabel}</span>
    `;
    row.addEventListener('click', () => onSelect(reservoir));
    container.appendChild(row);
  }
}

function formatPct(v) {
  if (v == null) return '—';
  return `${v.toFixed(0)}%`;
}
