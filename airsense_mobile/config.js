// Central API configuration and design system tokens for AirSense
import Constants from 'expo-constants';
import { Platform } from 'react-native';

function getApiBaseUrl() {
  const envUrl = process.env.EXPO_PUBLIC_API_URL;
  if (envUrl) {
    return envUrl.replace(/\/+$/, '');
  }

  // Support local development server resolution if running under Expo Go / local web
  const isDev = typeof __DEV__ !== 'undefined' ? __DEV__ : true;
  if (isDev) {
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
  }

  throw new Error(
    '[AirSense Configuration Error] Missing EXPO_PUBLIC_API_URL environment variable. ' +
    'Please set EXPO_PUBLIC_API_URL in your environment (e.g. EXPO_PUBLIC_API_URL=http://<host>:8000 or https://api.airsense.yourdomain.com).'
  );
}

export const API_BASE_URL = getApiBaseUrl();

export const HOTSPOT_THRESHOLD = 201.0;

export const ENDPOINTS = {
  health:               `${API_BASE_URL}/api/v1/health/`,
  healthTelemetry:      `${API_BASE_URL}/api/v1/health/telemetry/`,
  ingestionTelemetry:   `${API_BASE_URL}/api/v1/ingestion/telemetry/`,
  stations:             `${API_BASE_URL}/api/v1/stations/`,
  liveAqi:              `${API_BASE_URL}/api/v1/aqi/live/`,
  stationAqi:           (id) => `${API_BASE_URL}/api/v1/aqi/station/${id}/`,
  historicalAqi:        `${API_BASE_URL}/api/v1/aqi/historical/`,
  predict:              `${API_BASE_URL}/api/v1/ml/predict/`,
  modelMetrics:         `${API_BASE_URL}/api/v1/ml/models/`,
  forecastVerification: `${API_BASE_URL}/api/v1/ml/verification/`,
  mapLayers:            `${API_BASE_URL}/api/v1/gis/map-layers/`,
  hotspots:             `${API_BASE_URL}/api/v1/gis/hotspots/`,
  alerts:               `${API_BASE_URL}/api/v1/alerts/`,
  advisory:             `${API_BASE_URL}/api/v1/alerts/advisory/`,
  deviceToken:          `${API_BASE_URL}/api/v1/alerts/device-token/`,
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
  radiusXs:      4,
  radiusSm:      8,
  radiusMd:      12,
  radiusLg:      16,
  radiusFull:    9999,
};

// Standard 4/8-point spacing and dimensional scale
export const SPACING = {
  xxs:  2,
  xs:   4,
  sm:   8,
  md:   12,
  lg:   16,
  xl:   20,
  xxl:  24,
  xxxl: 32,
};

// Consistent typography scale and text hierarchy
export const TYPOGRAPHY = {
  // Display AQI Numbers
  heroAqi: {
    fontSize: 52,
    fontWeight: '800',
    letterSpacing: -1.5,
  },
  largeAqi: {
    fontSize: 44,
    fontWeight: '800',
    letterSpacing: -1,
  },
  statAqi: {
    fontSize: 28,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  cardAqi: {
    fontSize: 18,
    fontWeight: '800',
  },

  // Page & Section Headers
  pageTitle: {
    fontSize: 22,
    fontWeight: '800',
    letterSpacing: -0.4,
    lineHeight: 28,
  },
  pageSubtitle: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: -0.2,
    lineHeight: 20,
  },
  sectionSubtitle: {
    fontSize: 12,
    fontWeight: '400',
    lineHeight: 16,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 18,
  },

  // Body & Explanatory Copy
  body: {
    fontSize: 13,
    fontWeight: '400',
    lineHeight: 18,
  },
  bodyMedium: {
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 18,
  },
  bodySecondary: {
    fontSize: 12,
    fontWeight: '400',
    lineHeight: 17,
  },

  // Captions & Metadata (minimum 10px for mobile accessibility)
  caption: {
    fontSize: 11,
    fontWeight: '500',
    lineHeight: 15,
  },
  captionBold: {
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 15,
  },
  overline: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  badge: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  subBadge: {
    fontSize: 10,
    fontWeight: '600',
  },
};
