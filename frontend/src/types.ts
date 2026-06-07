export interface Restaurant {
  id: number;
  name: string;
  address: string | null;
  lat: number | null;
  lon: number | null;
  cuisine_type: string | null;
  price_range: string | null;
  gem_score: number | null;
  local_ratio: number | null;
  marketing_signal: number | null;
  distance_km: number | null;
}

export interface Review {
  id: number;
  body_text: string | null;
  rating: number | null;
  likes_count: number;
  published_at: string | null;
  language: string | null;
  author_id_hashed: string | null;
  authenticity_score: number | null;
  classification: string | null;
}

export interface RestaurantDetail extends Restaurant {
  google_place_id?: string | null;
  phone?: string | null;
  website?: string | null;
  gem_score_components?: Record<string, any> | null;
  checkin_count?: number;
  discovered_at?: string | null;
  top_reviews?: Review[];
  dish_recommendations?: string | null;
  hidden_gem_summary?: string | null;
}

export interface SearchParams {
  lat: number;
  lon: number;
  radius_km?: number;
  min_gem_score?: number;
  cuisine_type?: string;
  price_range?: string;
  query?: string;
}

export interface SearchResult {
  restaurants: Restaurant[];
  total: number;
  page: number;
  page_size: number;
  query_lat: number;
  query_lon: number;
}
