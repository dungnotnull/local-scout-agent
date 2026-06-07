import React, { useState, useEffect } from 'react';
import { Restaurant, RestaurantDetail, Review } from '../types';

interface Props {
  restaurant: Restaurant;
  onClose: () => void;
}

export default function DetailSheet({ restaurant, onClose }: Props) {
  const [detail, setDetail] = useState<RestaurantDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'info' | 'reviews' | 'menu'>('info');

  useEffect(() => {
    loadDetail();
  }, [restaurant.id]);

  const loadDetail = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/v1/restaurants/${restaurant.id}`);
      if (!res.ok) throw new Error('Not found');
      const data: RestaurantDetail = await res.json();
      setDetail(data);
    } catch {
      setDetail(null);
    } finally {
      setIsLoading(false);
    }
  };

  const formatScore = (score: number | null | undefined): string => {
    if (score == null) return '--';
    return score.toFixed(1);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[1000] bg-white rounded-t-2xl shadow-2xl border-t border-slate-200 max-h-[60vh] overflow-y-auto">
      <div className="sticky top-0 bg-white px-4 pt-4 pb-2 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="font-bold text-lg text-slate-900">{restaurant.name}</h2>
          <p className="text-xs text-slate-500">{restaurant.address || 'Address unavailable'}</p>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
      </div>

      <div className="flex border-b border-slate-100">
        {(['info', 'reviews', 'menu'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-sm font-medium capitalize ${
              activeTab === tab
                ? 'text-emerald-600 border-b-2 border-emerald-600'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="p-4 space-y-3">
          <div className="skeleton h-4 w-3/4 rounded"></div>
          <div className="skeleton h-4 w-1/2 rounded"></div>
          <div className="skeleton h-4 w-2/3 rounded"></div>
        </div>
      ) : detail ? (
        <div className="p-4">
          {activeTab === 'info' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-2xl">
                  {detail.gem_score != null
                    ? detail.gem_score >= 80 ? '\ud83d\udc8e' : detail.gem_score >= 60 ? '\u2b50' : detail.gem_score >= 40 ? '\ud83d\udc40' : '\u26a0\ufe0f'
                    : ''}
                </span>
                <span className="font-bold text-lg">Gem Score: {formatScore(detail.gem_score)}</span>
              </div>

              {detail.hidden_gem_summary && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-slate-700">
                  {detail.hidden_gem_summary}
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-400 block text-xs">Local Ratio</span>
                  <span className="font-medium">{detail.local_ratio != null ? `${(detail.local_ratio * 100).toFixed(0)}%` : '--'}</span>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-400 block text-xs">Marketing Signal</span>
                  <span className="font-medium">{detail.marketing_signal != null ? (1 - detail.marketing_signal).toFixed(2) : '--'}</span>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-400 block text-xs">Check-ins</span>
                  <span className="font-medium">{detail.checkin_count || 0}</span>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-400 block text-xs">Cuisine</span>
                  <span className="font-medium capitalize">{detail.cuisine_type || 'unknown'}</span>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-400 block text-xs">Price</span>
                  <span className="font-medium capitalize">{detail.price_range || 'unknown'}</span>
                </div>
              </div>

              {detail.dish_recommendations && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm">
                  <h4 className="font-semibold text-emerald-800 mb-1">\ud83c\udf7d\ufe0f Must-Try Dishes</h4>
                  <p className="text-emerald-700 whitespace-pre-wrap">{detail.dish_recommendations}</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'reviews' && (
            <div className="space-y-3">
              {detail.top_reviews && detail.top_reviews.length > 0 ? (
                detail.top_reviews.map((review: Review) => (
                  <div key={review.id} className="border border-slate-200 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-slate-400">
                        Local reviewer #{review.author_id_hashed?.slice(0, 4) || '--'}
                      </span>
                      {review.classification && (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          review.classification === 'organic' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {review.classification}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-700">{review.body_text}</p>
                    {review.authenticity_score != null && (
                      <div className="mt-1 text-xs text-slate-400">
                        Authenticity: {(review.authenticity_score * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-400">No reviews available yet.</p>
              )}
            </div>
          )}

          {activeTab === 'menu' && (
            <div className="text-sm text-slate-500">
              <p>Menu translation coming soon. Use the "Translate Menu" feature in the app.</p>
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 text-sm text-slate-400">Could not load restaurant details.</div>
      )}
    </div>
  );
}
