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
import { THEME, CPCB_COLORS, TYPOGRAPHY, SPACING } from '../config';

// --- Loading State ---
export function LoadingCard({ message = 'Connecting to telemetry feed...' }) {
  return (
    <View style={styles.centered} accessibilityRole="progressbar" accessibilityLabel={message}>
      <ActivityIndicator size="small" color={THEME.primaryLight} />
      <Text style={styles.loadingText}>{message}</Text>
    </View>
  );
}

// --- Error State ---
export function ErrorCard({ message, onRetry }) {
  return (
    <View style={styles.errorCard} accessibilityRole="alert">
      <Ionicons name="alert-circle-outline" size={24} color={THEME.error} />
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={styles.errorTitle}>Telemetry Offline</Text>
        <Text style={styles.errorMsg}>{message}</Text>
        {onRetry && (
          <TouchableOpacity
            style={styles.retryBtn}
            onPress={onRetry}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel="Retry telemetry connection"
          >
            <Text style={styles.retryText}>Retry Connection</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

// --- Non-destructive Error Banner (Preserves displayed data on failed refresh) ---
export function ErrorBanner({ message = 'Live sensor feed interrupted — tap to reconnect', onRetry }) {
  return (
    <View style={styles.errorBanner} accessibilityRole="alert">
      <Ionicons name="warning-outline" size={16} color={THEME.warning} />
      <Text style={styles.errorBannerText} numberOfLines={2}>{message}</Text>
      {onRetry && (
        <TouchableOpacity
          style={styles.errorBannerRetry}
          onPress={onRetry}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Reconnect live sensor feed"
        >
          <Text style={styles.errorBannerRetryText}>Reconnect</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// --- Empty State Card ---
export function EmptyCard({
  title = 'No Records Available',
  message = 'Sensor feeds have not reported data for this time period.',
  icon = 'file-tray-outline',
  actionLabel,
  onAction,
}) {
  return (
    <View style={styles.emptyCard} accessibilityRole="summary">
      <Ionicons name={icon} size={28} color={THEME.textMuted} />
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyDesc}>{message}</Text>
      {onAction && actionLabel && (
        <TouchableOpacity
          style={styles.emptyActionBtn}
          onPress={onAction}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel={actionLabel}
        >
          <Text style={styles.emptyActionText}>{actionLabel}</Text>
        </TouchableOpacity>
      )}
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
    <View
      style={[
        styles.aqiBadge,
        { borderColor: color + '55', backgroundColor: color + '15' },
        isLarge && styles.aqiBadgeLarge
      ]}
      accessibilityRole="text"
      accessibilityLabel={`Air Quality Index: ${aqi !== null && aqi !== undefined && !isNaN(aqi) ? Math.round(aqi) : 'unavailable'}, category ${category || 'unclassified'}`}
    >
      <Text style={[styles.aqiNum, { color: '#ffffff', fontSize: isLarge ? 48 : 28 }]}>
        {aqi !== null && aqi !== undefined && !isNaN(aqi) ? Math.round(aqi) : '--'}
      </Text>
      <View style={[styles.statusPill, { backgroundColor: color }]}>
        <Text style={styles.statusPillText}>
          {category || 'Unclassified'}
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
        {value !== null && value !== undefined && !isNaN(value) ? Number(value).toFixed(1) : '--'}
      </Text>
      <Text style={styles.metricUnit}>{unit}</Text>
    </View>
  );
}

// --- Clean Station Row Card ---
export function StationCard({ name, aqi, category, zone, onPress }) {
  const color = getAQIColor(category);
  const aqiDisplay = aqi !== null && aqi !== undefined && !isNaN(aqi) ? Math.round(aqi) : 'unavailable';

  return (
    <TouchableOpacity
      style={styles.stationCard}
      onPress={onPress}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Station ${name}, ${zone}. AQI ${aqiDisplay}, category ${category || 'unclassified'}. Tap to view telemetry.`}
    >
      <View style={[styles.stationIndicator, { backgroundColor: color }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.stationName} numberOfLines={1}>{name}</Text>
        <Text style={styles.stationZone}>{zone}</Text>
      </View>
      <View style={styles.stationValueWrapper}>
        <Text style={[styles.stationAQI, { color }]}>
          {aqi !== null && aqi !== undefined && !isNaN(aqi) ? Math.round(aqi) : '--'}
        </Text>
        <Text style={styles.stationCat}>{category || 'Unclassified'}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={THEME.textMuted} />
    </TouchableOpacity>
  );
}

// --- Utility Helpers ---
export function getAQIColor(category) {
  if (!category) return THEME.textMuted;
  const catLower = category.toLowerCase().trim();
  if (catLower.includes('very poor')) return CPCB_COLORS['Very Poor'];
  if (catLower.includes('poor')) return CPCB_COLORS.Poor;
  if (catLower.includes('severe')) return CPCB_COLORS.Severe;
  if (catLower.includes('moderate')) return CPCB_COLORS.Moderate;
  if (catLower.includes('satisfactory')) return CPCB_COLORS.Satisfactory;
  if (catLower.includes('good')) return CPCB_COLORS.Good;
  return THEME.textMuted;
}

export function getHealthAdvice(category) {
  if (!category) return 'Observation data currently unavailable. Please refresh shortly.';
  const catLower = category.toLowerCase().trim();
  if (catLower.includes('very poor')) {
    return 'Respiratory illness risk on prolonged exposure. Keep windows closed and operate indoor HEPA filtration.';
  }
  if (catLower.includes('poor')) {
    return 'Breathing discomfort likely on prolonged exposure. Avoid strenuous outdoor activity and wear an N95 mask.';
  }
  if (catLower.includes('severe')) {
    return 'Emergency conditions. Healthy persons may experience significant respiratory discomfort. Remain indoors.';
  }
  if (catLower.includes('moderate')) {
    return 'Air quality is moderate. Children, elderly, and people with respiratory conditions should limit prolonged outdoor exertion.';
  }
  if (catLower.includes('satisfactory')) {
    return 'Air quality is acceptable. Minor breathing discomfort may occur for highly sensitive individuals.';
  }
  if (catLower.includes('good')) {
    return 'Air quality is satisfactory. Atmospheric conditions pose little or no health risk.';
  }
  return 'Observation data currently unavailable. Please refresh shortly.';
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
    paddingVertical: 8,
    minHeight: 36,
    justifyContent: 'center',
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.borderLight,
  },
  retryText: {
    color: THEME.primaryLight,
    fontWeight: '600',
    fontSize: 12,
  },
  errorBanner: {
    marginHorizontal: 16,
    marginBottom: 10,
    backgroundColor: THEME.surfaceElevated,
    borderRadius: THEME.radiusSm,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: THEME.warning + '55',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  errorBannerText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.caption,
    flex: 1,
  },
  errorBannerRetry: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    minHeight: 32,
    justifyContent: 'center',
    borderRadius: THEME.radiusXs,
    backgroundColor: THEME.surface,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  errorBannerRetryText: {
    color: THEME.primaryLight,
    ...TYPOGRAPHY.subBadge,
  },
  emptyCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 10,
    borderRadius: THEME.radiusMd,
    padding: 24,
    borderWidth: 1,
    borderColor: THEME.border,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  emptyTitle: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
    marginTop: 6,
  },
  emptyDesc: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.bodySecondary,
    textAlign: 'center',
    maxWidth: 280,
  },
  emptyActionBtn: {
    marginTop: 10,
    backgroundColor: THEME.surfaceElevated,
    paddingHorizontal: 16,
    paddingVertical: 10,
    minHeight: 40,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  emptyActionText: {
    color: THEME.primaryLight,
    ...TYPOGRAPHY.bodySecondary,
    fontWeight: '600',
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 22,
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.sectionTitle,
  },
  sectionSubtitle: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.sectionSubtitle,
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
    paddingVertical: 4,
    borderRadius: THEME.radiusXs,
  },
  statusPillText: {
    color: '#ffffff',
    ...TYPOGRAPHY.badge,
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
    ...TYPOGRAPHY.overline,
  },
  metricDot: {
    width: 6,
    height: 6,
    borderRadius: THEME.radiusFull,
  },
  metricValue: {
    color: THEME.textPrimary,
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  metricUnit: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
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
    borderRadius: THEME.radiusXs,
  },
  stationName: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
  },
  stationZone: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
    marginTop: 2,
  },
  stationValueWrapper: {
    alignItems: 'flex-end',
    paddingRight: 4,
  },
  stationAQI: {
    ...TYPOGRAPHY.cardAqi,
  },
  stationCat: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.subBadge,
    marginTop: 1,
  },
});
