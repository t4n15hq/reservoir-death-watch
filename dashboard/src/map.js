import maplibregl from 'maplibre-gl';
import { awaitingFirstObservation, isStale, tierColor } from './data.js';

const INDIA_BOUNDS = [
  [67.0, 6.5],
  [98.5, 36.5],
];
const STALE_COLOR = '#4a5d6c';
const PENDING_COLOR = '#b0aba0';

// Track pin DOM elements so we can highlight the active reservoir from list clicks.
const pinElements = new Map();

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
  return map;
}

export function plotReservoirs(map, snapshot, { onSelect }) {
  pinElements.clear();
  for (const reservoir of snapshot.reservoirs) {
    const pending = awaitingFirstObservation(reservoir);
    const stale = !pending && isStale(reservoir);
    const el = document.createElement('button');
    el.type = 'button';
    const modifier = pending ? 'pin--pending' : stale ? 'pin--stale' : '';
    el.className = `pin ${modifier}`.trim();
    el.style.background = pending ? PENDING_COLOR : stale ? STALE_COLOR : tierColor(reservoir.tier);
    const tierLabel = pending ? 'awaiting first observation' : reservoir.tier;
    const days = reservoir.projection?.neutral_monsoon?.days_to_dead_storage;
    const tooltip = days != null
      ? `${reservoir.name} — ${tierLabel} · ${days}d to dead storage`
      : `${reservoir.name} — ${tierLabel}`;
    el.title = tooltip;
    el.setAttribute('aria-label', tooltip);
    el.addEventListener('click', () => onSelect(reservoir));

    new maplibregl.Marker({ element: el }).setLngLat([reservoir.lon, reservoir.lat]).addTo(map);
    pinElements.set(reservoir.id, el);
  }
}

export function setActivePin(reservoirId) {
  for (const [id, el] of pinElements.entries()) {
    el.classList.toggle('is-active', id === reservoirId);
  }
}

export function focusReservoir(map, reservoir) {
  map.flyTo({ center: [reservoir.lon, reservoir.lat], zoom: 7.5, speed: 1.2 });
}
