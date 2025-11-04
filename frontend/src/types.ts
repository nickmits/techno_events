export interface EventsRequest {
  query: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  days_ahead?: number;
  user_location?: string;
  thread_id?: string;
  resume_value?: string;
}

export interface Event {
  title: string;
  venue: string;
  event_date: string;
  url: string;
  source: string;
  location?: string;
  attending?: string;
  music_types?: string;
  distance_km?: number;
  drive_time_min?: number;
  walk_time_min?: number;
  venue_lat?: number;
  venue_lon?: number;
}

export interface EventSource {
  name: string;
  content: string;
}

export interface InterruptPayload {
  type: string;
  message: string;
  dates?: {
    start: string;
    end: string;
  };
}

export interface EventsResponse {
  query: string;
  source: string;
  intro?: string;
  events: Event[];
  sources: EventSource[];
  total_sources: number;
  timestamp: string;
  interrupt?: InterruptPayload | null;
  thread_id?: string;
}

export interface SearchFilters {
  location?: string;
  start_date?: string;
  end_date?: string;
}
