import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import FilterPanel from './components/FilterPanel';
import DetailSheet from './components/DetailSheet';
import OnboardingModal from './components/OnboardingModal';
import { Restaurant, SearchParams, SearchResult } from './types';

const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN || '';

function MapController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

function getMarkerColor(gemScore: number | undefined): string {
  if (!gemScore && gemScore !== 0) return 'marker-yellow';
  if (gemScore >= 70) return 'marker-green';
  if (gemScore >= 40) return 'marker-yellow';
  return 'marker-red';
}

function formatGemBadge(score: number | undefined): string {
  if (!score && score !== 0) return '--';
  if (score >= 80) return '\ud83d\udc8e Hidden Gem';
  if (score >= 60) return '\u2b50 Authentic';
  if (score >= 40) return '\ud83d\udc40 Mixed';
  return '\u26a0\ufe0f Tourist Trap';
}

export default function App() {
  const [center, setCenter] = useState<[number, number]>([10.7769, 106.7009]);
  const [zoom, setZoom] = useState(14);
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState<Restaurant | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [filters, setFilters] = useState<SearchParams>({
    lat: 10.7769,
    lon: 106.7009,
    radius_km: 3,
    min_gem_score: 0,
    cuisine_type: '',
    price_range: '',
    query: '',
  });

  const searchRestaurants = useCallback(async (params: SearchParams) => {
    setIsLoading(true);
    setError(null);

    const queryParams = new URLSearchParams();
    queryParams.set('lat', String(params.lat));
    queryParams.set('lon', String(params.lon));
    if (params.radius_km) queryParams.set('radius_km', String(params.radius_km));
    if (params.min_gem_score && params.min_gem_score > 0) queryParams.set('min_gem_score', String(params.min_gem_score));
    if (params.cuisine_type) queryParams.set('cuisine_type', params.cuisine_type);
    if (params.price_range) queryParams.set('price_range', params.price_range);
    if (params.query) queryParams.set('query', params.query);
    queryParams.set('page', '1');
    queryParams.set('page_size', '100');

    try {
      const res = await fetch(`/api/v1/restaurants?${queryParams}`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data: SearchResult = await res.json();
      setRestaurants(data.restaurants);
      if (data.restaurants.length > 0) {
        const avgLat = data.restaurants.reduce((s, r) => s + (r.lat || data.query_lat), 0) / data.restaurants.length;
        const avgLon = data.restaurants.reduce((s, r) => s + (r.lon || data.query_lon), 0) / data.restaurants.length;
        setCenter([avgLat, avgLon]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed');
      setRestaurants([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleFilterChange = (newFilters: SearchParams) => {
    setFilters(newFilters);
    searchRestaurants(newFilters);
  };

  const handleLocateMe = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords: [number, number] = [pos.coords.latitude, pos.coords.longitude];
          setCenter(coords);
          const updated = { ...filters, lat: coords[0], lon: coords[1] };
          setFilters(updated);
          searchRestaurants(updated);
        },
        () => setError('Could not access location')
      );
    }
  };

  const triggerScout = async () => {
    try {
      const res = await fetch('/api/v1/scout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: filters.lat, lon: filters.lon, radius_km: filters.radius_km }),
      });
      if (!res.ok) throw new Error('Scout failed');
      const { job_id } = await res.json();
      pollJobStatus(job_id);
    } catch (e) {
      setError('Failed to trigger scout');
    }
  };

  const pollJobStatus = async (jobId: string) => {
    let attempts = 0;
    const maxAttempts = 60;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/scout/${jobId}`);
        const data = await res.json();
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          if (data.status === 'completed') {
            searchRestaurants(filters);
          } else {
            setError('Crawl job failed');
          }
        }
        attempts++;
        if (attempts >= maxAttempts) clearInterval(interval);
      } catch {
        clearInterval(interval);
      }
    }, 2000);
  };

  return (
    <div className="flex flex-col h-screen">
      {showOnboarding && <OnboardingModal onClose={() => setShowOnboarding(false)} />}

      <header className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-bold tracking-tight">\ud83c\udf7d\ufe0f Local Scout</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleLocateMe}
            className="bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded text-sm font-medium transition-colors"
          >
            \ud83d\udccd Locate Me
          </button>
          <button
            onClick={triggerScout}
            disabled={isLoading}
            className="bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? '\u23f3 Scouting...' : '\ud83d\udd0d Scout Area'}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <FilterPanel filters={filters} onChange={handleFilterChange} />

        <main className="flex-1 relative">
          {error && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[1000] bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded-lg shadow-lg">
              {error}
              <button onClick={() => setError(null)} className="ml-2 font-bold">&times;</button>
            </div>
          )}

          <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} className="h-full w-full">
            <MapController center={center} zoom={zoom} />
            <TileLayer
              attribution='&copy; <a href="https://www.mapbox.com/">Mapbox</a>'
              url={MAPBOX_TOKEN
                ? `https://api.mapbox.com/styles/v1/mapbox/light-v11/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`
                : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
              }
            />
            {restaurants.map((r) => (
              <Marker
                key={r.id}
                position={[r.lat || 0, r.lon || 0]}
                icon={L.divIcon({
                  className: getMarkerColor(r.gem_score),
                  html: `<div style="width:24px;height:24px;border-radius:50%;background:${r.gem_score && r.gem_score >= 70 ? '#059669' : r.gem_score && r.gem_score >= 40 ? '#d97706' : '#dc2626'};border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`,
                  iconSize: [24, 24],
                  iconAnchor: [12, 12],
                })}
              >
                <Popup>
                  <div className="popup-content">
                    <h3 className="font-bold text-sm">{r.name}</h3>
                    <div className="text-xs mt-1">{formatGemBadge(r.gem_score)}</div>
                    {r.distance_km != null && (
                      <div className="text-xs text-slate-500">{r.distance_km.toFixed(1)} km away</div>
                    )}
                    <button
                      onClick={() => setSelectedRestaurant(r)}
                      className="mt-2 text-xs text-blue-600 hover:underline"
                    >
                      View Details \u2192
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>

          {isLoading && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur px-4 py-2 rounded-full shadow-lg text-sm font-medium z-[1000]">
              Scanning for hidden gems...
            </div>
          )}
        </main>
      </div>

      {selectedRestaurant && (
        <DetailSheet
          restaurant={selectedRestaurant}
          onClose={() => setSelectedRestaurant(null)}
        />
      )}
    </div>
  );
}
