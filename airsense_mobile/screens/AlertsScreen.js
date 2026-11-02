/**
 * Tab 4: Health Advisories & Active Alerts Screen
 * Built as an operational public health guidance system:
 * Active station alerts (measured & forecast), CPCB classification matrix,
 * activity restrictions, and emergency protocols without emojis or NaN states.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFetch } from '../hooks/useFetch';
import { LoadingCard, ErrorCard, ErrorBanner, SectionHeader, getAQIColor } from '../components/SharedComponents';
import { ENDPOINTS, THEME, CPCB_COLORS, TYPOGRAPHY, SPACING } from '../config';

const CPCB_TIERS = [
  {
    category: 'Good',
    range: '0–50',
    color: CPCB_COLORS.Good,
    summary: 'Minimal impact on health.',
    general: 'Outdoor activities normal.',
    sensitive: 'No preventative precautions required.',
  },
  {
    category: 'Satisfactory',
    range: '51–100',
    color: CPCB_COLORS.Satisfactory,
    summary: 'Minor breathing discomfort to sensitive people.',
    general: 'Acceptable atmospheric conditions for standard outdoor work.',
    sensitive: 'Sensitive individuals should monitor prolonged exertion.',
  },
  {
    category: 'Moderate',
    range: '101–200',
    color: CPCB_COLORS.Moderate,
    summary: 'Breathing discomfort to people with asthma, heart disease.',
    general: 'Normal activity acceptable; consider reducing strenuous sports.',
    sensitive: 'Wear simple masks and avoid peak evening outdoor rush.',
  },
  {
    category: 'Poor',
    range: '201–300',
    color: CPCB_COLORS.Poor,
    summary: 'Breathing discomfort on prolonged exposure.',
    general: 'N95 filtration masks recommended during commute.',
    sensitive: 'Avoid prolonged outdoor exertion; keep indoor windows closed.',
  },
  {
    category: 'Very Poor',
    range: '301–400',
    color: CPCB_COLORS['Very Poor'],
    summary: 'Respiratory illness on prolonged exposure.',
    general: 'Avoid heavy outdoor exertion; run indoor HEPA purifiers.',
    sensitive: 'Remain indoors; keep emergency bronchodilators accessible.',
  },
  {
    category: 'Severe',
    range: '401–500',
    color: CPCB_COLORS.Severe,
    summary: 'Affects healthy people and severely impacts those with disease.',
    general: 'Emergency protocol: restrict all non-essential outdoor transit.',
    sensitive: 'Strict indoor stay; use sealed rooms with active air cleaners.',
  },
];

const PRECAUTIONARY_PROTOCOLS = [
  {
    title: 'High-Efficiency Particulate Air (HEPA)',
    description: 'Indoor air purifiers with true HEPA filters capture 99.97% of airborne PM2.5 particles down to 0.3 microns.',
  },
  {
    title: 'N95 Respirator Usage',
    description: 'Standard cloth masks provide less than 30% filtration against fine particulates. Certified N95/FFP2 masks are required during Poor or Severe intervals.',
  },
  {
    title: 'Morning Ventilation Windows',
    description: 'Pollution levels typically concentrate overnight and peak around morning rush hours (7 AM–10 AM). Schedule physical exercise or ventilation during early afternoons when convection lifts ground particulates.',
  },
  {
    title: 'Urban Microclimate Selection',
    description: 'Areas within 200 meters of arterial traffic corridors experience up to 3x higher ultrafine black carbon and nitrogen dioxide concentrations compared to residential interior roads.',
  },
];

export default function AlertsScreen() {
  const insets = useSafeAreaInsets();
  const liveAqi = useFetch(ENDPOINTS.liveAqi);
  const alertsFetch = useFetch(ENDPOINTS.alerts);
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([liveAqi.refetch(), alertsFetch.refetch()]);
    setRefreshing(false);
  };

  const cityAQI = liveAqi.data?.city_average_aqi;
  const hasValidCityAqi = cityAQI !== null && cityAQI !== undefined && !isNaN(cityAQI);
  const cityCat = liveAqi.data?.city_category;
  const cityColor = getAQIColor(cityCat);

  const activeAlerts = alertsFetch.data?.alerts || [];

  return (
    <View style={styles.container}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={THEME.primaryLight}
            colors={[THEME.primary]}
          />
        }
      >
        {/* Header Title */}
        <View style={[styles.headerBar, { paddingTop: Math.max(16, insets.top) }]}>
          <Text style={styles.headerSubtitle}>Public Health Guidelines</Text>
          <Text style={styles.headerTitle}>Advisories & Protocols</Text>
        </View>

        {/* Failed background refresh notification */}
        {(liveAqi.error || alertsFetch.error) && (liveAqi.data || alertsFetch.data) && (
          <ErrorBanner message={liveAqi.error || alertsFetch.error} onRetry={onRefresh} />
        )}

        {/* Current City Status Card */}
        <View style={[styles.statusCard, { borderLeftColor: cityColor }]}>
          <View style={styles.statusHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.statusLabel}>Current Ambient Tier</Text>
              <Text style={styles.statusCategory}>
                {cityCat || (liveAqi.loading ? 'Assessing...' : (liveAqi.error ? 'Unavailable' : 'Observation Pending'))}
              </Text>
            </View>
            <View style={styles.statusScoreWrap}>
              <Text style={[styles.statusScore, { color: cityColor }]}>
                {hasValidCityAqi ? Math.round(cityAQI) : '--'}
              </Text>
              <Text style={styles.statusScoreLabel}>AQI</Text>
            </View>
          </View>
          <Text style={styles.statusExplanation}>
            Mean of active monitoring station AQIs across Greater Mumbai based on Central Pollution Control Board (CPCB) NAQI guidelines.
          </Text>
        </View>

        {/* Active Emergency & Forecast Alerts */}
        <SectionHeader
          title="Active Hotspot Alerts"
          subtitle="Real-time threshold exceedances (AQI ≥ 201) and predictive warnings"
        />
        {alertsFetch.loading ? (
          <LoadingCard message="Checking active sensor warnings..." />
        ) : alertsFetch.error ? (
          <ErrorCard message={alertsFetch.error} onRetry={alertsFetch.refetch} />
        ) : activeAlerts.length > 0 ? (
          activeAlerts.map((alert) => {
            const isForecast = alert.is_forecast_alert;
            const aqiVal = alert.aqi_value ?? alert.actual_aqi;
            const alertColor = (aqiVal != null && aqiVal >= 301) ? CPCB_COLORS['Very Poor'] : CPCB_COLORS.Poor;

            return (
              <View key={alert.id} style={[styles.alertNotificationCard, { borderLeftColor: alertColor }]}>
                <View style={styles.alertHeaderRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.alertStationName} numberOfLines={1}>{alert.station_name || alert.station_code || alert.station_id}</Text>
                    <Text style={styles.alertTypeTag}>
                      {isForecast ? `Forecast Warning (+${alert.forecast_horizon_hours}h Horizon)` : 'Active Observed Exceedance'}
                    </Text>
                  </View>
                  <View style={[styles.alertScoreBadge, { backgroundColor: alertColor }]}>
                    <Text style={styles.alertScoreText}>
                      AQI {aqiVal != null ? Math.round(aqiVal) : '--'}
                    </Text>
                  </View>
                </View>
                <Text style={styles.alertMessage}>{alert.message}</Text>
              </View>
            );
          })
        ) : (
          <View style={styles.allClearCard}>
            <Ionicons name="checkmark-circle-outline" size={20} color={THEME.success} />
            <Text style={styles.allClearText}>
              All active monitoring stations currently below Poor hotspot threshold (AQI &lt; 201).
            </Text>
          </View>
        )}

        {/* CPCB Health Severity Matrix */}
        <SectionHeader
          title="NAQI Classification Matrix"
          subtitle="Official regulatory thresholds and public advisories"
        />
        {CPCB_TIERS.map((tier) => (
          <View key={tier.category} style={styles.tierCard}>
            <View style={styles.tierHeader}>
              <View style={[styles.tierColorBar, { backgroundColor: tier.color }]} />
              <Text style={styles.tierTitle}>{tier.category}</Text>
              <Text style={styles.tierRange}>AQI {tier.range}</Text>
            </View>
            <Text style={styles.tierSummary}>{tier.summary}</Text>
            <View style={styles.tierGroupGrid}>
              <View style={styles.tierGroup}>
                <Text style={styles.tierGroupLabel}>General Public</Text>
                <Text style={styles.tierGroupText}>{tier.general}</Text>
              </View>
              <View style={styles.tierGroup}>
                <Text style={styles.tierGroupLabel}>Sensitive Individuals</Text>
                <Text style={styles.tierGroupText}>{tier.sensitive}</Text>
              </View>
            </View>
          </View>
        ))}

        {/* Regulatory & Safety Protocols */}
        <SectionHeader
          title="Protective Interventions"
          subtitle="Standard operational recommendations for urban populations"
        />
        {PRECAUTIONARY_PROTOCOLS.map((p, idx) => (
          <View key={idx} style={styles.protocolCard}>
            <View style={styles.protocolHeader}>
              <Ionicons name="shield-checkmark-outline" size={16} color={THEME.primaryLight} />
              <Text style={styles.protocolTitle}>{p.title}</Text>
            </View>
            <Text style={styles.protocolDesc}>{p.description}</Text>
          </View>
        ))}

        {/* Public Health Disclaimer */}
        <View style={styles.disclaimerCard}>
          <Ionicons name="information-circle-outline" size={16} color={THEME.textMuted} />
          <Text style={styles.disclaimerText}>
            Public Health Notice: Guidance is based on Central Pollution Control Board (CPCB) NAQI and WHO environmental health criteria. AirSense provides environmental risk indications, not clinical medical advice or individual diagnoses.
          </Text>
        </View>

        <View style={{ height: 32 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.bg,
  },
  headerBar: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 6,
  },
  headerSubtitle: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.pageSubtitle,
  },
  headerTitle: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.pageTitle,
    marginTop: 2,
  },
  statusCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginTop: 10,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 16,
    borderWidth: 1,
    borderColor: THEME.border,
    borderLeftWidth: 4,
    gap: 8,
  },
  statusHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  statusLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  statusCategory: {
    color: THEME.textPrimary,
    fontSize: 18,
    fontWeight: '800',
    marginTop: 2,
  },
  statusScoreWrap: {
    alignItems: 'flex-end',
  },
  statusScore: {
    ...TYPOGRAPHY.statAqi,
  },
  statusScoreLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  statusExplanation: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.bodySecondary,
  },
  alertNotificationCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 10,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    borderLeftWidth: 4,
    gap: 8,
  },
  alertHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  alertStationName: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
  },
  alertTypeTag: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
    marginTop: 2,
  },
  alertScoreBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: THEME.radiusXs,
  },
  alertScoreText: {
    color: '#ffffff',
    ...TYPOGRAPHY.badge,
  },
  alertMessage: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.bodySecondary,
  },
  allClearCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  allClearText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.bodySecondary,
    flex: 1,
  },
  tierCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    gap: 6,
  },
  tierHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  tierColorBar: {
    width: 3,
    height: 16,
    borderRadius: THEME.radiusXs,
  },
  tierTitle: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
    flex: 1,
  },
  tierRange: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.captionBold,
  },
  tierSummary: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.bodySecondary,
  },
  tierGroupGrid: {
    marginTop: 6,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    gap: 6,
  },
  tierGroup: {
    gap: 2,
  },
  tierGroupLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  tierGroupText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.bodySecondary,
  },
  protocolCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    gap: 6,
  },
  protocolHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  protocolTitle: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
  },
  protocolDesc: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.body,
  },
  disclaimerCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginHorizontal: 16,
    marginTop: 12,
    padding: 12,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  disclaimerText: {
    flex: 1,
    color: THEME.textMuted,
    fontSize: 10,
    lineHeight: 14,
  },
});
