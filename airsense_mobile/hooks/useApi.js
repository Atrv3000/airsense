/**
 * AirSense Mumbai — Unified API Client & React Query Hooks
 * Powered by @tanstack/react-query with automated foreground synchronization,
 * offline caching, deduplication, and honest data classification.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ENDPOINTS } from '../config';

async function fetcher(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error('Data endpoint not found (404). Check API configuration.');
      } else if (res.status === 429) {
        throw new Error('Rate limit exceeded (429). Please wait a moment.');
      } else if (res.status >= 500) {
        throw new Error(`Server temporarily unavailable (${res.status}). Service restarting.`);
      } else {
        throw new Error(`Request returned HTTP status ${res.status}`);
      }
    }
    return await res.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error('Network request timed out. Please check your connectivity.');
    }
    throw err;
  }
}

export const QUERY_KEYS = {
  LIVE_AQI: ['liveAqi'],
  STATIONS: ['stations'],
  FORECAST: (stationId, hours) => ['forecast', stationId, hours],
  HISTORY: (stationId, limit) => ['history', stationId, limit],
  ALERTS: ['alerts'],
  HEALTH: ['health'],
  TELEMETRY: ['telemetry'],
  MAP_LAYERS: ['mapLayers'],
  MODEL_METRICS: ['modelMetrics'],
};

// 1. Live AQI Feed (refreshes every 5m)
export function useLiveAQI(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.LIVE_AQI,
    queryFn: () => fetcher(ENDPOINTS.liveAqi),
    refetchInterval: 300_000, // 5 minutes foreground polling
    staleTime: 60_000,        // Fresh for 1 minute
    ...options,
  });
}

// 2. Monitoring Stations List
export function useStations(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.STATIONS,
    queryFn: () => fetcher(ENDPOINTS.stations),
    staleTime: 300_000,
    ...options,
  });
}

// 3. Station AQI Forecast (24h / 48h)
export function useForecast(stationId, hours = 24, options = {}) {
  const url = stationId
    ? `${ENDPOINTS.predict}?station_id=${stationId}&hours=${hours}`
    : `${ENDPOINTS.predict}?hours=${hours}`;

  return useQuery({
    queryKey: QUERY_KEYS.FORECAST(stationId, hours),
    queryFn: () => fetcher(url),
    enabled: options.enabled !== undefined ? options.enabled : true,
    refetchInterval: 300_000,
    staleTime: 120_000,
    ...options,
  });
}

// 4. Historical AQI Trend
export function useHistoricalTrend(stationId = null, limit = 24, options = {}) {
  const url = stationId
    ? `${ENDPOINTS.historicalAqi}?station_id=${stationId}&limit=${limit}`
    : `${ENDPOINTS.historicalAqi}?limit=${limit}`;

  return useQuery({
    queryKey: QUERY_KEYS.HISTORY(stationId, limit),
    queryFn: () => fetcher(url),
    staleTime: 120_000,
    ...options,
  });
}

// 5. Active & Historical Alerts
export function useAlerts(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.ALERTS,
    queryFn: () => fetcher(ENDPOINTS.alerts),
    refetchInterval: 120_000, // Check alerts every 2 minutes
    staleTime: 30_000,
    ...options,
  });
}

// 6. System Health Check
export function useSystemHealth(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.HEALTH,
    queryFn: () => fetcher(ENDPOINTS.health),
    refetchInterval: 60_000,
    staleTime: 30_000,
    ...options,
  });
}

// 7. System Telemetry
export function useSystemTelemetry(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.TELEMETRY,
    queryFn: () => fetcher(ENDPOINTS.healthTelemetry),
    refetchInterval: 120_000,
    staleTime: 60_000,
    ...options,
  });
}

// 8. Unified Map Layers (Stations + Hotspots + Forecasts)
export function useUnifiedMapLayers(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.MAP_LAYERS,
    queryFn: () => fetcher(ENDPOINTS.mapLayers),
    refetchInterval: 300_000,
    staleTime: 120_000,
    ...options,
  });
}

// 9. Model Metrics & Evaluation (MAE, RMSE, R²)
export function useModelMetrics(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.MODEL_METRICS,
    queryFn: () => fetcher(ENDPOINTS.modelMetrics),
    staleTime: 300_000,
    ...options,
  });
}

// 10. Forecast Verification (Continuous Rolling Error)
export function useForecastVerification(options = {}) {
  return useQuery({
    queryKey: ['forecastVerification'],
    queryFn: () => fetcher(ENDPOINTS.forecastVerification),
    staleTime: 300_000,
    ...options,
  });
}
