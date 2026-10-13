/**
 * Shared reusable UI components for AirSense mobile app.
 * Built with professional SaaS design principles: typography hierarchy, restrained borders,
 * accessible contrast, and zero emoji clutter.
 */
import React from 'react';
import {
  View, Text, StyleSheet, ActivityIndicator,
  TouchableOpacity
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { THEME, CPCB_COLORS } from '../config';

// --- Loading State ---
export function LoadingCard({ message = 'Loading live data...' }) {
  return (
    <View style={styles.centered}>
      <ActivityIndicator size="small" color={THEME.primaryLight} />
      <Text style={styles.loadingText}>{message}</Text>
    </View>
  );
}

// --- Error State ---
export function ErrorCard({ message, onRetry }) {
  return (
    <View style={styles.errorCard}>
      <Ionicons name="alert-circle-outline" size={24} color={THEME.error} />
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={styles.errorTitle}>Unable to connect</Text>
        <Text style={styles.errorMsg}>{message}</Text>
        {onRetry && (
          <TouchableOpacity style={styles.retryBtn} onPress={onRetry} activeOpacity={0.7}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

// --- Clean Section Header ---
export function SectionHeader({ title, subtitle, rightElement }) {
  return (
    <View style={styles.sectionHeader}>
      <View style={{ flex: 1 }}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle && <Text style={styles.sectionSubtitle}>{subtitle}</Text>}
      </View>
      {rightElement}
    </View>
  );
}

// --- Refined Minimal AQI Gauge Badge ---
export function AQIBadge({ aqi, category, size = 'md' }) {
  const color = getAQIColor(category);
  const isLarge = size === 'lg';

  return (
    <View style={[
      styles.aqiBadge,
      { borderColor: color + '55', backgroundColor: color + '15' },
      isLarge && styles.aqiBadgeLarge
    ]}>
      <Text style={[styles.aqiNum, { color: '#ffffff', fontSize: isLarge ? 48 : 28 }]}>
        {aqi !== null && aqi !== undefined ? Math.round(aqi) : '--'}
      </Text>
      <View style={[styles.statusPill, { backgroundColor: color }]}>
        <Text style={styles.statusPillText}>
          {category || 'Unknown'}
        </Text>
      </View>
    </View>
  );
}

// --- Metric Card (Single Pollutant) ---
export function MetricPill({ label, value, unit, statusColor }) {
  return (
    <View style={styles.metricCard}>
      <View style={styles.metricHeader}>
        <Text style={styles.metricLabel}>{label}</Text>
        {statusColor && <View style={[styles.metricDot, { backgroundColor: statusColor }]} />}
      </View>
      <Text style={styles.metricValue}>
        {value !== null && value !== undefined ? Number(value).toFixed(1) : '--'}
      </Text>
      <Text style={styles.metricUnit}>{unit}</Text>
    </View>
  );
}

// --- Clean Station Row Card ---
export function StationCard({ name, aqi, category, zone, onPress }) {
  const color = getAQIColor(category);

  return (
    <TouchableOpacity
      style={styles.stationCard}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={[styles.stationIndicator, { backgroundColor: color }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.stationName} numberOfLines={1}>{name}</Text>
        <Text style={styles.stationZone}>{zone}</Text>
      </View>
      <View style={styles.stationValueWrapper}>
        <Text style={[styles.stationAQI, { color }]}>
          {aqi !== null ? Math.round(aqi) : '--'}
        </Text>
        <Text style={styles.stationCat}>{category?.split(' ')[0] || '--'}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={THEME.textMuted} />
    </TouchableOpacity>
  );
}

// --- Utility Helpers ---
export function getAQIColor(category) {
  if (!category) return THEME.textMuted;
  for (const [key, val] of Object.entries(CPCB_COLORS)) {
    if (category.toLowerCase().includes(key.toLowerCase())) return val;
  }
  return THEME.textMuted;
}

export function getHealthAdvice(category) {
  const map = {
    good:         'Air quality is satisfactory. Atmospheric conditions pose little or no health risk.',
    satisfactory: 'Air quality is acceptable. Minor breathing discomfort may occur for highly sensitive individuals.',
    moderate:     'Air quality is moderate. Children, elderly, and people with respiratory conditions should limit prolonged outdoor exertion.',
    poor:         'Breathing discomfort likely on prolonged exposure. Avoid strenuous outdoor activity and wear an N95 mask.',
    'very poor':  'Respiratory illness risk on prolonged exposure. Keep windows closed and operate indoor HEPA filtration.',
    severe:       'Emergency conditions. Healthy persons may experience significant respiratory discomfort. Remain indoors.',
  };
  const key = (category || '').toLowerCase().split(' (')[0];
  for (const [k, v] of Object.entries(map)) {
    if (key.includes(k)) return v;
  }
  return 'Real-time observation data currently unavailable. Please refresh shortly.';
}

const styles = StyleSheet.create({
  centered: {
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  loadingText: {
    color: THEME.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
  errorCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginVertical: 12,
    borderRadius: THEME.radiusMd,
    padding: 16,
    borderWidth: 1,
    borderColor: THEME.error + '44',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  errorTitle: {
    color: THEME.textPrimary,
    fontWeight: '600',
    fontSize: 14,
  },
  errorMsg: {
    color: THEME.textSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
  retryBtn: {
    alignSelf: 'flex-start',
    marginTop: 8,
    backgroundColor: THEME.surfaceElevated,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.borderLight,
  },
  retryText: {
    color: THEME.primaryLight,
    fontWeight: '600',
    fontSize: 12,
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 24,
    paddingBottom: 10,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    color: THEME.textPrimary,
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  sectionSubtitle: {
    color: THEME.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  aqiBadge: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: THEME.radiusLg,
    borderWidth: 1,
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  aqiBadgeLarge: {
    paddingVertical: 20,
    minWidth: 180,
  },
  aqiNum: {
    fontWeight: '800',
    letterSpacing: -1,
  },
  statusPill: {
    marginTop: 8,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 6,
  },
  statusPillText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  metricCard: {
    flex: 1,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  metricHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  metricLabel: {
    color: THEME.textMuted,
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metricDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  metricValue: {
    color: THEME.textPrimary,
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  metricUnit: {
    color: THEME.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  stationCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  stationIndicator: {
    width: 4,
    height: 32,
    borderRadius: 2,
  },
  stationName: {
    color: THEME.textPrimary,
    fontWeight: '600',
    fontSize: 14,
  },
  stationZone: {
    color: THEME.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  stationValueWrapper: {
    alignItems: 'flex-end',
    paddingRight: 4,
  },
  stationAQI: {
    fontSize: 17,
    fontWeight: '700',
  },
  stationCat: {
    fontSize: 10,
    color: THEME.textMuted,
    marginTop: 1,
  },
});
