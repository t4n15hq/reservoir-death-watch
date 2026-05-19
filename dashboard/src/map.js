import maplibregl from 'maplibre-gl';
import { awaitingFirstObservation, isStale, tierColor } from './data.js';

const INDIA_BOUNDS = [
  [67.0, 6.5],
  [98.5, 36.5],
];
const STALE_COLOR = '#34495e';
const PENDING_COLOR = '#bdc3c7';

export async function initMap(elementId) {
  const map = new maplibregl.Map({
    container: elementId,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
    },
    bounds: INDIA_BOUNDS,
    fitBoundsOptions: { padding: 30 },
  });
  await new Promise((resolve) => map.on('load', resolve));
  return map;
}

export function plotReservoirs(map, snapshot, { onSelect }) {
  for (const reservoir of snapshot.reservoirs) {
    const pending = awaitingFirstObservation(reservoir);
    const stale = !pending && isStale(reservoir);
    const el = document.createElement('button');
    el.type = 'button';
    const modifier = pending ? 'pin--pending' : stale ? 'pin--stale' : '';
    el.className = `pin ${modifier}`.trim();
    el.style.background = pending ? PENDING_COLOR : stale ? STALE_COLOR : tierColor(reservoir.tier);
    const tierLabel = pending ? 'awaiting first observation' : reservoir.tier;
    el.title = `${reservoir.name} (${tierLabel})`;
    el.setAttribute('aria-label', `${reservoir.name}, ${tierLabel}`);
    el.addEventListener('click', () => onSelect(reservoir));

    new maplibregl.Marker({ element: el }).setLngLat([reservoir.lon, reservoir.lat]).addTo(map);
  }
}

export function focusReservoir(map, reservoir) {
  map.flyTo({ center: [reservoir.lon, reservoir.lat], zoom: 8, speed: 1.2 });
}
