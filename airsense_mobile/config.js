// Central API configuration and design system tokens for AirSense
import Constants from 'expo-constants';
import { Platform } from 'react-native';

function getApiBaseUrl() {
  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    const ip = hostUri.split(':')[0];
    if (ip) {
      return `http://${ip}:8000`;
    }
  }

  if (Platform.OS === 'web') {
    return 'http://127.0.0.1:8000';
  }

  return 'http://192.168.0.100:8000';
}

export const API_BASE_URL = getApiBaseUrl();

export const ENDPOINTS = {
  health:        `${API_BASE_URL}/api/v1/health/`,
  stations:      `${API_BASE_URL}/api/v1/stations/`,
  liveAqi:       `${API_BASE_URL}/api/v1/aqi/live/`,
  stationAqi:    (id) => `${API_BASE_URL}/api/v1/aqi/station/${id}/`,
  historicalAqi: `${API_BASE_URL}/api/v1/aqi/historical/`,
  predict:       `${API_BASE_URL}/api/v1/ml/predict/`,
  modelMetrics:  `${API_BASE_URL}/api/v1/ml/models/`,
  mapLayers:     `${API_BASE_URL}/api/v1/gis/map-layers/`,
  hotspots:      `${API_BASE_URL}/api/v1/gis/hotspots/`,
  alerts:        `${API_BASE_URL}/api/v1/alerts/`,
};

export const MUMBAI_MAP_CENTER = {
  latitude: 19.0760,
  longitude: 72.8777,
  latitudeDelta: 0.45,
  longitudeDelta: 0.40,
};

// Official CPCB Breakpoint Color System (Refined for contrast & restraint)
export const CPCB_COLORS = {
  Good:         '#15803d', // Forest Green
  Satisfactory: '#65a30d', // Olive Green
  Moderate:     '#d97706', // Rich Amber
  Poor:         '#ea580c', // Dark Orange
  'Very Poor':  '#dc2626', // Crimson Red
  Severe:       '#991b1b', // Deep Burgundy
};

// Human-Designed SaaS Design Tokens (Restrained, functional, professional)
export const THEME = {
  bg:            '#090d16', // Deep neutral obsidian
  surface:       '#111827', // Crisp card surface
  surfaceElevated: '#1a2234',
  border:        '#1f293d', // Subtle divider
  borderLight:   '#2d3748',
  primary:       '#0284c7', // Slate cyan
  primaryLight:  '#38bdf8',
  textPrimary:   '#f8fafc', // High-contrast primary
  textSecondary: '#94a3b8', // Muted reading secondary
  textMuted:     '#64748b', // Captions and timestamps
  success:       '#10b981',
  warning:       '#f59e0b',
  error:         '#ef4444',
  radiusSm:      8,
  radiusMd:      12,
  radiusLg:      16,
};
