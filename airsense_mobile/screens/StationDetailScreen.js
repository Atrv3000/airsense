/**
 * StationDetailScreen.js
 * Shows granular continuous air quality & surface meteorology readings
 * for a specific monitoring station, plus 24h forecast and historical series.
 * Free of fake authority claims; honestly labels measured vs modelled feeds.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, StatusBar, RefreshControl, Dimensions
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFetch } from '../hooks/useFetch';
import {
  LoadingCard, ErrorCard, ErrorBanner, EmptyCard, SectionHeader,
  AQIBadge, MetricPill, getAQIColor, getHealthAdvice,
  ClassificationBadge, FreshnessPill
} from '../components/SharedComponents';
import { ENDPOINTS, THEME, TYPOGRAPHY, SPACING } from '../config';

const { width: SCREEN_W } = Dimensions.get('window');

export default function StationDetailScreen({ route, navigation }) {
  const insets = useSafeAreaInsets();
  const { station } = route.params || {};
  const stationId = station?.station_id_code || station?.station_id || station?.id || 'OPENAQ_6927';
  const stationName = station?.station_name || station?.name || stationId;

  const url = ENDPOINTS.stationAqi(stationId);
  const { data, loading, error, refetch } = useFetch(url);
  const forecastFetch = useFetch(`${ENDPOINTS.predict}?station_id=${stationId}&hours=24`);
  const historyFetch = useFetch(`${ENDPOINTS.historicalAqi}?station_id=${stationId}&limit=24`);

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([refetch(), forecastFetch.refetch(), historyFetch.refetch()]);
    setRefreshing(false);
  };

  // Support direct object returned by StationAQIDetailView or nested structures
  const current = data?.station_id_code ? data : (data?.current || station || {});
  const aqiVal = (current.overall_aqi !== null && current.overall_aqi !== undefined && !isNaN(current.overall_aqi))
    ? current.overall_aqi
    : null;
  const aqiCat = current.aqi_category || current.category || (aqiVal !== null ? 'Assessing' : 'Pending Observation');
  const aqiColor = getAQIColor(aqiCat);
  const healthMsg = getHealthAdvice(aqiCat);

  const isMeasured = current.source === 'OPENAQ_MEASURED' || current.source === 'CPCB_OFFICIAL';
  const sourceLabel = current.source === 'CPCB_OFFICIAL'
    ? 'Official CPCB CAAQMS'
    : (current.source === 'OPENAQ_MEASURED' ? 'OpenAQ Ground Station' : 'Open-Meteo Atmospheric Grid');
  const feedType = current.source === 'CPCB_OFFICIAL'
    ? 'Official Ground Sensor'
    : (isMeasured ? 'Measured Sensor' : 'Modelled Reanalysis');

  const forecasts = forecastFetch.data?.forecasts || [];
  const historyList = historyFetch.data?.history || [];

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={THEME.bg} />
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
        {/* Top Navigation Bar */}
        <View style={[styles.navBar, { paddingTop: Math.max(16, insets.top) }]}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => navigation.goBack()}
            activeOpacity={0.7}
          >
            <Ionicons name="arrow-back" size={18} color={THEME.textPrimary} />
            <Text style={styles.backBtnText}>Stations</Text>
          </TouchableOpacity>
          <View style={styles.stationBadgeWrap}>
            <Text style={styles.stationCode}>{stationId}</Text>
          </View>
        </View>

        {/* Station Title & Honest Source Designation */}
        <View style={styles.titleSection}>
          <Text style={styles.stationTitle}>{stationName}</Text>
          <View style={styles.badgeRow}>
            <ClassificationBadge classification={current.data_classification || (isMeasured ? 'Ground measured' : 'Modelled')} />
            <FreshnessPill isStale={current.is_stale} hours={current.freshness_hours} />
          </View>
          <View style={styles.sourcePillRow}>
            <View style={[styles.sourceDot, { backgroundColor: isMeasured ? THEME.success : THEME.primaryLight }]} />
            <Text style={styles.stationSubtitle}>{sourceLabel} ({current.provider || feedType})</Text>
          </View>
        </View>

        {loading && !refreshing && !data ? (
          <LoadingCard message="Retrieving telemetry records for this station..." />
        ) : error && !data ? (
          <ErrorCard message={error} onRetry={refetch} />
        ) : (
          <>
            {/* Failed background refresh banner */}
            {error && data && (
              <ErrorBanner message={error} onRetry={refetch} />
            )}
            {/* Live AQI Score Card */}
            <View style={styles.heroCard}>
              <AQIBadge aqi={aqiVal} category={aqiCat} size="lg" />
              <View style={styles.heroMeta}>
                <View style={styles.heroMetaItem}>
                  <Text style={styles.heroMetaLabel}>Prominent Pollutant</Text>
                  <Text style={styles.heroMetaVal}>{current.prominent_pollutant || 'None'}</Text>
                </View>
                <View style={styles.heroMetaDivider} />
                <View style={styles.heroMetaItem}>
                  <Text style={styles.heroMetaLabel}>Telemetry Feed</Text>
                  <Text style={styles.heroMetaVal}>{feedType}</Text>
                </View>
              </View>
            </View>

            {/* Health Advisory */}
            <View style={[styles.advisoryCard, { borderLeftColor: aqiColor }]}>
              <View style={styles.advisoryHeader}>
                <Ionicons name="shield-checkmark-outline" size={16} color={THEME.primaryLight} />
                <Text style={styles.advisoryTitle}>Health Advisory</Text>
              </View>
              <Text style={styles.advisoryText}>{healthMsg}</Text>
            </View>

            {/* Granular Pollutant Concentrations */}
            <SectionHeader
              title="Pollutant Concentrations"
              subtitle="Concentrations and parameters recorded for this station"
            />
            <View style={styles.metricsGrid}>
              <MetricPill label="PM2.5" value={current.raw_pm25 ?? current.pm25} unit="µg/m³" statusColor="#f87171" />
              <MetricPill label="PM10"  value={current.raw_pm10 ?? current.pm10} unit="µg/m³" statusColor="#fb923c" />
            </View>
            <View style={styles.metricsGrid}>
              <MetricPill label="NO₂"  value={current.raw_no2 ?? current.no2} unit="µg/m³" statusColor="#a78bfa" />
              <MetricPill label="SO₂"  value={current.raw_so2 ?? current.so2} unit="µg/m³" statusColor="#fbbf24" />
            </View>
            <View style={styles.metricsGrid}>
              <MetricPill label="CO"   value={current.raw_co ?? current.co}   unit="mg/m³" statusColor="#4ade80" />
              <MetricPill label="O₃"   value={current.raw_o3 ?? current.o3}   unit="µg/m³" statusColor="#38bdf8" />
            </View>

            {/* Surface Meteorology Conditions */}
            <SectionHeader
              title="Surface Meteorology"
              subtitle="Atmospheric conditions at station coordinates"
            />
            <View style={styles.weatherSummaryRow}>
              <View style={styles.weatherItem}>
                <Text style={styles.weatherLabel}>Temperature</Text>
                <Text style={styles.weatherValue}>
                  {current.temperature != null ? Number(current.temperature).toFixed(1) + ' °C' : '--'}
                </Text>
              </View>
              <View style={styles.weatherItemDivider} />
              <View style={styles.weatherItem}>
                <Text style={styles.weatherLabel}>Relative Humidity</Text>
                <Text style={styles.weatherValue}>
                  {current.humidity != null ? Number(current.humidity).toFixed(0) + ' %' : '--'}
                </Text>
              </View>
              <View style={styles.weatherItemDivider} />
              <View style={styles.weatherItem}>
                <Text style={styles.weatherLabel}>Wind Speed</Text>
                <Text style={styles.weatherValue}>
                  {current.wind_speed != null ? Number(current.wind_speed).toFixed(1) + ' km/h' : '--'}
                </Text>
              </View>
            </View>

            {/* 24-Hour Predictive Forecast Horizon */}
            <SectionHeader
              title="24-Hour Forecast"
              subtitle="Trained ML model projection with expected error bounds"
            />
            {forecastFetch.loading ? (
              <LoadingCard message="Loading 24-hour predictive horizon..." />
            ) : forecasts.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.forecastStrip}>
                {forecasts.map((fc, i) => {
                  const targetD = fc.target_timestamp ? new Date(fc.target_timestamp) : null;
                  const timeLabel = targetD
                    ? targetD.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
                    : `+${fc.step_ahead_hours}h`;
                  const low = fc.lower_bound ?? fc.confidence_lower ?? 0;
                  const high = fc.upper_bound ?? fc.confidence_upper ?? 0;

                  return (
                    <View key={i} style={[styles.forecastCard, { borderTopColor: fc.color_hex || THEME.primary, borderTopWidth: 3 }]}>
                      <Text style={styles.fcHour}>{timeLabel}</Text>
                      <Text style={[styles.fcAqi, { color: fc.color_hex || THEME.primaryLight }]}>
                        {Math.round(fc.predicted_aqi)}
                      </Text>
                      <Text style={styles.fcCat}>{fc.category || 'AQI'}</Text>
                      <Text style={styles.fcRange}>{Math.round(low)}–{Math.round(high)}</Text>
                    </View>
                  );
                })}
              </ScrollView>
            ) : (
              <EmptyCard
                title="Forecast Model Output Pending"
                message="Precomputed machine learning forecasts have not yet synced for this monitoring location."
                icon="trending-up-outline"
                actionLabel="Fetch Forecast"
                onAction={forecastFetch.refetch}
              />
            )}

            {/* Recent Observation History */}
            <SectionHeader
              title="Recent Observed History"
              subtitle="Latest validated measurements recorded"
            />
            {historyFetch.loading ? (
              <LoadingCard message="Retrieving station history..." />
            ) : historyList.length > 0 ? (
              <View style={styles.historyCard}>
                {historyList.slice(0, 8).map((rec, i) => {
                  const d = new Date(rec.recorded_at);
                  const timeStr = d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }) + ' ' +
                                  d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
                  const color = rec.color_hex || getAQIColor(rec.aqi_category);

                  return (
                    <View key={rec.id || i} style={[styles.historyRow, i > 0 && styles.historyRowBorder]}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.historyTime}>{timeStr}</Text>
                        <Text style={styles.historyPollutant}>
                          Prominent: {rec.prominent_pollutant || 'None'}
                        </Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={[styles.historyAqi, { color }]}>
                          {rec.overall_aqi != null ? Math.round(rec.overall_aqi) : '--'}
                        </Text>
                        <Text style={styles.historyCat}>{rec.aqi_category || '--'}</Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            ) : (
              <EmptyCard
                title="No Recent Station History"
                message="Continuous hourly sensor measurements have not been reported for this station within this time window."
                icon="time-outline"
                actionLabel="Reload Sensor History"
                onAction={historyFetch.refetch}
              />
            )}
          </>
        )}

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
  navBar: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingRight: 12,
    minHeight: 40,
    justifyContent: 'center',
  },
  backBtnText: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.bodyMedium,
  },
  stationBadgeWrap: {
    backgroundColor: THEME.surfaceElevated,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  stationCode: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.badge,
  },
  titleSection: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
  },
  stationTitle: {
    color: THEME.textPrimary,
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: -0.3,
    lineHeight: 26,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
    marginBottom: 4,
  },
  sourcePillRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
  },
  sourceDot: {
    width: 6,
    height: 6,
    borderRadius: THEME.radiusFull,
  },
  stationSubtitle: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.bodySecondary,
  },
  heroCard: {
    marginHorizontal: 16,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusLg,
    padding: 20,
    borderWidth: 1,
    borderColor: THEME.border,
    alignItems: 'center',
    gap: 16,
  },
  heroMeta: {
    flexDirection: 'row',
    width: '100%',
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
  },
  heroMetaItem: {
    flex: 1,
    alignItems: 'center',
    gap: 2,
  },
  heroMetaDivider: {
    width: 1,
    height: '70%',
    backgroundColor: THEME.border,
    alignSelf: 'center',
  },
  heroMetaLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  heroMetaVal: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
  },
  advisoryCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginTop: 10,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    borderLeftWidth: 4,
    gap: 6,
  },
  advisoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  advisoryTitle: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
  },
  advisoryText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.body,
  },
  metricsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 10,
  },
  weatherSummaryRow: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusMd,
    borderWidth: 1,
    borderColor: THEME.border,
    flexDirection: 'row',
    paddingVertical: 12,
  },
  weatherItem: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
  },
  weatherItemDivider: {
    width: 1,
    height: '60%',
    backgroundColor: THEME.border,
    alignSelf: 'center',
  },
  weatherLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  weatherValue: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.cardTitle,
  },
  forecastStrip: {
    paddingHorizontal: 16,
    gap: 8,
    paddingBottom: 8,
  },
  forecastCard: {
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusSm,
    padding: 12,
    alignItems: 'center',
    minWidth: 70,
    borderWidth: 1,
    borderColor: THEME.border,
    gap: 3,
  },
  fcHour: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  fcAqi: {
    fontSize: 16,
    fontWeight: '800',
  },
  fcCat: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.subBadge,
  },
  fcRange: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.subBadge,
  },
  historyCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    borderRadius: THEME.radiusMd,
    borderWidth: 1,
    borderColor: THEME.border,
    paddingHorizontal: 14,
    paddingVertical: 4,
  },
  historyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  historyRowBorder: {
    borderTopWidth: 1,
    borderTopColor: THEME.border,
  },
  historyTime: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.bodySecondary,
    fontWeight: '600',
  },
  historyPollutant: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
    marginTop: 2,
  },
  historyAqi: {
    ...TYPOGRAPHY.cardAqi,
  },
  historyCat: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.subBadge,
  },
  emptyCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    borderRadius: THEME.radiusMd,
    padding: 16,
    borderWidth: 1,
    borderColor: THEME.border,
    alignItems: 'center',
  },
  emptyText: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.bodySecondary,
  },
});
