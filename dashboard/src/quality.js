// Renders the "Data quality" card just above the footer.
// Honest count of what's measured vs derived vs unverified, so readers can
// calibrate trust per field instead of taking the dashboard at face value.

export function renderDataQuality(container, provenance, reservoirs = null, filters = null) {
  if (!provenance) {
    container.innerHTML = '';
    return;
  }

  const provenanceById = new Map((provenance.reservoirs ?? []).map((r) => [r.id, r]));
  const hasExplicitReservoirs = Array.isArray(reservoirs);
  const rows = hasExplicitReservoirs
    ? reservoirs.map((r) => ({ snapshot: r, provenance: provenanceById.get(r.id) }))
    : (provenance.reservoirs ?? []).map((r) => ({ snapshot: null, provenance: r }));
  const total = rows.length;
  const counts = countCurrentView(rows, hasExplicitReservoirs ? null : (provenance.counts ?? {}));
  const scopeLabel = scopeName(filters?.scope);

  const coverageTiles = [
    {
      label: 'Satellite observed',
      verified: counts.observedWithSatellite,
      hint: 'At least one Sentinel-2 or Sentinel-1 observation.',
      kind: 'coverage',
    },
    {
      label: 'CWC reference loaded',
      verified: counts.cwcReferenceAvailable,
      hint: 'Reservoirs with an authoritative CWC live-storage row in this snapshot.',
      kind: 'coverage',
    },
    {
      label: 'CWC-calibrated storage',
      verified: counts.storageCwcCalibrated,
      hint: 'Power-law area-to-volume curve fit against the loaded CWC row.',
      kind: 'coverage',
    },
    {
      label: 'FRL capacity from CWC',
      verified: counts.fullPoolCapacityFromCwc,
      hint: 'Live capacity at FRL loaded from CWC. Dead-storage capacity is still unsourced.',
      kind: 'coverage',
    },
    {
      label: 'AOI polygon available',
      verified: counts.aoiAvailable,
      hint: 'GeoJSON AOI exists and can be rendered on the map. This is not the same as hand review.',
      kind: 'coverage',
    },
  ];

  const backlogTiles = [
    {
      label: 'AOI hand reviewed',
      verified: counts.aoiVisuallyReviewed,
      hint: 'Polygon checked by hand. Auto-derived AOIs remain honest proxies.',
      kind: 'backlog',
    },
    {
      label: 'Coordinates source checked',
      verified: counts.latLonVerified,
      hint: 'Dam lat/lon cross-checked against CWC bulletin or OpenStreetMap.',
      kind: 'backlog',
    },
    {
      label: 'Population source checked',
      verified: counts.populationVerified,
      hint: 'Beneficiary population sourced from census or utility data, not estimated.',
      kind: 'backlog',
    },
  ];

  const coverageHtml = coverageTiles
    .map((t) => {
      const pct = total ? Math.round((t.verified / total) * 100) : 0;
      const cls = qualityClass(t.verified, total, t.kind);
      return tileHtml(t, total, pct, cls);
    })
    .join('');

  const backlogHtml = backlogTiles
    .map((t) => {
      const pct = total ? Math.round((t.verified / total) * 100) : 0;
      const cls = qualityClass(t.verified, total, t.kind);
      return tileHtml(t, total, pct, cls);
    })
    .join('');

  const generated = provenance.generated_at
    ? new Date(provenance.generated_at).toISOString().slice(0, 16).replace('T', ' ')
    : null;

  container.innerHTML = `
    <div class="quality-card">
      <div class="quality-card__head">
        <h2>Data quality · ${scopeLabel}</h2>
        <p>
          Current-view counts for ${total} reservoir${total === 1 ? '' : 's'}.
          Coverage means the field is loaded enough to use; source checks are the manual verification backlog.
          See <a href="https://github.com/t4n15hq/reservoir-death-watch/blob/main/docs/PROVENANCE.md">docs/PROVENANCE.md</a> for per-field sources.
          ${generated ? `<span class="quality-card__gen">audited ${generated} UTC</span>` : ''}
        </p>
      </div>
      <div class="quality-group">
        <div class="quality-group__label">Operational coverage</div>
        <div class="quality-grid">${coverageHtml}</div>
      </div>
      <div class="quality-group">
        <div class="quality-group__label">Manual source checks</div>
        <div class="quality-grid quality-grid--compact">${backlogHtml}</div>
      </div>
      <div class="quality-card__foot">
        <span class="quality-key"><span class="quality-key__dot quality-key__dot--coverage"></span> loaded from satellite, CWC, or AOI artifacts</span>
        <span class="quality-key"><span class="quality-key__dot quality-key__dot--backlog"></span> honest backlog, not silently marked verified</span>
      </div>
    </div>
  `;
}

