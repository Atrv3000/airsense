/**
 * Tab 1: Home Dashboard Screen
 * Upgraded Environmental Intelligence Interface for Greater Mumbai:
 * - Large current AQI indicator & CPCB category
 * - Dominant pollutant indicator
 * - Data source classification badge (Ground Measured vs Modelled)
 * - Last updated timestamp & observation freshness indicator
 * - Monitoring station count & honest source attribution
 * - Mumbai regional average AQI with statistical validity badge
 * - 24-hour ML forecast horizon strip
 * - Hourly pollution trend chart
 * - Structured public health advisory (general, sensitive-group, outdoor activity)
 * - Operational System Health Telemetry modal
 * - Zero decorative emojis; standard Lucide/Ionicons only
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  RefreshControl, TouchableOpacity, StatusBar,
  Dimensions
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LineChart } from 'react-native-chart-kit';
import { useFetch } from '../hooks/useFetch';
import {
  LoadingCard, ErrorCard, ErrorBanner, EmptyCard, SectionHeader,
  AQIBadge, MetricPill, StationCard,
  ClassificationBadge, FreshnessPill, DominantPollutantBadge,
  StatValidityBadge, HealthAdvisoryCard, SystemHealthModal,
  getAQIColor, getHealthAdvice
} from '../components/SharedComponents';
import { ENDPOINTS, THEME, TYPOGRAPHY, SPACING, CPCB_COLORS } from '../config';

const { width: SCREEN_W } = Dimensions.get('window');
const CHART_WIDTH = SCREEN_W - 60;

const CHART_CONFIG = {
  backgroundGradientFrom: THEME.surface,
  backgroundGradientTo:   THEME.surface,
  color: (opacity = 1) => `rgba(2, 132, 199, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(148, 163, 184, ${opacity})`,
  propsForDots: { r: '3', strokeWidth: '1.5', stroke: THEME.primaryLight },
  propsForBackgroundLines: { stroke: THEME.border, strokeDasharray: '4' },
  decimalPlaces: 0,
  strokeWidth: 2,
};

export default function HomeScreen({ navigation }) {
  const [refreshing, setRefreshing] = useState(false);
  const [healthModalVisible, setHealthModalVisible] = useState(false);

  // Core telemetry & data queries
  const { data, loading, error, refetch } = useFetch(ENDPOINTS.liveAqi);
  const telemetryFetch = useFetch(ENDPOINTS.healthTelemetry);
  const forecastFetch = useFetch(`${ENDPOINTS.predict}?hours=24`);
  const historyFetch = useFetch(`${ENDPOINTS.historicalAqi}?limit=12`);

  // Minute-interval clock state
  const [currentTime, setCurrentTime] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const formattedDate = currentTime.toLocaleDateString('en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  const formattedClock = currentTime.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      refetch(),
      telemetryFetch.refetch(),
      forecastFetch.refetch(),
      historyFetch.refetch()
    ]);
    setRefreshing(false);
  };

  if (loading && !refreshing && !data) return <LoadingCard message="Retrieving real-time telemetry across Greater Mumbai..." />;
  if (error && !data) return <ErrorCard message={error} onRetry={refetch} />;
  if (!data && !loading && !error) {
    return (
      <View style={styles.container}>
        <EmptyCard
          title="No Air Quality Readings"
          message="No monitoring stations are currently reporting ambient AQI in Greater Mumbai."
          actionLabel="Reconnect Telemetry"
          onAction={refetch}
        />
      </View>
    );
  }

  const cityAQI = data.city_average_aqi;
  const isStatValid = data.is_statistically_valid !== false;
  const cityCat = data.city_category || 'Moderate';
  const cityColor = getAQIColor(cityCat);
  const stations = data.stations || [];
  const worst = data.worst_location;
  const cleanest = data.cleanest_location;
  const dominantPollutant = data.dominant_pollutant || 'PM2.5';
  const monitoredCount = data.monitored_stations_count || stations.length;
  const groundMeasuredCount = data.ground_measured_stations_count || 0;
  const freshnessInfo = data.freshness || {};

  // Primary ground vs modelled source attribution
  const primaryClassification = groundMeasuredCount > 0 ? "Ground measured" : "Modelled";

  // Citywide mean concentrations across all active stations or fallback
  const cityP = data.city_pollutants || {};
  const fallbackStation = stations.find(s => s.raw_pm25 != null && s.raw_pm10 != null) || worst || stations[0];
  const pollutants = {
    pm25: cityP.pm25 ?? fallbackStation?.raw_pm25,
    pm10: cityP.pm10 ?? fallbackStation?.raw_pm10,
    no2:  cityP.no2  ?? fallbackStation?.raw_no2,
    so2:  cityP.so2  ?? fallbackStation?.raw_so2,
    co:   cityP.co   ?? fallbackStation?.raw_co,
    o3:   cityP.o3   ?? fallbackStation?.raw_o3,
    temperature: cityP.temperature ?? fallbackStation?.temperature,
    humidity:    cityP.humidity    ?? fallbackStation?.humidity,
    wind_speed:  cityP.wind_speed  ?? fallbackStation?.wind_speed,
  };

  // Station sensor observation timestamp
  const observedTime = data.last_updated_at ? new Date(data.last_updated_at).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }) : (fallbackStation?.recorded_at ? new Date(fallbackStation.recorded_at).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }) : null);

  // 24-hour forecast strip items
  const forecasts = forecastFetch.data?.forecasts || [];

  // Hourly trend line chart items (past 8-12 hours)
  const historyRecords = historyFetch.data?.history?.filter(r => r.overall_aqi != null) || [];
  const sampledHistory = historyRecords.length > 7
    ? historyRecords.filter((_, i) => i % Math.max(1, Math.floor(historyRecords.length / 6)) === 0 || i === historyRecords.length - 1).slice(0, 7)
    : historyRecords;

  const trendChartData = sampledHistory.length > 1 ? {
    labels: sampledHistory.map(r => {
      const d = new Date(r.recorded_at);
      return `${d.getHours()}:00`;
    }),
    datasets: [{ data: sampledHistory.map(r => Math.round(r.overall_aqi)), strokeWidth: 2 }]
  } : null;

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
        {/* Top App Header with Real Date & System Health Button */}
        <View style={styles.headerBar}>
          <View>
            <Text style={styles.headerSubtitle}>{formattedDate}</Text>
            <Text style={styles.headerTitle}>Greater Mumbai</Text>
          </View>
          <View style={styles.headerActions}>
            <TouchableOpacity
              style={styles.healthStatusBtn}
              onPress={() => setHealthModalVisible(true)}
              activeOpacity={0.7}
              accessibilityRole="button"
              accessibilityLabel="Open System Health Monitoring"
            >
              <View style={styles.liveDot} />
              <Ionicons name="pulse" size={13} color={THEME.primaryLight} />
              <Text style={styles.healthStatusText}>System Health</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Failed background refresh notification without wiping visible UI */}
        {error && data && (
          <ErrorBanner message={error} onRetry={refetch} />
        )}

        {/* Primary Environmental Intelligence Hero Card */}
        <View style={styles.heroCard}>
          <View style={styles.heroTopRow}>
            <ClassificationBadge classification={primaryClassification} />
            <FreshnessPill
              hours={freshnessInfo.freshness_age_minutes != null ? Math.round(freshnessInfo.freshness_age_minutes / 60 * 10) / 10 : null}
              label={freshnessInfo.freshness_label}
              isStale={freshnessInfo.is_stale}
              syncTime={observedTime}
            />
          </View>

          <View style={styles.heroMainRow}>
            <View style={styles.heroAqiBlock}>
              <Text style={styles.heroAqiNumber}>
                {isStatValid && cityAQI != null ? Math.round(cityAQI) : (fallbackStation?.overall_aqi ? Math.round(fallbackStation.overall_aqi) : '--')}
              </Text>
              <View style={styles.heroAqiMeta}>
                <Text style={styles.heroAqiUnit}>AQI</Text>
                <View style={[styles.categoryBadge, { backgroundColor: cityColor }]}>
                  <Text style={styles.categoryBadgeText}>{cityCat}</Text>
                </View>
              </View>
            </View>

            <View style={styles.heroSubBlock}>
              <DominantPollutantBadge pollutant={dominantPollutant} />
              <StatValidityBadge
                isValid={isStatValid}
                reportingCount={monitoredCount}
                totalCount={16}
              />
            </View>
          </View>

          <View style={styles.heroFooterRow}>
            <View style={styles.heroFooterItem}>
              <Ionicons name="radio-outline" size={13} color={THEME.textMuted} />
              <Text style={styles.heroFooterText}>
                {monitoredCount} Active Stations ({groundMeasuredCount} Ground Measured)
              </Text>
            </View>
            {observedTime && (
              <View style={styles.heroFooterItem}>
                <Ionicons name="time-outline" size={13} color={THEME.textMuted} />
                <Text style={styles.heroFooterText}>Observed: {observedTime}</Text>
              </View>
            )}
          </View>
        </View>

        {/* 24-Hour ML Forecast Horizon Strip */}
        {forecasts.length > 0 && (
          <>
            <SectionHeader
              title="24-Hour AQI Forecast"
              subtitle={`Predictive horizon via ${forecastFetch.data?.model_used || 'Multi-Horizon Model'}`}
              rightElement={
                <TouchableOpacity onPress={() => navigation.navigate('Forecast')} activeOpacity={0.7}>
                  <Text style={styles.seeAllText}>Full Model &gt;</Text>
                </TouchableOpacity>
              }
            />
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.forecastStripContent}
            >
              {forecasts.slice(0, 10).map((fc, idx) => {
                const targetD = fc.target_timestamp ? new Date(fc.target_timestamp) : null;
                const timeLabel = targetD
                  ? targetD.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
                  : `+${fc.step_ahead_hours}h`;
                const aqiVal = Math.round(fc.predicted_aqi);
                const color = fc.color_hex || getAQIColor(fc.category);

                return (
                  <View key={idx} style={[styles.forecastStripCard, { borderTopColor: color, borderTopWidth: 3 }]}>
                    <Text style={styles.forecastHour}>{timeLabel}</Text>
                    <Text style={[styles.forecastAqi, { color }]}>{aqiVal}</Text>
                    <Text style={styles.forecastCat} numberOfLines={1}>{fc.category || 'Moderate'}</Text>
                    <Text style={styles.forecastBand}>±{Math.round(fc.expected_error_band || 12)}</Text>
                  </View>
                );
              })}
            </ScrollView>
          </>
        )}

        {/* Hourly Pollution Trend Chart */}
        {trendChartData && (
          <>
            <SectionHeader
              title="Hourly Pollution Trend"
              subtitle="Recent observed AQI readings across reporting hours"
            />
            <View style={styles.chartCard}>
              <LineChart
                data={trendChartData}
                width={CHART_WIDTH}
                height={160}
                chartConfig={CHART_CONFIG}
                bezier
                style={{ borderRadius: THEME.radiusSm }}
                withShadow={false}
              />
              <View style={styles.thresholdRow}>
                {[
                  { label: 'Good (≤50)', color: CPCB_COLORS.Good },
                  { label: 'Moderate (≤200)', color: CPCB_COLORS.Moderate },
                  { label: 'Poor (≤300)', color: CPCB_COLORS.Poor },
                ].map(t => (
                  <View key={t.label} style={styles.tRow}>
                    <View style={[styles.tDot, { backgroundColor: t.color }]} />
                    <Text style={styles.tLabel}>{t.label}</Text>
                  </View>
                ))}
              </View>
            </View>
          </>
        )}

        {/* Public Health Advisory Card */}
        <SectionHeader
          title="Health Advisory & Recommendations"
          subtitle="CPCB public health implications and precautions"
        />
        <HealthAdvisoryCard
          category={cityCat}
          dominantPollutant={dominantPollutant}
        />

        {/* Extremes: Best & Worst Stations */}
        {(worst || cleanest) && (
          <>
            <SectionHeader
              title="Station Extremes"
              subtitle="Highest and lowest observed index readings"
            />
            <View style={styles.extremesRow}>
              {cleanest && (
                <TouchableOpacity
                  style={styles.extremeCard}
                  onPress={() => navigation.navigate('StationDetail', { station: cleanest })}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.extremeLabel, { color: THEME.success }]}>Lowest AQI</Text>
                  <Text style={styles.extremeStationName} numberOfLines={1}>
                    {cleanest.station_name}
                  </Text>
                  <View style={styles.extremeScoreRow}>
                    <Text style={[styles.extremeScore, { color: getAQIColor(cleanest.aqi_category) }]}>
                      {Math.round(cleanest.overall_aqi)}
                    </Text>
                    <Text style={styles.extremeCat}>{cleanest.aqi_category}</Text>
                  </View>
                </TouchableOpacity>
              )}
              {worst && (
                <TouchableOpacity
                  style={styles.extremeCard}
                  onPress={() => navigation.navigate('StationDetail', { station: worst })}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.extremeLabel, { color: THEME.warning }]}>Highest AQI</Text>
                  <Text style={styles.extremeStationName} numberOfLines={1}>
                    {worst.station_name}
                  </Text>
                  <View style={styles.extremeScoreRow}>
                    <Text style={[styles.extremeScore, { color: getAQIColor(worst.aqi_category) }]}>
                      {Math.round(worst.overall_aqi)}
                    </Text>
                    <Text style={styles.extremeCat}>{worst.aqi_category}</Text>
                  </View>
                </TouchableOpacity>
              )}
            </View>
          </>
        )}

        {/* Detailed Pollutants Matrix */}
        <SectionHeader
          title="Pollutant Concentrations"
          subtitle="Surface concentrations across monitored criteria pollutants"
        />
        <View style={styles.metricsGrid}>
          <MetricPill label="PM2.5" value={pollutants.pm25} unit="µg/m³" statusColor="#f87171" />
          <MetricPill label="PM10"  value={pollutants.pm10} unit="µg/m³" statusColor="#fb923c" />
        </View>
        <View style={styles.metricsGrid}>
          <MetricPill label="NO₂"  value={pollutants.no2} unit="µg/m³" statusColor="#a78bfa" />
          <MetricPill label="SO₂"  value={pollutants.so2} unit="µg/m³" statusColor="#fbbf24" />
        </View>
        <View style={styles.metricsGrid}>
          <MetricPill label="CO"   value={pollutants.co}  unit="mg/m³" statusColor="#4ade80" />
          <MetricPill label="O₃"   value={pollutants.o3}  unit="µg/m³" statusColor="#38bdf8" />
        </View>

        {/* Surface Meteorology Summary */}
        <View style={styles.weatherSummaryRow}>
          <View style={styles.weatherItem}>
            <Text style={styles.weatherLabel}>Temperature</Text>
            <Text style={styles.weatherValue}>
              {pollutants.temperature != null ? Number(pollutants.temperature).toFixed(1) + ' °C' : '--'}
            </Text>
          </View>
          <View style={styles.weatherItemDivider} />
          <View style={styles.weatherItem}>
            <Text style={styles.weatherLabel}>Relative Humidity</Text>
            <Text style={styles.weatherValue}>
              {pollutants.humidity != null ? Number(pollutants.humidity).toFixed(0) + ' %' : '--'}
            </Text>
          </View>
          <View style={styles.weatherItemDivider} />
          <View style={styles.weatherItem}>
            <Text style={styles.weatherLabel}>Wind Speed</Text>
            <Text style={styles.weatherValue}>
              {pollutants.wind_speed != null ? Number(pollutants.wind_speed).toFixed(1) + ' km/h' : '--'}
            </Text>
          </View>
        </View>

        {/* All Active Stations */}
        <SectionHeader
          title="Monitoring Stations"
          subtitle="Reporting continuous ambient air quality stations in Greater Mumbai"
        />
        {stations.length > 0 ? (
          stations.map((st, i) => (
            <StationCard
              key={st.station_id_code || i}
              name={st.station_name}
              aqi={st.overall_aqi}
              category={st.aqi_category}
              zone={st.station_id_code}
              source={st.source}
              dataClassification={st.data_classification}
              onPress={() => navigation.navigate('StationDetail', { station: st })}
            />
          ))
        ) : (
          <EmptyCard
            title="No Active Stations"
            message="No monitoring sensors are currently transmitting observations for this region."
            actionLabel="Refresh Station Feeds"
            onAction={refetch}
          />
        )}

        <View style={{ height: 32 }} />
      </ScrollView>

      {/* System Health Telemetry Modal */}
      <SystemHealthModal
        visible={healthModalVisible}
        onClose={() => setHealthModalVisible(false)}
        telemetry={telemetryFetch.data}
        onRefresh={telemetryFetch.refetch}
      />
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
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
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
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  healthStatusBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: THEME.surface,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: THEME.radiusFull,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: THEME.success,
  },
  healthStatusText: {
    color: THEME.textSecondary,
    fontSize: 11,
    fontWeight: '700',
  },
  seeAllText: {
    color: THEME.primaryLight,
    fontSize: 11,
    fontWeight: '700',
  },
  heroCard: {
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 12,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusLg,
    padding: 18,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  heroTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  heroMainRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  heroAqiBlock: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 12,
  },
  heroAqiNumber: {
    fontSize: 52,
    fontWeight: '800',
    color: THEME.textPrimary,
    letterSpacing: -1,
  },
  heroAqiMeta: {
    gap: 4,
  },
  heroAqiUnit: {
    color: THEME.textMuted,
    fontSize: 12,
    fontWeight: '700',
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: THEME.radiusXs,
  },
  categoryBadgeText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  heroSubBlock: {
    alignItems: 'flex-end',
    gap: 8,
  },
  heroFooterRow: {
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    paddingTop: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  heroFooterItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  heroFooterText: {
    color: THEME.textMuted,
    fontSize: 11,
  },
  forecastStripContent: {
    paddingHorizontal: 16,
    gap: 8,
    paddingBottom: 4,
  },
  forecastStripCard: {
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusSm,
    padding: 12,
    minWidth: 80,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: THEME.border,
  },
  forecastHour: {
    color: THEME.textMuted,
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 4,
  },
  forecastAqi: {
    fontSize: 20,
    fontWeight: '800',
    marginBottom: 2,
  },
  forecastCat: {
    color: THEME.textSecondary,
    fontSize: 9,
    fontWeight: '700',
    marginBottom: 4,
  },
  forecastBand: {
    color: THEME.textMuted,
    fontSize: 9,
  },
  chartCard: {
    marginHorizontal: 16,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  thresholdRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
  },
  tRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  tDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  tLabel: {
    color: THEME.textMuted,
    fontSize: 9,
  },
  extremesRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 12,
    marginBottom: 10,
  },
  extremeCard: {
    flex: 1,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusMd,
    padding: 12,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  extremeLabel: {
    ...TYPOGRAPHY.overline,
    fontWeight: '700',
    marginBottom: 4,
  },
  extremeStationName: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.bodySecondary,
    fontWeight: '600',
    marginBottom: 6,
  },
  extremeScoreRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
  },
  extremeScore: {
    fontSize: 22,
    fontWeight: '800',
  },
  extremeCat: {
    color: THEME.textMuted,
    fontSize: 10,
    fontWeight: '600',
  },
  metricsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 10,
  },
  weatherSummaryRow: {
    flexDirection: 'row',
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginVertical: 6,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    justifyContent: 'space-around',
  },
  weatherItem: {
    alignItems: 'center',
  },
  weatherLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
    marginBottom: 4,
  },
  weatherValue: {
    color: THEME.textPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
  weatherItemDivider: {
    width: 1,
    backgroundColor: THEME.border,
  },
});
