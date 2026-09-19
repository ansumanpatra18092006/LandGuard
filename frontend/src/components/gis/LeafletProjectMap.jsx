import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

function severity(project) {
  if (project.risk_category) return project.risk_category.toLowerCase();
  if (project.legal_disputes >= 2 || project.pending_approvals >= 3) return 'high';
  if (project.legal_disputes || project.pending_approvals) return 'medium';
  return 'low';
}

function markerIcon(project, selected) {
  const level = severity(project);
  return L.divIcon({
    className: '',
    html: `<span class="leaflet-project-marker ${level}${selected ? ' selected' : ''}${project.slip_alert ? ' predictive-alert' : ''}" aria-hidden="true"><span>${project.delay_probability != null ? Math.round(project.delay_probability * 100) : ''}</span></span>`,
    iconSize: [30, 38],
    iconAnchor: [15, 36],
    popupAnchor: [0, -30],
  });
}

export default function LeafletProjectMap({
  projects,
  selected,
  onSelect,
  onBoundsChange,
  locateRequest = 0,
  fitRequest = 0,
}) {
  const host = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(new Map());
  const layerRef = useRef(null);

  // Keep callbacks in refs so changing parent callback identities does not
  // destroy/recreate the Leaflet map.
  const onBoundsChangeRef = useRef(onBoundsChange);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onBoundsChangeRef.current = onBoundsChange;
  }, [onBoundsChange]);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const bounds = useMemo(() => {
    const points = projects.filter(
      (p) => Number.isFinite(p.latitude) && Number.isFinite(p.longitude),
    );
    return points.length
      ? L.latLngBounds(points.map((p) => [p.latitude, p.longitude]))
      : null;
  }, [projects]);

  // Create the Leaflet map exactly once for this mounted component.
  // This intentionally has an empty dependency list. In development,
  // React StrictMode mounts/cleans/re-mounts effects, so cleanup must also
  // cancel every deferred Leaflet operation.
  useEffect(() => {
    if (!host.current || mapRef.current) return undefined;

    let disposed = false;
    let initTimer = null;

    const map = L.map(host.current, {
      zoomControl: false,
      preferCanvas: true,
    }).setView([20.5937, 78.9629], 5);

    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map);

    L.tileLayer(
      'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 17,
        attribution:
          'Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap',
      }
    ).addTo(map);

    const layer = L.layerGroup().addTo(map);

    mapRef.current = map;
    layerRef.current = layer;

    const emitBounds = () => {
      // A queued move/zoom callback may run after React has started cleanup.
      // Never ask Leaflet for bounds after map.remove().
      if (
        disposed ||
        mapRef.current !== map ||
        !map._loaded ||
        !map.getPane('mapPane')
      ) {
        return;
      }

      const callback = onBoundsChangeRef.current;
      if (!callback) return;

      const b = map.getBounds();
      callback({
        min_lat: b.getSouth(),
        max_lat: b.getNorth(),
        min_lon: b.getWest(),
        max_lon: b.getEast(),
      });
    };

    map.on('moveend zoomend', emitBounds);

    // Let the DOM finish laying out before asking Leaflet to calculate size.
    initTimer = window.setTimeout(() => {
      if (disposed || mapRef.current !== map) return;
      map.invalidateSize();
      emitBounds();
    }, 0);

    return () => {
      disposed = true;

      if (initTimer !== null) {
        window.clearTimeout(initTimer);
      }

      map.off('moveend zoomend', emitBounds);

      if (mapRef.current === map) {
        mapRef.current = null;
      }
      if (layerRef.current === layer) {
        layerRef.current = null;
      }

      markersRef.current.clear();
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    markersRef.current.clear();

    projects.forEach((project) => {
      if (
        !Number.isFinite(project.latitude) ||
        !Number.isFinite(project.longitude)
      ) {
        return;
      }

      const marker = L.marker([project.latitude, project.longitude], {
        icon: markerIcon(
          project,
          selected?.project_id === project.project_id,
        ),
        keyboard: true,
      });

      marker.bindTooltip(
        `${project.project_name} · ${project.district}`,
        {
          direction: 'top',
          offset: [0, -25],
          opacity: 0.96,
        },
      );

      const riskLine = project.delay_probability != null
        ? `<span class="gis-popup-risk ${severity(project)}">${Math.round(project.delay_probability * 100)}% ${project.risk_category} · ${project.slip_alert ? 'ALERT' : 'NO ALERT'}</span>`
        : '<span>Predictive risk not scored</span>';
      marker.bindPopup(
        `<div class="gis-popup"><strong>${project.project_name}</strong><span>${project.project_id} · ${project.district}, ${project.state}</span>${riskLine}<span>${project.acquisition_stage.replaceAll('_', ' ')}</span></div>`,
      );

      marker.on('click', () => onSelectRef.current?.(project));
      marker.addTo(layer);
      markersRef.current.set(project.project_id, marker);
    });
  }, [projects, selected?.project_id]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) return;

    const marker = markersRef.current.get(selected.project_id);
    if (!marker) return;

    map.flyTo(
      marker.getLatLng(),
      Math.max(map.getZoom(), 11),
      { duration: 0.65 },
    );
    marker.openPopup();
  }, [selected]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !bounds || !fitRequest) return;

    map.fitBounds(bounds.pad(0.18), {
      maxZoom: 12,
      animate: true,
      duration: 0.6,
    });
  }, [fitRequest, bounds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !locateRequest) return;

    map.locate({
      setView: true,
      maxZoom: 13,
      enableHighAccuracy: true,
    });
  }, [locateRequest]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !bounds) return;

    map.fitBounds(bounds.pad(0.18), {
      maxZoom: 11,
      animate: false,
    });
  }, [bounds]);

  return (
    <div
      ref={host}
      className="leaflet-map"
      aria-label="Interactive project GIS map"
    />
  );
}