function countCurrentView(rows, fallbackCounts) {
  if (!rows.length) {
    return {
      observedWithSatellite: fallbackCounts?.observed_with_satellite ?? 0,
      cwcReferenceAvailable: fallbackCounts?.cwc_reference_available ?? 0,
      storageCwcCalibrated: fallbackCounts?.storage_cwc_calibrated ?? 0,
      fullPoolCapacityFromCwc: fallbackCounts?.full_pool_capacity_from_cwc ?? 0,
      aoiAvailable: fallbackCounts?.aoi_available ?? 0,
      aoiVisuallyReviewed: fallbackCounts?.aoi_visually_reviewed ?? 0,
      latLonVerified: fallbackCounts?.lat_lon_verified ?? 0,
      populationVerified: fallbackCounts?.population_verified_against_census ?? 0,
    };
  }

  return {
    observedWithSatellite: rows.filter(({ snapshot, provenance }) => {
      const asOf = snapshot?.current?.as_of ?? provenance?.current_observation?.as_of;
      return asOf && asOf !== '1900-01-01';
    }).length,
    cwcReferenceAvailable: rows.filter(({ snapshot, provenance }) => (
      snapshot?.current?.cwc_reported_bcm ?? provenance?.cwc_reference?.reported_bcm
    ) != null).length,
    storageCwcCalibrated: rows.filter(({ snapshot, provenance }) => (
      snapshot?.flags ?? []
    ).includes('cwc_calibrated_single_point') || provenance?.storage_calibration?.cwc_anchored).length,
    fullPoolCapacityFromCwc: rows.filter(({ provenance }) => (
      provenance?.full_pool_capacity_bcm?.verified
    )).length,
    aoiAvailable: rows.filter(({ provenance }) => provenance?.aoi?.available).length,
    aoiVisuallyReviewed: rows.filter(({ provenance }) => provenance?.aoi?.verified).length,
    latLonVerified: rows.filter(({ provenance }) => provenance?.lat_lon?.verified).length,
    populationVerified: rows.filter(({ provenance }) => provenance?.population_served?.verified).length,
  };
}

function tileHtml(tile, total, pct, cls) {
  return `
    <div class="quality-tile ${cls}" data-kind="${tile.kind}">
      <div class="quality-tile__count">
        <span class="quality-tile__num">${tile.verified}</span>
        <span class="quality-tile__total">of ${total}</span>
      </div>
      <div class="quality-tile__label">${tile.label}</div>
      <div class="quality-tile__bar"><span style="width:${pct}%"></span></div>
      <div class="quality-tile__hint">${tile.hint}</div>
    </div>
  `;
}

function qualityClass(verified, total, kind) {
  if (verified >= total && total > 0) return 'quality-tile--full';
  if (kind === 'backlog') return 'quality-tile--todo';
  return verified === 0 ? 'quality-tile--zero' : 'quality-tile--partial';
}

function scopeName(scope) {
  if (scope === 'core_city') return 'core city';
  if (scope === 'expanded_cwc') return 'expanded CWC';
  if (scope === 'all') return 'all scopes';
  return 'current view';
}
