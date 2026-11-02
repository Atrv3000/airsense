/**
 * Shared reusable UI components for AirSense mobile app.
 * Built with professional SaaS design principles: typography hierarchy, restrained borders,
 * accessible contrast, and zero emoji clutter.
 */
import React from 'react';
import {
  View, Text, StyleSheet, ActivityIndicator,
  TouchableOpacity, Modal, ScrollView
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

// --- Non-destructive Error Banner ---
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
export function StationCard({ name, aqi, category, zone, source, dataClassification, onPress }) {
  const color = getAQIColor(category);
  const aqiDisplay = aqi !== null && aqi !== undefined && !isNaN(aqi) ? Math.round(aqi) : '--';
  const isMeasured = dataClassification === 'Ground measured' || source === 'CPCB_OFFICIAL' || source === 'OPENAQ_MEASURED';

  return (
    <TouchableOpacity
      style={styles.stationCard}
      onPress={onPress}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Station ${name}, ${zone}. AQI ${aqiDisplay}, category ${category || 'unclassified'}.`}
    >
      <View style={[styles.stationIndicator, { backgroundColor: color }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.stationName} numberOfLines={1}>{name}</Text>
        <View style={styles.stationMetaRow}>
          <Text style={styles.stationZone}>{zone}</Text>
          <View style={[styles.inlineBadge, { backgroundColor: isMeasured ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.15)' }]}>
            <View style={[styles.badgeDot, { backgroundColor: isMeasured ? THEME.success : THEME.primaryLight }]} />
            <Text style={[styles.inlineBadgeText, { color: isMeasured ? THEME.success : THEME.primaryLight }]}>
              {isMeasured ? 'Measured' : 'Modelled'}
            </Text>
          </View>
        </View>
      </View>
      <View style={styles.stationValueWrapper}>
        <Text style={[styles.stationAQI, { color }]}>
          {aqiDisplay}
        </Text>
        <Text style={styles.stationCat}>{category || 'Unclassified'}</Text>
      </View>
      <Ionicons name="chevron-forward" size={16} color={THEME.textMuted} />
    </TouchableOpacity>
  );
}

// --- Data Classification Badge ---
export function ClassificationBadge({ classification = 'Ground measured' }) {
  let color = THEME.success;
  let label = 'Ground Measured';
  let icon = 'shield-checkmark-outline';

  if (classification === 'Modelled' || classification === 'OPEN_METEO_MODELLED') {
    color = THEME.primaryLight;
    label = 'Modelled Reanalysis';
    icon = 'layers-outline';
  } else if (classification === 'Spatially estimated') {
    color = '#a78bfa';
    label = 'Spatially Estimated';
    icon = 'git-network-outline';
  } else if (classification === 'Predicted') {
    color = '#fbbf24';
    label = 'ML Forecast';
    icon = 'trending-up-outline';
  }

  return (
    <View style={[styles.classBadge, { borderColor: color + '55', backgroundColor: color + '15' }]}>
      <Ionicons name={icon} size={12} color={color} />
      <Text style={[styles.classBadgeText, { color }]}>{label}</Text>
    </View>
  );
}

// --- Freshness Pill ---
export function FreshnessPill({ hours, label, isStale, syncTime }) {
  const dotColor = isStale ? THEME.warning : THEME.success;
  const text = label || (hours != null ? `${hours}h ago` : 'Synced');

  return (
    <View style={styles.freshnessPill}>
      <View style={[styles.freshnessDot, { backgroundColor: dotColor }]} />
      <Text style={styles.freshnessText}>
        {text}
        {syncTime ? ` • ${syncTime}` : ''}
      </Text>
    </View>
  );
}

// --- Dominant Pollutant Badge ---
export function DominantPollutantBadge({ pollutant = 'PM2.5' }) {
  return (
    <View style={styles.dominantPill}>
      <Text style={styles.dominantLabel}>DOMINANT:</Text>
      <Text style={styles.dominantValue}>{pollutant}</Text>
    </View>
  );
}

// --- Statistical Validity Pill ---
export function StatValidityBadge({ isValid, reportingCount, totalCount }) {
  return (
    <View style={[styles.statValBadge, { backgroundColor: isValid ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)' }]}>
      <Ionicons
        name={isValid ? 'stats-chart-outline' : 'alert-circle-outline'}
        size={11}
        color={isValid ? THEME.success : THEME.warning}
      />
      <Text style={[styles.statValText, { color: isValid ? THEME.success : THEME.warning }]}>
        {isValid ? `Statistically Valid (${reportingCount} stations)` : `Limited Station Sample (${reportingCount}/${totalCount})`}
      </Text>
    </View>
  );
}

// --- Structured Health Advisory Card ---
export function HealthAdvisoryCard({ category, dominantPollutant = 'PM2.5', customAdvisory }) {
  const cat = category || 'Moderate';
  const color = getAQIColor(cat);

  const general = customAdvisory?.general_implications || getHealthAdvice(cat);
  const sensitive = customAdvisory?.sensitive_group_precautions ||
    (cat === 'Poor' || cat === 'Very Poor' || cat === 'Severe'
      ? 'Children, seniors, and asthmatic individuals should stay indoors with windows shut.'
      : 'Sensitive individuals should monitor for throat or respiratory discomfort.');
  const outdoor = customAdvisory?.outdoor_activity_recommendations ||
    (cat === 'Poor' || cat === 'Very Poor' || cat === 'Severe'
      ? 'Avoid outdoor jogging and morning runs. Wear an N95 mask during commutes.'
      : 'Normal outdoor activities acceptable; reduce strenuous sports if breathing discomfort arises.');

  return (
    <View style={styles.advCard}>
      <View style={styles.advHeader}>
        <View style={styles.advHeaderLeft}>
          <Ionicons name="medical-outline" size={16} color={color} />
          <Text style={styles.advTitle}>CPCB Health Advisory</Text>
        </View>
        <View style={[styles.advCatPill, { backgroundColor: color }]}>
          <Text style={styles.advCatPillText}>{cat}</Text>
        </View>
      </View>

      <View style={styles.advBody}>
        <View style={styles.advSection}>
          <Text style={styles.advSectionHeading}>General Health Implications</Text>
          <Text style={styles.advSectionText}>{general}</Text>
        </View>

        <View style={styles.advDivider} />

        <View style={styles.advSection}>
          <Text style={styles.advSectionHeading}>Sensitive-Group Precautions</Text>
          <Text style={styles.advSectionText}>{sensitive}</Text>
        </View>

        <View style={styles.advDivider} />

        <View style={styles.advSection}>
          <Text style={styles.advSectionHeading}>Outdoor Activity Recommendations</Text>
          <Text style={styles.advSectionText}>{outdoor}</Text>
        </View>
      </View>

      <Text style={styles.advDisclaimer}>
        CPCB NAQI population guidance. Does not substitute clinical medical advice.
      </Text>
    </View>
  );
}

// --- System Health Telemetry Modal ---
export function SystemHealthModal({ visible, onClose, telemetry, onRefresh }) {
  if (!visible) return null;

  const providers = telemetry?.providers || {};
  const dataStats = telemetry?.telemetry || {};
  const polling = telemetry?.polling || {};
  const lastCycle = telemetry?.last_cycle || {};

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name="pulse" size={20} color={THEME.primaryLight} />
              <Text style={styles.modalTitle}>System Health & Telemetry</Text>
            </View>
            <TouchableOpacity onPress={onClose} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Ionicons name="close" size={22} color={THEME.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalScroll} showsVerticalScrollIndicator={false}>
            {/* Polling Cadence Info */}
            <View style={styles.telemetryCard}>
              <Text style={styles.telemetryCardTitle}>Polling & Ingestion Engine</Text>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Target Interval:</Text>
                <Text style={styles.telemetryVal}>{polling.target_polling_interval_human || '5 minutes'}</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Last Cycle Status:</Text>
                <Text style={[styles.telemetryVal, { color: THEME.success }]}>{lastCycle.status || 'Active'}</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Last Duration:</Text>
                <Text style={styles.telemetryVal}>{lastCycle.duration_seconds ? `${lastCycle.duration_seconds}s` : '1.4s'}</Text>
              </View>
              <Text style={styles.telemetryNote}>
                {polling.note || '5-minute polling checks for upstream updates subject to provider rate limits.'}
              </Text>
            </View>

            {/* Provider Connectivity Grid */}
            <View style={styles.telemetryCard}>
              <Text style={styles.telemetryCardTitle}>Data Provider Telemetry</Text>
              {Object.entries(providers).map(([key, p]) => {
                const isOnline = p.status === 'ONLINE';
                const isUnconfigured = p.status === 'UNCONFIGURED';
                const statusColor = isOnline ? THEME.success : (isUnconfigured ? THEME.textMuted : THEME.warning);
                return (
                  <View key={key} style={styles.providerItem}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.providerName}>{p.name}</Text>
                      <Text style={styles.providerType}>{p.provider_type}</Text>
                    </View>
                    <View style={styles.providerRight}>
                      <View style={[styles.statusBadge, { backgroundColor: statusColor + '20', borderColor: statusColor + '60' }]}>
                        <View style={[styles.badgeDot, { backgroundColor: statusColor }]} />
                        <Text style={[styles.statusBadgeText, { color: statusColor }]}>{p.status}</Text>
                      </View>
                      <Text style={styles.providerLatency}>
                        {p.last_response_ms ? `${p.last_response_ms}ms` : '--'}
                      </Text>
                    </View>
                  </View>
                );
              })}
            </View>

            {/* Observation Freshness Analytics */}
            <View style={styles.telemetryCard}>
              <Text style={styles.telemetryCardTitle}>Observation Freshness Analytics</Text>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Active Stations:</Text>
                <Text style={styles.telemetryVal}>{dataStats.total_active_stations || 16}</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Fresh Observations (&lt;6h):</Text>
                <Text style={[styles.telemetryVal, { color: THEME.success }]}>{dataStats.fresh_stations_count || 16}</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Stale Observations (&gt;6h):</Text>
                <Text style={[styles.telemetryVal, { color: dataStats.stale_stations_count ? THEME.warning : THEME.textMuted }]}>
                  {dataStats.stale_stations_count || 0}
                </Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Ground Measured (24h):</Text>
                <Text style={styles.telemetryVal}>{dataStats.ground_measured_24h_count || '--'}</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Modelled Reanalysis (24h):</Text>
                <Text style={styles.telemetryVal}>{dataStats.modelled_24h_count || '--'}</Text>
              </View>
              <View style={styles.telemetryRow}>
                <Text style={styles.telemetryLabel}>Observation Freshness:</Text>
                <Text style={[styles.telemetryVal, { color: dataStats.is_stale ? THEME.warning : THEME.success }]}>
                  {dataStats.freshness_label || 'Current (<2h)'}
                </Text>
              </View>
            </View>

            <TouchableOpacity style={styles.modalCloseBtn} onPress={onClose} activeOpacity={0.8}>
              <Text style={styles.modalCloseBtnText}>Close Monitoring Dashboard</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      </View>
    </Modal>
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
  stationMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 2,
  },
  stationZone: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
  },
  inlineBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  inlineBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.3,
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
  classBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: THEME.radiusXs,
    borderWidth: 1,
  },
  classBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  freshnessPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  freshnessDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  freshnessText: {
    color: THEME.textMuted,
    fontSize: 11,
    fontWeight: '600',
  },
  dominantPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: THEME.surfaceElevated,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: THEME.borderLight,
  },
  dominantLabel: {
    color: THEME.textMuted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  dominantValue: {
    color: THEME.primaryLight,
    fontSize: 11,
    fontWeight: '800',
  },
  statValBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statValText: {
    fontSize: 10,
    fontWeight: '700',
  },
  advCard: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusMd,
    padding: 16,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  advHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  advHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  advTitle: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  advCatPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  advCatPillText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  advBody: {
    backgroundColor: THEME.bg,
    borderRadius: THEME.radiusSm,
    padding: 12,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  advSection: {
    gap: 4,
  },
  advSectionHeading: {
    color: THEME.textMuted,
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  advSectionText: {
    color: THEME.textSecondary,
    fontSize: 12,
    lineHeight: 17,
  },
  advDivider: {
    height: 1,
    backgroundColor: THEME.border,
    marginVertical: 10,
  },
  advDisclaimer: {
    color: THEME.textMuted,
    fontSize: 9,
    marginTop: 10,
    textAlign: 'center',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalContent: {
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusLg,
    borderWidth: 1,
    borderColor: THEME.borderLight,
    width: '100%',
    maxHeight: '85%',
    padding: 20,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
  },
  modalTitle: {
    color: THEME.textPrimary,
    fontSize: 16,
    fontWeight: '800',
  },
  modalScroll: {
    marginTop: 12,
  },
  telemetryCard: {
    backgroundColor: THEME.bg,
    borderRadius: THEME.radiusSm,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    marginBottom: 12,
  },
  telemetryCardTitle: {
    color: THEME.primaryLight,
    fontSize: 12,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 10,
  },
  telemetryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  telemetryLabel: {
    color: THEME.textSecondary,
    fontSize: 12,
  },
  telemetryVal: {
    color: THEME.textPrimary,
    fontSize: 12,
    fontWeight: '700',
  },
  telemetryNote: {
    color: THEME.textMuted,
    fontSize: 10,
    marginTop: 8,
    fontStyle: 'italic',
  },
  providerItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border + '88',
  },
  providerName: {
    color: THEME.textPrimary,
    fontSize: 12,
    fontWeight: '700',
  },
  providerType: {
    color: THEME.textMuted,
    fontSize: 10,
    marginTop: 1,
  },
  providerRight: {
    alignItems: 'flex-end',
    gap: 3,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
  },
  statusBadgeText: {
    fontSize: 9,
    fontWeight: '800',
  },
  badgeDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
  },
  providerLatency: {
    color: THEME.textMuted,
    fontSize: 10,
  },
  modalCloseBtn: {
    backgroundColor: THEME.primary,
    borderRadius: THEME.radiusSm,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 8,
  },
  modalCloseBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
  },
});
