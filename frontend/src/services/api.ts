import axios, { AxiosError } from 'axios';
import type { EventsRequest, EventsResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function fetchEvents(
  query: string,
  user_location?: string,
  filters: Partial<EventsRequest> = {}
): Promise<EventsResponse> {
  try {
    const response = await apiClient.post<EventsResponse>('/api/events', {
      query,
      user_location,
      ...filters,
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<{ detail: string }>;
      if (axiosError.response) {
        // Server responded with error status
        throw new Error(
          axiosError.response.data?.detail || 'Server error occurred'
        );
      } else if (axiosError.request) {
        // Request made but no response
        throw new Error('Unable to connect to server. Please try again.');
      }
    }
    throw new Error('An unexpected error occurred');
  }
}

export default apiClient;
