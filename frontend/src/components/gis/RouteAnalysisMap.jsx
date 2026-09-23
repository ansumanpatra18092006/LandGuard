import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const lineColors = ['#0f766e', '#2563eb', '#b45309'];
const corridorColors = ['rgba(15,118,110,0.18)', 'rgba(37,99,235,0.12)', 'rgba(180,83,9,0.12)'];

function marker(label, className) {
  return L.divIcon({
    className: '',
    html: `<span class="route-point-marker ${className}"><b>${label}</b></span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function smoothRoadConcept(coords, variantIndex = 0) {
  if (!Array.isArray(coords) || coords.length < 2) return [];
  const [startLon, startLat] = coords[0];
  const [endLon, endLat] = coords[coords.length - 1];
  const meanLat = (startLat + endLat) / 2;
  const metresPerLat = 111_320.0;
  const metresPerLon = 111_320.0 * Math.max(Math.cos((meanLat * Math.PI) / 180), 0.2);
  const dx = (endLon - startLon) * metresPerLon;
  const dy = (endLat - startLat) * metresPerLat;
  const length = Math.max(Math.hypot(dx, dy), 1.0);
  const px = -dy / length;
  const py = dx / length;

  const profiles = [
    [-0.045, 0.060],
    [0.020, -0.055],
    [0.070, 0.020],
    [-0.030, 0.075],
    [0.048, -0.040],
  ];
  const [f1, f2] = profiles[variantIndex % profiles.length];
  const capM = clamp(length * 0.09, 1400, 5400);
  const offset1 = clamp(length * f1, -capM, capM);
  const offset2 = clamp(length * f2, -capM, capM);

  const p0 = [0, 0];
  const p1 = [dx * 0.28 + px * offset1, dy * 0.28 + py * offset1];
  const p2 = [dx * 0.72 + px * offset2, dy * 0.72 + py * offset2];
  const p3 = [dx, dy];

  const latlngs = [];
  const samples = 64;
  for (let i = 0; i < samples; i += 1) {
    const t = i / (samples - 1);
    const omt = 1 - t;
    const x = (omt ** 3) * p0[0]
      + 3 * (omt ** 2) * t * p1[0]
      + 3 * omt * (t ** 2) * p2[0]
      + (t ** 3) * p3[0];
    const y = (omt ** 3) * p0[1]
      + 3 * (omt ** 2) * t * p1[1]
      + 3 * omt * (t ** 2) * p2[1]
      + (t ** 3) * p3[1];
    latlngs.push([startLat + y / metresPerLat, startLon + x / metresPerLon]);
  }
  return latlngs;
}

function toDisplayLatLngs(candidate, analysis, index) {
  const coords = candidate.geometry?.coordinates || [];
  if (coords.length < 2) return [];
  const base = coords.map(([lon, lat]) => [lat, lon]);
  if (
    analysis?.alignment_mode === 'NEW_ALIGNMENT'
    && analysis?.construction_type === 'ROAD'
    && candidate.candidate_kind === 'GREENFIELD_CONCEPT'
  ) {
    return smoothRoadConcept(coords, index);
  }
  return base;
}

export default function RouteAnalysisMap({ analysis, selectedRouteId, onSelect }) {
  const host = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  useEffect(() => {
    if (!host.current || mapRef.current) return undefined;
    const map = L.map(host.current, { zoomControl: false }).setView([20.59, 78.96], 5);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map);
    L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      attribution: 'Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap',
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;
    const timer = window.setTimeout(() => map.invalidateSize(), 0);
    return () => {
      window.clearTimeout(timer);
      mapRef.current = null;
      layerRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer || !analysis) return;
    layer.clearLayers();

    const all = [];
    analysis.candidates.forEach((candidate, index) => {
      const latlngs = toDisplayLatLngs(candidate, analysis, index);
      if (latlngs.length < 2) return;
      all.push(...latlngs);
      const selected = candidate.route_id === selectedRouteId;
      const recommended = candidate.route_id === analysis.recommended_route_id;

      const halo = L.polyline(latlngs, {
        color: corridorColors[index % corridorColors.length],
        weight: selected ? 22 : recommended ? 16 : 12,
        opacity: selected ? 0.7 : recommended ? 0.55 : 0.4,
        interactive: false,
        lineCap: 'round',
        lineJoin: 'round',
      });
      halo.addTo(layer);

      const line = L.polyline(latlngs, {
        color: lineColors[index % lineColors.length],
        weight: selected ? 6 : recommended ? 5 : 4,
        opacity: selected ? 0.96 : recommended ? 0.88 : 0.58,
        dashArray: selected ? null : recommended ? '10 6' : '8 8',
        lineCap: 'round',
        lineJoin: 'round',
      });
      const burdenText = candidate.route_burden_score == null ? 'screening score unavailable' : `burden ${candidate.route_burden_score.toFixed(1)}/100`;
      const suitability = candidate.feasibility_score == null ? '' : ` · score ${candidate.feasibility_score.toFixed(0)}/100`;
      const basis = candidate.candidate_kind === 'GREENFIELD_CONCEPT' ? 'screening corridor concept' : 'mapped network candidate';
      line.bindTooltip(`${candidate.label} · ${candidate.distance_km.toFixed(2)} km · ${basis} · ${burdenText}${suitability}`, { sticky: true });
      line.on('click', () => onSelect?.(candidate.route_id));
      line.addTo(layer);
    });

    const start = [analysis.origin.latitude, analysis.origin.longitude];
    const end = [analysis.destination.latitude, analysis.destination.longitude];
    L.marker(start, { icon: marker('A', 'start') }).bindTooltip(analysis.origin.label, { direction: 'top' }).addTo(layer);
    L.marker(end, { icon: marker('B', 'end') }).bindTooltip(analysis.destination.label, { direction: 'top' }).addTo(layer);
    all.push(start, end);
    if (all.length) map.fitBounds(L.latLngBounds(all).pad(0.10), { maxZoom: 14, animate: false });
  }, [analysis, selectedRouteId, onSelect]);

  return <div ref={host} className="route-analysis-map" aria-label="Route candidate preview map"/>;
}
