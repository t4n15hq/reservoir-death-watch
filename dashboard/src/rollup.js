export function renderStateBand(container, snapshot, stateAggregates = null) {
  const states = stateAggregates?.states ?? [];
  if (!states.length) {
    container.innerHTML = '';
    return;
  }

  const sorted = [...states].sort((a, b) => {
    const ac = (a.tier_counts?.critical ?? 0) + (a.tier_counts?.warning ?? 0);
    const bc = (b.tier_counts?.critical ?? 0) + (b.tier_counts?.warning ?? 0);
    if (ac !== bc) return bc - ac;
    return (a.percent_full ?? 0) - (b.percent_full ?? 0);
  });

  const rows = sorted
    .map(
      (s) => `
        <div class="state-row">
          <span class="state-row__name">${s.state}</span>
          <span class="state-row__pct">${formatPercent(s.percent_full)}</span>
          <span class="state-row__observed">${s.observed_count ?? s.reservoir_count}/${s.reservoir_count}</span>
          <span class="state-row__tiers">
            ${tierBadge('critical', s.tier_counts?.critical)}
            ${tierBadge('warning', s.tier_counts?.warning)}
            ${tierBadge('watch', s.tier_counts?.watch)}
            ${tierBadge('stable', s.tier_counts?.stable)}
          </span>
        </div>
      `,
    )
    .join('');

  container.innerHTML = `
    <div class="states-card">
      <div class="states-card__head">
        <h2>By state</h2>
        <p>${states.length} states · observed/total shown per state.</p>
      </div>
      <div class="states-grid">${rows}</div>
    </div>
  `;
}

function tierBadge(tier, count) {
  const n = count ?? 0;
  if (!n) return `<span class="tier-dot tier-dot--zero">·</span>`;
  return `<span class="tier-dot tier-dot--${tier}" title="${n} ${tier}">${n}</span>`;
}

function formatPercent(value) {
  if (value == null) return '—';
  return `${value.toFixed(1)}%`;
}
