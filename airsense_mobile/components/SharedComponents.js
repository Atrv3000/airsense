/**
 * Shared reusable UI components for AirSense mobile app.
 */
import React from 'react';
import {
  View, Text, StyleSheet, ActivityIndicator,
  TouchableOpacity, ScrollView
} from 'react-native';
import { THEME, CPCB_COLORS } from '../config';

// --- Loading Spinner ---
export function LoadingCard() {
  return (
    <View style={styles.centered}>
      <ActivityIndicator size="large" color={THEME.primary} />
      <Text style={styles.loadingText}>Loading live data…</Text>
    </View>
  );
}

// --- Error Card ---
export function ErrorCard({ message, onRetry }) {
  return (
    <View style={styles.errorCard}>
      <Text style={styles.errorIcon}>⚠️</Text>
      <Text style={styles.errorTitle}>Connection Error</Text>
      <Text style={styles.errorMsg}>{message}</Text>
      <Text style={styles.errorHint}>Make sure the Django backend is running and reachable.</Text>
      {onRetry && (
        <TouchableOpacity style={styles.retryBtn} onPress={onRetry}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// --- Section Header ---
export function SectionHeader({ title, subtitle }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle && <Text style={styles.sectionSubtitle}>{subtitle}</Text>}
    </View>
  );
}

// --- AQI Badge ---
export function AQIBadge({ aqi, category, size = 'md' }) {
  const color = getAQIColor(category);
  const isLarge = size === 'lg';
  return (
    <View style={[styles.aqiBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.aqiNum, { color, fontSize: isLarge ? 42 : 28 }]}>
        {aqi !== null && aqi !== undefined ? Math.round(aqi) : '--'}
      </Text>
      <Text style={[styles.aqiCat, { color, fontSize: isLarge ? 13 : 11 }]}>
        {category || 'Unknown'}
      </Text>
    </View>
  );
}

// --- Metric Pill (single pollutant card) ---
export function MetricPill({ label, value, unit, color }) {
  return (
    <View style={styles.metricPill}>
      <Text style={[styles.metricLabel, { color: color || THEME.textSecondary }]}>{label}</Text>
      <Text style={styles.metricValue}>
        {value !== null && value !== undefined ? Number(value).toFixed(1) : '--'}
      </Text>
      <Text style={styles.metricUnit}>{unit}</Text>
    </View>
  );
}

// --- Station Row Card ---
export function StationCard({ name, aqi, category, zone, onPress }) {
  const color = getAQIColor(category);
  return (
    <TouchableOpacity style={styles.stationCard} onPress={onPress} activeOpacity={0.8}>
      <View style={[styles.stationDot, { backgroundColor: color }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.stationName} numberOfLines={1}>{name}</Text>
        <Text style={[styles.stationZone, { color: THEME.textMuted }]}>{zone}</Text>
      </View>
      <View style={[styles.stationBadge, { borderColor: color }]}>
        <Text style={[styles.stationAQI, { color }]}>{aqi !== null ? Math.round(aqi) : '--'}</Text>
        <Text style={[styles.stationCat, { color }]}>{category?.split(' ')[0] || '--'}</Text>
      </View>
    </TouchableOpacity>
  );
}

// --- Divider ---
export function Divider() {
  return <View style={styles.divider} />;
}

// Utility
export function getAQIColor(category) {
  if (!category) return '#94a3b8';
  for (const [key, val] of Object.entries(CPCB_COLORS)) {
    if (category.toLowerCase().includes(key.toLowerCase())) return val;
  }
  return '#94a3b8';
}

export function getHealthAdvice(category) {
  const map = {
    good:         'Air quality is satisfactory. Outdoor activities are safe for everyone.',
    satisfactory: 'Acceptable air quality. Unusually sensitive individuals may experience discomfort.',
    moderate:     'Sensitive groups (elderly, children, asthmatics) should reduce prolonged outdoor activities.',
    poor:         'Avoid outdoor physical exertion. Wear N95 masks outdoors.',
    'very poor':  'Health alert! Everyone should avoid outdoor activities. Keep windows closed.',
    severe:       '🚨 Emergency conditions! Remain indoors. Wear mask even indoors near windows.',
  };
  const key = (category || '').toLowerCase().split(' (')[0];
  for (const [k, v] of Object.entries(map)) {
    if (key.includes(k)) return v;
  }
  return 'Data unavailable. Please check back shortly.';
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    gap: 12,
  },
  loadingText: {
    color: THEME.textSecondary,
    fontSize: 14,
  },
  errorCard: {
    backgroundColor: THEME.surface,
    margin: 20,
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: THEME.error + '44',
    gap: 8,
  },
  errorIcon:  { fontSize: 36 },
  errorTitle: { color: THEME.error, fontWeight: '700', fontSize: 16 },
  errorMsg:   { color: THEME.textSecondary, fontSize: 13, textAlign: 'center' },
  errorHint:  { color: THEME.textMuted, fontSize: 11, textAlign: 'center' },
  retryBtn: {
    marginTop: 8,
    backgroundColor: THEME.primaryDark,
    paddingHorizontal: 28,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryText: { color: '#fff', fontWeight: '700' },
  sectionHeader: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 8 },
  sectionTitle:  { color: THEME.textPrimary, fontSize: 17, fontWeight: '700', letterSpacing: -0.3 },
  sectionSubtitle: { color: THEME.textSecondary, fontSize: 12, marginTop: 2 },
  aqiBadge: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 16,
    borderWidth: 2,
    padding: 20,
  },
  aqiNum: { fontWeight: '800', letterSpacing: -1 },
  aqiCat: { fontWeight: '600', marginTop: 2 },
  metricPill: {
    backgroundColor: THEME.surface,
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: THEME.border,
    flex: 1,
  },
  metricLabel: { fontSize: 11, fontWeight: '600', marginBottom: 4, textTransform: 'uppercase' },
  metricValue: { color: THEME.textPrimary, fontSize: 20, fontWeight: '800' },
  metricUnit:  { color: THEME.textMuted, fontSize: 10, marginTop: 2 },
  stationCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 20,
    marginBottom: 8,
    borderRadius: 14,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  stationDot:   { width: 10, height: 10, borderRadius: 5 },
  stationName:  { color: THEME.textPrimary, fontWeight: '600', fontSize: 14 },
  stationZone:  { fontSize: 11, marginTop: 2 },
  stationBadge: {
    alignItems: 'flex-end',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  stationAQI:  { fontSize: 18, fontWeight: '800' },
  stationCat:  { fontSize: 9, fontWeight: '600' },
  divider:     { height: 1, backgroundColor: THEME.border, marginVertical: 8 },
});
