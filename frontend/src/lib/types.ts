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
  timeout_seconds?: number;
  is_active: boolean;
  use_proxy?: boolean;
  proxy_url?: string | null;
  headers?: Record<string, unknown>;
  cookies?: Record<string, unknown>;
  auth?: Record<string, unknown>;
  selectors?: Record<string, unknown>;
  city_ids?: number[];
  last_checked_at?: string;
  last_error?: string;
  error_count: number;
}

export interface NewsMedia {
  id: number;
  type: string;
  remote_url?: string | null;
  processed_path?: string | null;
  file_path?: string | null;
  is_spoiler: boolean;
  is_enabled: boolean;
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
  author_name?: string | null;
  submitted_anonymously?: boolean;
  submitted_by_telegram_id?: number | null;
  moderated_by?: number | null;
  source_published_at?: string | null;
  processed_at?: string | null;
  template_id?: number | null;
  emoji?: string | null;
  is_edited?: boolean;
  is_world_news?: boolean;
  published_message_ids?: Record<string, number[]>;
  media?: NewsMedia[];
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
  total_channels: number;
  active_channels: number;
  channels_by_city: { city: string; count: number }[];
  bot_submissions: number;
  bot_unique_users: number;
  bot_anonymous: number;
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
  telegram_id?: number | null;
  yandex_id?: string | null;
  permissions?: { grant?: string[]; deny?: string[] };
}
