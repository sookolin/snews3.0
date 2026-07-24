export interface City {
  id: number;
  name: string;
  slug: string;
  description?: string;
  keywords: string[];
  extra_keywords: string[];
  exclude_keywords: string[];
  region?: string;
  country?: string;
  language: string;
  is_active: boolean;
  telegram_topic_id?: number;
  template_id?: number;
  created_at: string;
}

export interface Source {
  id: number;
  name: string;
  url: string;
  type: string;
  parser_engine: string;
  priority: number;
  check_interval_seconds: number;
  is_active: boolean;
  last_checked_at?: string;
  last_error?: string;
  error_count: number;
}

export interface NewsItem {
  id: number;
  title?: string;
  original_title?: string;
  status: string;
  origin: string;
  city_id?: number;
  source_id?: number;
  match_score?: number;
  is_spoiler: boolean;
  scheduled_at?: string;
  published_at?: string;
  created_at: string;
}

export interface DashboardStats {
  total_news: number;
  published: number;
  pending: number;
  rejected: number;
  failed: number;
  duplicates: number;
  total_cities: number;
  active_sources: number;
  total_sources: number;
  by_status: { status: string; count: number }[];
  last_7_days: { date: string; count: number }[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface User {
  id: number;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
  is_2fa_enabled: boolean;
  language: string;
}
