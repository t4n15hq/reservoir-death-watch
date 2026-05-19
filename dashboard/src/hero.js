export function renderHero(snapshot, backtestCase) {
  const reservoirs = snapshot.reservoirs ?? [];
  const observed = reservoirs.filter(
    (r) => !(r.flags ?? []).includes('awaiting_first_observation'),
  );
  const agg = snapshot.national_aggregate ?? {};

  const peopleAtRisk = (agg.people_at_risk_neutral ?? 0) + (agg.people_at_risk_el_nino ?? 0);
  const criticalCount = agg.reservoirs_critical ?? 0;
  const warningCount = agg.reservoirs_warning ?? 0;

  // Hero deck — lead with the most urgent reservoir if any are critical/warning.
  const deckEl = document.getElementById('hero-deck');
  if (deckEl) deckEl.textContent = buildDeck(observed, snapshot, backtestCase);

  // Header meta line.
  const metaEl = document.getElementById('generated-meta');
  if (metaEl) metaEl.innerHTML = buildMeta(snapshot);

  // Stat strip.
  const statsEl = document.getElementById('hero-stats');
  if (statsEl) {
    statsEl.innerHTML = `
      <div class="stat">
        <div class="stat__label">At-risk population</div>
        <div class="stat__value stat__value--critical">${formatPopulation(peopleAtRisk)}<span class="stat__suffix">people</span></div>
        <div class="stat__hint">Downstream of critical + warning reservoirs.</div>
      </div>
      <div class="stat">
        <div class="stat__label">Critical / Warning</div>
        <div class="stat__value">
          <span class="stat__value--critical">${criticalCount}</span>
          <span class="stat__suffix">/</span>
          <span class="stat__value--warning">${warningCount}</span>
        </div>
        <div class="stat__hint">of ${reservoirs.length} reservoirs (${observed.length} observed).</div>
      </div>
      <div class="stat">
        <div class="stat__label">National live storage</div>
        <div class="stat__value">${formatBcm(agg.current_storage_bcm)}<span class="stat__suffix">/ ${formatBcm(agg.total_capacity_bcm)} BCM</span></div>
        <div class="stat__hint">${formatPercent(agg.percent_full)} of FRL across observed reservoirs.</div>
      </div>
      <div class="stat">
        <div class="stat__label">ENSO state</div>
        <div class="stat__value">${formatEnso(snapshot.enso?.state)}</div>
        <div class="stat__hint">${ensoHint(snapshot.enso)}</div>
      </div>
    `;
  }
}

function buildDeck(observed, snapshot, backtestCase) {
  if (backtestCase) {
    return `Historical backtest of ${observed.length} reservoirs — replay of the model as it would have flagged conditions on the case date.`;
  }
  const worst = pickHeadline(observed);
  if (!worst) {
    return 'Satellite-derived early warning for the reservoirs supplying India\'s major cities.';
  }
  const days = worst.projection?.neutral_monsoon?.days_to_dead_storage;
  if (days != null && days < 60) {
    return `${worst.name} — supplying ${worst.city_served || 'urban India'} — is ${days} days from dead storage under a neutral monsoon. ${othersAtTier(observed, 'critical')}`;
  }
  return 'Satellite-derived early warning for the reservoirs supplying India\'s major cities. Updated weekly.';
}

function pickHeadline(observed) {
  const tierOrder = { critical: 0, warning: 1, watch: 2, stable: 3 };
  return [...observed].sort((a, b) => {
    const dt = (tierOrder[a.tier] ?? 9) - (tierOrder[b.tier] ?? 9);
    if (dt !== 0) return dt;
    const da = a.projection?.neutral_monsoon?.days_to_dead_storage ?? 99999;
    const db = b.projection?.neutral_monsoon?.days_to_dead_storage ?? 99999;
    return da - db;
  })[0];
}

function othersAtTier(observed, tier) {
  const count = observed.filter((r) => r.tier === tier).length;
  if (count <= 1) return '';
  return `${count - 1} other ${tier === 'critical' ? 'critical' : 'warning'} reservoirs visible on the map.`;
}

function buildMeta(snapshot) {
  const generated = snapshot.generated_at
    ? new Date(snapshot.generated_at).toISOString().slice(0, 10)
    : 'unknown';
  const model = snapshot.model_version ?? 'unknown';
  return `
    <span><strong>Generated</strong>${generated}</span>
    <span><strong>Model</strong>v${model}</span>
  `;
}

function formatPopulation(n) {
  if (!n) return '—';
  if (n >= 1e7) return `${(n / 1e7).toFixed(1)} Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)} L`;
  return n.toLocaleString();
}

function formatBcm(v) {
  if (v == null) return '—';
  return v.toFixed(2);
}

function formatPercent(v) {
  if (v == null) return '—';
  return `${v.toFixed(1)}%`;
}

function formatEnso(state) {
  if (!state || state === 'unavailable') return '—';
  return state.replaceAll('_', ' ');
}

function ensoHint(enso) {
  if (!enso || enso.state === 'unavailable') return 'NOAA ONI feed unavailable.';
  const oni = enso.oni_latest;
  if (oni == null) return 'ONI not reported.';
  const sign = oni >= 0 ? '+' : '';
  return `ONI ${sign}${oni.toFixed(2)} · El Niño would suppress monsoon refill.`;
}
