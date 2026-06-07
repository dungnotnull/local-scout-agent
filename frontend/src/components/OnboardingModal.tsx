import React from 'react';

interface Props {
  onClose: () => void;
}

export default function OnboardingModal({ onClose }: Props) {
  return (
    <div className="fixed inset-0 z-[2000] bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl">
        <div className="text-center mb-4">
          <div className="text-4xl mb-2">\ud83c\udf7d\ufe0f</div>
          <h2 className="text-xl font-bold text-slate-900">Welcome to Local Scout</h2>
          <p className="text-sm text-slate-500 mt-1">
            Discover authentic local restaurants — not tourist traps.
          </p>
        </div>

        <div className="space-y-3 mb-6">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 flex-shrink-0 text-sm font-bold">1</div>
            <div>
              <p className="text-sm font-medium text-slate-800">Set your location</p>
              <p className="text-xs text-slate-500">Tap "Locate Me" or search an area</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 flex-shrink-0 text-sm font-bold">2</div>
            <div>
              <p className="text-sm font-medium text-slate-800">Scout for hidden gems</p>
              <p className="text-xs text-slate-500">We crawl local forums and blogs for authentic reviews</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 flex-shrink-0 text-sm font-bold">3</div>
            <div>
              <p className="text-sm font-medium text-slate-800">Explore &amp; eat like a local</p>
              <p className="text-xs text-slate-500">Color-coded markers: Green = authentic, Yellow = mixed, Red = tourist trap</p>
            </div>
          </div>
        </div>

        <button
          onClick={onClose}
          className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl transition-colors"
        >
          Got it — find me hidden gems!
        </button>
      </div>
    </div>
  );
}
