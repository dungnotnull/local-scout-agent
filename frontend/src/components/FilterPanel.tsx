import React from 'react';
import { SearchParams } from '../types';

const CUISINE_OPTIONS = ['', 'vietnamese', 'japanese', 'korean', 'chinese', 'western', 'street_food', 'seafood', 'vegetarian'];
const PRICE_OPTIONS = ['', 'budget', 'moderate', 'expensive', 'luxury'];

interface Props {
  filters: SearchParams;
  onChange: (filters: SearchParams) => void;
}

export default function FilterPanel({ filters, onChange }: Props) {
  const update = (key: keyof SearchParams, value: any) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <aside className="w-72 bg-white border-r border-slate-200 p-4 overflow-y-auto hidden lg:block">
      <h2 className="font-semibold text-slate-800 mb-4">Filters</h2>

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Search</label>
          <input
            type="text"
            value={filters.query || ''}
            onChange={(e) => update('query', e.target.value)}
            placeholder="e.g. best pho local..."
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Radius (km)</label>
          <input
            type="range"
            min="0.5"
            max="20"
            step="0.5"
            value={filters.radius_km || 3}
            onChange={(e) => update('radius_km', parseFloat(e.target.value))}
            className="w-full accent-emerald-600"
          />
          <div className="text-xs text-slate-400 text-right">{filters.radius_km || 3} km</div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Min Gem Score</label>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={filters.min_gem_score || 0}
            onChange={(e) => update('min_gem_score', parseInt(e.target.value))}
            className="w-full accent-emerald-600"
          />
          <div className="text-xs text-slate-400 text-right">{filters.min_gem_score || 0}</div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Cuisine</label>
          <select
            value={filters.cuisine_type || ''}
            onChange={(e) => update('cuisine_type', e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-emerald-500 outline-none"
          >
            {CUISINE_OPTIONS.map((c) => (
              <option key={c} value={c}>{c === '' ? 'All cuisines' : c.replace('_', ' ')}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Price</label>
          <select
            value={filters.price_range || ''}
            onChange={(e) => update('price_range', e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-emerald-500 outline-none"
          >
            {PRICE_OPTIONS.map((p) => (
              <option key={p} value={p}>{p === '' ? 'All prices' : p}</option>
            ))}
          </select>
        </div>
      </div>
    </aside>
  );
}
