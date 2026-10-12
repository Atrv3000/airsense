// Central API configuration for the AirSense backend
// 10.0.2.2 is the Expo Go / Android emulator alias for your computer's localhost
// Change this to your computer's actual LAN IP when testing on a real phone
// e.g., 'http://192.168.1.5:8000'

export const API_BASE_URL = 'http://10.0.2.2:8000';

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

export const CPCB_COLORS = {
  Good:         '#00B050',
  Satisfactory: '#92D050',
  Moderate:     '#FFFF00',
  Poor:         '#FF9900',
  'Very Poor':  '#FF0000',
  Severe:       '#C00000',
};

export const THEME = {
  bg:           '#0f172a',
  surface:      '#1e293b',
  surfaceAlt:   '#162032',
  border:       '#334155',
  primary:      '#38bdf8',
  primaryDark:  '#0284c7',
  textPrimary:  '#f8fafc',
  textSecondary:'#94a3b8',
  textMuted:    '#64748b',
  accent:       '#818cf8',
  error:        '#f87171',
  success:      '#34d399',
  warning:      '#fbbf24',
};
