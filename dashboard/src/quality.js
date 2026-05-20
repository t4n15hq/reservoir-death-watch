// Renders the "Data quality" card just above the footer.
// Honest count of what's measured vs derived vs unverified, so readers can
// calibrate trust per field instead of taking the dashboard at face value.

export function renderDataQuality(container, provenance) {
  if (!provenance) {
    container.innerHTML = '';
    return;
  }
  const c = provenance.counts ?? {};
  const total = c.total_reservoirs ?? 0;

  const tiles = [
    {
      label: 'Satellite observed',
      verified: c.observed_with_satellite ?? 0,
      hint: 'At least one Sentinel-2 or Sentinel-1 observation.',
      kind: 'measured',
    },
    {
      label: 'CWC reference loaded',
      verified: c.cwc_reference_available ?? 0,
      hint: 'Reservoirs with an authoritative CWC live-storage row in this snapshot.',
      kind: 'measured',
    },
    {
      label: 'CWC-calibrated storage',
      verified: c.storage_cwc_calibrated ?? 0,
      hint: 'Power-law area-to-volume curve fit against the loaded CWC row.',
      kind: 'measured',
    },
    {
      label: 'FRL capacity from CWC',
      verified: c.full_pool_capacity_from_cwc ?? 0,
      hint: 'Live capacity at FRL loaded from CWC. Dead-storage capacity is still unsourced.',
      kind: 'measured',
    },
    {
      label: 'AOI marked reviewed',
      verified: c.aoi_visually_reviewed ?? 0,
      hint: 'Polygon checked by hand. Auto-derived AOIs remain honest proxies.',
      kind: 'metadata',
    },
    {
      label: 'Coordinates checked',
      verified: c.lat_lon_verified ?? 0,
      hint: 'Dam lat/lon cross-checked against CWC bulletin or OpenStreetMap.',
      kind: 'metadata',
    },
    {
      label: 'Population sourced',
      verified: c.population_verified_against_census ?? 0,
      hint: 'Beneficiary population sourced from census or utility data, not estimated.',
      kind: 'metadata',
    },
  ];

  const tilesHtml = tiles
    .map((t) => {
      const pct = total ? Math.round((t.verified / total) * 100) : 0;
      const cls = t.verified === 0 ? 'quality-tile--zero' : t.verified < total ? 'quality-tile--partial' : 'quality-tile--full';
      return `
        <div class="quality-tile ${cls}" data-kind="${t.kind}">
          <div class="quality-tile__count">
            <span class="quality-tile__num">${t.verified}</span>
            <span class="quality-tile__total">of ${total}</span>
          </div>
          <div class="quality-tile__label">${t.label}</div>
          <div class="quality-tile__bar"><span style="width:${pct}%"></span></div>
          <div class="quality-tile__hint">${t.hint}</div>
        </div>
      `;
    })
    .join('');

  const generated = provenance.generated_at
    ? new Date(provenance.generated_at).toISOString().slice(0, 16).replace('T', ' ')
    : null;

  container.innerHTML = `
    <div class="quality-card">
      <div class="quality-card__head">
        <h2>Data quality</h2>
        <p>
          What is loaded, derived, or still unsourced in this snapshot. Honest counts —
          see <a href="https://github.com/t4n15hq/reservoir-death-watch/blob/main/docs/PROVENANCE.md">docs/PROVENANCE.md</a> for per-field sources.
          ${generated ? `<span class="quality-card__gen">audited ${generated} UTC</span>` : ''}
        </p>
      </div>
      <div class="quality-grid">${tilesHtml}</div>
      <div class="quality-card__foot">
        <span class="quality-key"><span class="quality-key__dot quality-key__dot--measured"></span> measured / loaded from satellite + CWC</span>
        <span class="quality-key"><span class="quality-key__dot quality-key__dot--metadata"></span> metadata or capacity fields needing manual source work</span>
      </div>
    </div>
  `;
}
