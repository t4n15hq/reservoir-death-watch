import maplibregl from 'maplibre-gl';
import { awaitingFirstObservation, isStale } from './data.js';

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
const POINT_SOURCE_ID = 'reservoir-points';
const POINT_RING_LAYER_ID = 'reservoir-points-ring';
const POINT_LAYER_ID = 'reservoir-points';
const POINT_ACTIVE_LAYER_ID = 'reservoir-points-active';
const POINT_HIT_LAYER_ID = 'reservoir-points-hit';
const TIER_COLORS = {
  critical: '#b83b3b',
  warning: '#d4842d',
  watch: '#c6a53f',
  stable: '#4d8b69',
  stale: STALE_COLOR,
  pending: PENDING_COLOR,
};

const aoiCache = new Map();
let currentReservoirsById = new Map();
let currentOnSelect = null;
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
  installPointLayers(map);
  overlayMap = map;
  return map;
}

export function plotReservoirs(map, reservoirs, { onSelect }) {
  overlayMap = map;
  currentOnSelect = onSelect;
  currentReservoirsById = new Map(reservoirs.map((reservoir) => [reservoir.id, reservoir]));
  removeLegacyDomMarkers(map);
  renderAoiOverlays(map, reservoirs);
  renderPointLayer(map, reservoirs);
}

export function setActivePin(reservoirId) {
  if (overlayMap?.getLayer(AOI_ACTIVE_LAYER_ID)) {
    overlayMap.setFilter(AOI_ACTIVE_LAYER_ID, ['==', ['get', 'id'], reservoirId]);
  }
  if (overlayMap?.getLayer(POINT_ACTIVE_LAYER_ID)) {
    overlayMap.setFilter(POINT_ACTIVE_LAYER_ID, ['==', ['get', 'id'], reservoirId]);
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

  const west = Math.min(...visible.map((r) => r.lon));
  const east = Math.max(...visible.map((r) => r.lon));
  const south = Math.min(...visible.map((r) => r.lat));
  const north = Math.max(...visible.map((r) => r.lat));
  const isNationalView = visible.length > 12 || (east - west > 9 && north - south > 12);
  if (isNationalView) {
    map.easeTo({
      center: [80.8, 21.6],
      zoom: 4.15,
      duration: animate ? 500 : 0,
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

function installPointLayers(map) {
  if (!map.getSource(POINT_SOURCE_ID)) {
    map.addSource(POINT_SOURCE_ID, {
      type: 'geojson',
      data: emptyFeatureCollection(),
    });
  }

  if (!map.getLayer(POINT_RING_LAYER_ID)) {
    map.addLayer({
      id: POINT_RING_LAYER_ID,
      type: 'circle',
      source: POINT_SOURCE_ID,
      paint: {
        'circle-radius': [
          'match',
          ['get', 'tier'],
          'critical',
          16,
          'warning',
          13,
          0,
        ],
        'circle-color': colorExpression(),
        'circle-opacity': [
          'match',
          ['get', 'tier'],
          'critical',
          0.2,
          'warning',
          0.13,
          0,
        ],
      },
    });
  }

  if (!map.getLayer(POINT_LAYER_ID)) {
    map.addLayer({
      id: POINT_LAYER_ID,
      type: 'circle',
      source: POINT_SOURCE_ID,
      paint: {
        'circle-radius': [
          'match',
          ['get', 'tier'],
          'critical',
          8.5,
          'warning',
          7.6,
          'pending',
          7.6,
          7,
        ],
        'circle-color': [
          'match',
          ['get', 'tier'],
          'pending',
          'rgba(255,253,246,0.94)',
          'stale',
          'rgba(255,253,246,0.82)',
          'critical',
          TIER_COLORS.critical,
          'warning',
          TIER_COLORS.warning,
          'watch',
          TIER_COLORS.watch,
          'stable',
          TIER_COLORS.stable,
          TIER_COLORS.pending,
        ],
        'circle-stroke-color': [
          'match',
          ['get', 'tier'],
          'pending',
          STALE_COLOR,
          'stale',
          STALE_COLOR,
          '#fffdf6',
        ],
        'circle-stroke-width': [
          'match',
          ['get', 'tier'],
          'pending',
          2,
          'stale',
          2,
          2.2,
        ],
        'circle-opacity': 0.96,
      },
    });
  }

  if (!map.getLayer(POINT_ACTIVE_LAYER_ID)) {
    map.addLayer({
      id: POINT_ACTIVE_LAYER_ID,
      type: 'circle',
      source: POINT_SOURCE_ID,
      filter: ['==', ['get', 'id'], ''],
      paint: {
        'circle-radius': 12,
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': '#141414',
        'circle-stroke-width': 2.6,
        'circle-stroke-opacity': 0.85,
      },
    });
  }

  if (!map.getLayer(POINT_HIT_LAYER_ID)) {
    map.addLayer({
      id: POINT_HIT_LAYER_ID,
      type: 'circle',
      source: POINT_SOURCE_ID,
      paint: {
        'circle-radius': 16,
        'circle-color': 'rgba(0,0,0,0.01)',
        'circle-stroke-width': 0,
      },
    });
    map.on('click', POINT_HIT_LAYER_ID, (event) => {
      const id = event.features?.[0]?.properties?.id;
      const reservoir = currentReservoirsById.get(id);
      if (reservoir && currentOnSelect) currentOnSelect(reservoir);
    });
    map.on('mouseenter', POINT_HIT_LAYER_ID, () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', POINT_HIT_LAYER_ID, () => {
      map.getCanvas().style.cursor = '';
    });
  }
}

function renderPointLayer(map, reservoirs) {
  const source = map.getSource(POINT_SOURCE_ID);
  if (!source) return;
  source.setData({
    type: 'FeatureCollection',
    features: reservoirs
      .filter((r) => Number.isFinite(r.lon) && Number.isFinite(r.lat))
      .map((reservoir) => {
        const pending = awaitingFirstObservation(reservoir);
        const stale = !pending && isStale(reservoir);
        const tier = pending ? 'pending' : stale ? 'stale' : reservoir.tier;
        return {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [reservoir.lon, reservoir.lat],
          },
          properties: {
            id: reservoir.id,
            name: reservoir.name,
            tier,
          },
        };
      }),
  });
}

function removeLegacyDomMarkers(map) {
  // Older dev-server bundles used MapLibre HTML markers; clear any that HMR
  // left behind so only native map-layer points remain.
  const container = map.getContainer();
  container.querySelectorAll('.maplibregl-marker').forEach((marker) => marker.remove());
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
