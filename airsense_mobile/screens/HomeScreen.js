/**
 * Tab 1: Home Dashboard Screen
 * Redesigned for production SaaS: clear typography, restrained visual hierarchy,
 * clean status indicators, and no decorative emojis.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  RefreshControl, TouchableOpacity, StatusBar
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFetch } from '../hooks/useFetch';
import {
  LoadingCard, ErrorCard, SectionHeader,
  AQIBadge, MetricPill, StationCard,
  getAQIColor, getHealthAdvice
} from '../components/SharedComponents';
import { ENDPOINTS, THEME } from '../config';

export default function HomeScreen({ navigation }) {
  const [refreshing, setRefreshing] = useState(false);
  const { data, loading, error, refetch } = useFetch(ENDPOINTS.liveAqi);

  // Minute-interval clock state
  const [currentTime, setCurrentTime] = useState(new Date());

  React.useEffect(() => {
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
    await refetch();
    setRefreshing(false);
  };

  if (loading && !refreshing) return <LoadingCard message="Retrieving station feeds..." />;
  if (error) return <ErrorCard message={error} onRetry={refetch} />;
  if (!data) return null;

  const cityAQI = data.city_average_aqi;
  const hasValidCityAqi = cityAQI !== null && cityAQI !== undefined && !isNaN(cityAQI);
  const cityCat = data.city_category;
  const cityColor = getAQIColor(cityCat);
  const healthMsg = getHealthAdvice(cityCat);
  const stations = data.stations || [];
  const worst = data.worst_location;
  const cleanest = data.cleanest_location;

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
  const observedTime = fallbackStation?.recorded_at ? new Date(fallbackStation.recorded_at).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }) : null;

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
        {/* Top App Header with Real Date & Live Clock */}
        <View style={styles.headerBar}>
          <View>
            <Text style={styles.headerSubtitle}>{formattedDate}</Text>
            <Text style={styles.headerTitle}>Greater Mumbai</Text>
          </View>
          <View style={styles.liveIndicator}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>{formattedClock}</Text>
          </View>
        </View>

        {/* Primary City Index Card */}
        <View style={styles.heroCard}>
          <View style={styles.heroLeft}>
            <View style={styles.heroTagRow}>
              <Text style={styles.heroTag}>Citywide Air Quality</Text>
              {observedTime && (
                <Text style={styles.heroObservedTime}>Sync: {observedTime}</Text>
              )}
            </View>
            <View style={styles.heroAqiRow}>
              <Text style={styles.heroAqiNumber}>
                {hasValidCityAqi ? Math.round(cityAQI) : '--'}
              </Text>
              <View style={styles.heroAqiMeta}>
                <Text style={styles.heroAqiUnit}>AQI</Text>
                <View style={[styles.categoryBadge, { backgroundColor: cityColor }]}>
                  <Text style={styles.categoryBadgeText}>{cityCat || 'No data'}</Text>
                </View>
              </View>
            </View>
            <Text style={styles.heroStationCount}>
              Mean of {data.monitored_stations_count || stations.length} active monitoring station AQIs
            </Text>
          </View>
        </View>

        {/* Health Advisory Banner */}
        <View style={styles.advisoryCard}>
          <View style={styles.advisoryHeader}>
            <Ionicons name="information-circle-outline" size={18} color={THEME.primaryLight} />
            <Text style={styles.advisoryTitle}>Health Advisory</Text>
          </View>
          <Text style={styles.advisoryText}>{healthMsg}</Text>
        </View>

        {/* Extremes: Best & Worst Stations */}
        {(worst || cleanest) && (
          <>
            <SectionHeader
              title="Station Extremes"
              subtitle="Highest and lowest observed index readings"
            />
            <View style={styles.extremesRow}>
              {cleanest && (
                <View style={styles.extremeCard}>
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
                </View>
              )}
              {worst && (
                <View style={styles.extremeCard}>
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
                </View>
              )}
            </View>
          </>
        )}

        {/* Detailed Pollutants Matrix */}
        <SectionHeader
          title="Pollutant Concentrations"
          subtitle="Citywide ground telemetry across reporting stations"
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
          subtitle="Select a station to inspect time-series logs and sub-indices"
        />
        {stations.map((st, i) => (
          <StationCard
            key={st.station_id_code || i}
            name={st.station_name}
            aqi={st.overall_aqi}
            category={st.aqi_category}
            zone={st.station_id_code}
            onPress={() => navigation.navigate('StationDetail', { station: st })}
          />
        ))}

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
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerSubtitle: {
    color: THEME.textMuted,
    fontSize: 12,
    fontWeight: '500',
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  headerTitle: {
    color: THEME.textPrimary,
    fontSize: 22,
    fontWeight: '800',
    letterSpacing: -0.4,
    marginTop: 2,
  },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: THEME.surface,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: THEME.success,
  },
  liveText: {
    color: THEME.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  heroCard: {
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 12,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusLg,
    padding: 20,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  heroLeft: {
    gap: 6,
  },
  heroTagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heroTag: {
    color: THEME.textMuted,
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  heroObservedTime: {
    color: THEME.primaryLight,
    fontSize: 11,
    fontWeight: '600',
  },
  heroAqiRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 12,
    marginVertical: 4,
  },
  heroAqiNumber: {
    color: THEME.textPrimary,
    fontSize: 54,
    fontWeight: '800',
    letterSpacing: -2,
  },
  heroAqiMeta: {
    gap: 4,
  },
  heroAqiUnit: {
    color: THEME.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  categoryBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 6,
  },
  categoryBadgeText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700',
  },
  heroStationCount: {
    color: THEME.textSecondary,
    fontSize: 12,
  },
  advisoryCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    gap: 6,
  },
  advisoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  advisoryTitle: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: '700',
  },
  advisoryText: {
    color: THEME.textSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
  extremesRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
  },
  extremeCard: {
    flex: 1,
    backgroundColor: THEME.surface,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
    gap: 4,
  },
  extremeLabel: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  extremeStationName: {
    color: THEME.textPrimary,
    fontWeight: '600',
    fontSize: 13,
  },
  extremeScoreRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
    marginTop: 4,
  },
  extremeScore: {
    fontSize: 22,
    fontWeight: '800',
  },
  extremeCat: {
    color: THEME.textMuted,
    fontSize: 11,
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
    fontSize: 11,
    fontWeight: '500',
  },
  weatherValue: {
    color: THEME.textPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
});
