import maplibregl from 'maplibre-gl';
import { awaitingFirstObservation, isStale, tierColor } from './data.js';

const INDIA_BOUNDS = [
  [67.0, 6.5],
  [98.5, 36.5],
];
const STALE_COLOR = '#4a5d6c';
const PENDING_COLOR = '#b0aba0';
const AOI_SOURCE_ID = 'reservoir-aois';
const AOI_FILL_LAYER_ID = 'reservoir-aois-fill';
const AOI_LINE_LAYER_ID = 'reservoir-aois-line';
const AOI_ACTIVE_LAYER_ID = 'reservoir-aois-active-line';
const TIER_COLORS = {
  critical: '#b83b3b',
  warning: '#d4842d',
  watch: '#c6a53f',
  stable: '#4d8b69',
  stale: STALE_COLOR,
  pending: PENDING_COLOR,
};

// Track pin DOM elements so we can highlight the active reservoir from list clicks.
const pinElements = new Map();
const aoiCache = new Map();
let markers = [];
let overlayMap = null;
let overlayRequestId = 0;

export async function initMap(elementId) {
  // Carto Positron — minimal label noise, lets the pins do the talking.
  const map = new maplibregl.Map({
    container: elementId,
    style: {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources: {
        carto: {
          type: 'raster',
          tiles: [
            'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
            'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
            'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          ],
          tileSize: 256,
          attribution:
            '© <a href="https://carto.com/attribution">CARTO</a> · © OpenStreetMap contributors',
        },
      },
      layers: [{ id: 'carto', type: 'raster', source: 'carto' }],
    },
    bounds: INDIA_BOUNDS,
    fitBoundsOptions: { padding: 50 },
    attributionControl: { compact: true },
  });
  await new Promise((resolve) => map.on('load', resolve));
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  installAoiLayers(map);
  overlayMap = map;
  return map;
}

export function plotReservoirs(map, reservoirs, { onSelect }) {
  overlayMap = map;
  for (const marker of markers) marker.remove();
  markers = [];
  pinElements.clear();
  renderAoiOverlays(map, reservoirs);
  for (const reservoir of reservoirs) {
    const pending = awaitingFirstObservation(reservoir);
    const stale = !pending && isStale(reservoir);
    const el = document.createElement('button');
    el.type = 'button';
    const tier = pending ? 'pending' : stale ? 'stale' : reservoir.tier;
    el.className = `pin pin--${tier}`;
    el.style.setProperty('--pin-color', TIER_COLORS[tier] ?? tierColor(reservoir.tier));
    const tierLabel = pending ? 'awaiting first observation' : reservoir.tier;
    const days = reservoir.projection?.neutral_monsoon?.days_to_dead_storage;
    const tooltip = days != null
      ? `${reservoir.name} — ${tierLabel} · ${days}d to dead storage`
      : `${reservoir.name} — ${tierLabel}`;
    el.title = tooltip;
    el.setAttribute('aria-label', tooltip);
    el.addEventListener('click', () => onSelect(reservoir));

    const marker = new maplibregl.Marker({ element: el })
      .setLngLat([reservoir.lon, reservoir.lat])
      .addTo(map);
    markers.push(marker);
    pinElements.set(reservoir.id, el);
  }
}

export function setActivePin(reservoirId) {
  for (const [id, el] of pinElements.entries()) {
    el.classList.toggle('is-active', id === reservoirId);
  }
  if (overlayMap?.getLayer(AOI_ACTIVE_LAYER_ID)) {
    overlayMap.setFilter(AOI_ACTIVE_LAYER_ID, ['==', ['get', 'id'], reservoirId]);
  }
}

export function focusReservoir(map, reservoir) {
  map.flyTo({ center: [reservoir.lon, reservoir.lat], zoom: 7.5, speed: 1.2 });
}

export function fitReservoirs(map, reservoirs, { animate = true } = {}) {
  const visible = reservoirs.filter((r) => Number.isFinite(r.lon) && Number.isFinite(r.lat));
  if (!visible.length) {
    map.fitBounds(INDIA_BOUNDS, {
      duration: animate ? 500 : 0,
      padding: 50,
    });
    return;
  }

  if (visible.length === 1) {
    const [reservoir] = visible;
    if (!animate) {
      map.jumpTo({ center: [reservoir.lon, reservoir.lat], zoom: 7.6 });
      return;
    }
    map.flyTo({
      center: [reservoir.lon, reservoir.lat],
      zoom: 7.6,
      speed: 1.2,
    });
    return;
  }

  const bounds = new maplibregl.LngLatBounds();
  for (const reservoir of visible) bounds.extend([reservoir.lon, reservoir.lat]);
  map.fitBounds(bounds, {
    duration: animate ? 550 : 0,
    maxZoom: 6.8,
    padding: { top: 54, right: 54, bottom: 54, left: 54 },
  });
}

function installAoiLayers(map) {
  if (!map.getSource(AOI_SOURCE_ID)) {
    map.addSource(AOI_SOURCE_ID, {
      type: 'geojson',
      data: emptyFeatureCollection(),
    });
  }

  if (!map.getLayer(AOI_FILL_LAYER_ID)) {
    map.addLayer({
      id: AOI_FILL_LAYER_ID,
      type: 'fill',
      source: AOI_SOURCE_ID,
      paint: {
        'fill-color': colorExpression(),
        'fill-opacity': [
          'case',
          ['==', ['get', 'tier'], 'critical'],
          0.22,
          0.14,
        ],
      },
    });
  }

  if (!map.getLayer(AOI_LINE_LAYER_ID)) {
    map.addLayer({
      id: AOI_LINE_LAYER_ID,
      type: 'line',
      source: AOI_SOURCE_ID,
      paint: {
        'line-color': colorExpression(),
        'line-opacity': 0.8,
        'line-width': 1.4,
      },
    });
  }

  if (!map.getLayer(AOI_ACTIVE_LAYER_ID)) {
    map.addLayer({
      id: AOI_ACTIVE_LAYER_ID,
      type: 'line',
      source: AOI_SOURCE_ID,
      filter: ['==', ['get', 'id'], ''],
      paint: {
        'line-color': '#141414',
        'line-opacity': 0.9,
        'line-width': 3,
      },
    });
  }
}

async function renderAoiOverlays(map, reservoirs) {
  const requestId = ++overlayRequestId;
  const features = (
    await Promise.all(reservoirs.map((reservoir) => aoiFeatureForReservoir(reservoir)))
  ).filter(Boolean);
  if (requestId !== overlayRequestId) return;
  const source = map.getSource(AOI_SOURCE_ID);
  if (source) {
    source.setData({
      type: 'FeatureCollection',
      features,
    });
  }
}

async function aoiFeatureForReservoir(reservoir) {
  if ((reservoir.scope ?? 'core_city') !== 'core_city') return null;
  const feature = await loadAoiFeature(reservoir.id);
  if (!feature?.geometry) return null;
  const pending = awaitingFirstObservation(reservoir);
  const stale = !pending && isStale(reservoir);
  const tier = pending ? 'pending' : stale ? 'stale' : reservoir.tier;
  return {
    type: 'Feature',
    geometry: feature.geometry,
    properties: {
      ...(feature.properties ?? {}),
      id: reservoir.id,
      name: reservoir.name,
      tier,
    },
  };
}

async function loadAoiFeature(reservoirId) {
  if (!aoiCache.has(reservoirId)) {
    aoiCache.set(
      reservoirId,
      fetch(`/data/aois/${reservoirId}.geojson`)
        .then((response) => (response.ok ? response.json() : null))
        .then(normalizeFeature)
        .catch(() => null),
    );
  }
  return aoiCache.get(reservoirId);
}

function normalizeFeature(data) {
  if (!data) return null;
  if (data.type === 'Feature') return data;
  if (data.type === 'FeatureCollection') return data.features?.[0] ?? null;
  if (data.type === 'Polygon' || data.type === 'MultiPolygon') {
    return { type: 'Feature', geometry: data, properties: {} };
  }
  return null;
}

function colorExpression() {
  return [
    'match',
    ['get', 'tier'],
    'critical',
    TIER_COLORS.critical,
    'warning',
    TIER_COLORS.warning,
    'watch',
    TIER_COLORS.watch,
    'stable',
    TIER_COLORS.stable,
    'stale',
    TIER_COLORS.stale,
    TIER_COLORS.pending,
  ];
}

function emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] };
}
