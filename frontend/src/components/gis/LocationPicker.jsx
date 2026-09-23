import { useEffect, useRef, useState } from 'react';
import { Crosshair, MapPin, Search } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../../services/api';

const INDIA_CENTER = [22.9734, 78.6569];

function pointIcon() {
  return L.divIcon({
    className: '',
    html: '<span class="location-picker-marker" aria-hidden="true"><span></span></span>',
    iconSize: [32, 42],
    iconAnchor: [16, 40],
  });
}

export default function LocationPicker({
  latitude,
  longitude,
  state,
  district,
  disabled = false,
  onChange,
}) {
  const hostRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const onChangeRef = useRef(onChange);
  const disabledRef = useRef(disabled);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState('');
  const [label, setLabel] = useState('');

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    disabledRef.current = disabled;
  }, []);

  useEffect(() => {
    if (!hostRef.current || mapRef.current) return undefined;

    const hasPoint = Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude))
      && latitude !== '' && longitude !== '';
    const center = hasPoint ? [Number(latitude), Number(longitude)] : INDIA_CENTER;
    const map = L.map(hostRef.current, {
      zoomControl: true,
    }).setView(center, hasPoint ? 13 : 5);

    L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      attribution: 'Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap',
    }).addTo(map);

    map.on('click', (event) => {
      if (disabledRef.current) return;
      setError('');
      setResults([]);
      setLabel('Selected directly on map');
      onChangeRef.current?.({
        latitude: Number(event.latlng.lat.toFixed(7)),
        longitude: Number(event.latlng.lng.toFixed(7)),
      });
    });

    mapRef.current = map;
    const resizeFrame = requestAnimationFrame(() => {
      if (mapRef.current === map) map.invalidateSize();
    });

    return () => {
      cancelAnimationFrame(resizeFrame);
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
  }, [disabled]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const lat = Number(latitude);
    const lon = Number(longitude);
    const hasPoint = latitude !== '' && longitude !== '' && Number.isFinite(lat) && Number.isFinite(lon);

    if (!hasPoint) {
      if (markerRef.current) {
        map.removeLayer(markerRef.current);
        markerRef.current = null;
      }
      return;
    }

    if (!markerRef.current) {
      markerRef.current = L.marker([lat, lon], {
        icon: pointIcon(),
        keyboard: true,
        title: 'Selected project location',
      }).addTo(map);
    } else {
      markerRef.current.setLatLng([lat, lon]);
    }
  }, [latitude, longitude]);

  async function searchLocation(event) {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    setSearching(true);
    setError('');
    setResults([]);
    try {
      const context = [text, district, state, 'India'].filter(Boolean).join(', ');
      const rows = await api(`/gis/geocode?q=${encodeURIComponent(context)}`);
      setResults(rows);
      if (!rows.length) setError('No matching place found. Try a village, town, landmark, tehsil or district name.');
    } catch (err) {
      setError(err.message || 'Place search is temporarily unavailable. You can still click the map.');
    } finally {
      setSearching(false);
    }
  }

  function chooseResult(result) {
    setResults([]);
    setLabel(result.display_name);
    onChangeRef.current?.({ latitude: result.latitude, longitude: result.longitude });
    const map = mapRef.current;
    if (map) map.flyTo([result.latitude, result.longitude], 15, { duration: 0.6 });
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError('This browser does not provide device location. Search or click the map instead.');
      return;
    }
    setLocating(true);
    setError('');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const point = {
          latitude: Number(position.coords.latitude.toFixed(7)),
          longitude: Number(position.coords.longitude.toFixed(7)),
        };
        setLabel('Device location');
        onChangeRef.current?.(point);
        mapRef.current?.flyTo([point.latitude, point.longitude], 16, { duration: 0.6 });
        setLocating(false);
      },
      () => {
        setError('Location permission was unavailable. Search or click the map instead.');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    );
  }

  const selected = latitude !== '' && longitude !== ''
    && Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude));

  return (
    <section className="location-picker" aria-labelledby="project-location-title">
      <div className="location-picker-heading">
        <div>
          <div className="eyebrow">PROJECT LOCATION</div>
          <h3 id="project-location-title">Select the site on the map</h3>
          <p>Search an area or click the map. LandGuard stores the coordinates automatically.</p>
        </div>
        <button type="button" className="button location-current" disabled={disabled || locating} onClick={useCurrentLocation}>
          <Crosshair size={16}/>{locating ? 'Locating…' : 'Use current location'}
        </button>
      </div>

      <div className="location-search">
        <div className="location-search-box">
          <Search size={17}/>
          <input
            value={query}
            disabled={disabled}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                if (!searching && query.trim()) searchLocation(event);
              }
            }}
            placeholder="Village, tehsil, town, landmark or project area"
            aria-label="Search project location"
          />
        </div>
        <button type="button" className="button" onClick={searchLocation} disabled={disabled || searching || !query.trim()}>
          {searching ? 'Searching…' : 'Find on map'}
        </button>
      </div>

      {results.length > 0 && (
        <div className="location-results" role="listbox" aria-label="Location search results">
          {results.map((result, index) => (
            <button
              type="button"
              key={`${result.latitude}-${result.longitude}-${index}`}
              onClick={() => chooseResult(result)}
              className="location-result"
            >
              <MapPin size={15}/><span>{result.display_name}</span>
            </button>
          ))}
        </div>
      )}

      {error && <div className="location-error">{error}</div>}

      <div ref={hostRef} className="location-picker-map" aria-label="Map for selecting project location"/>

      <div className={`location-selection ${selected ? 'selected' : ''}`}>
        <MapPin size={17}/>
        <div>
          <strong>{selected ? 'Project location captured' : 'Location required'}</strong>
          <span>{selected ? (label || `${district || 'Selected area'}, ${state || 'India'}`) : 'Search above or click directly on the map.'}</span>
          {selected && <small>Technical metadata: {Number(latitude).toFixed(6)}, {Number(longitude).toFixed(6)}</small>}
        </div>
      </div>
    </section>
  );
}
