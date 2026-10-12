/**
 * StationDetailScreen.js
 * Shows granular air quality & meteorological readings for a selected monitoring station.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, StatusBar, RefreshControl
} from 'react-native';
import { useFetch } from '../hooks/useFetch';
import {
  LoadingCard, ErrorCard, SectionHeader,
  AQIBadge, MetricPill, getAQIColor, getHealthAdvice
} from '../components/SharedComponents';
import { ENDPOINTS, THEME } from '../config';

export default function StationDetailScreen({ route, navigation }) {
  const { station } = route.params || {};
  const stationId = station?.station_id_code || station?.id || 'MUM_BKC';
  const stationName = station?.station_name || station?.name || stationId;

  const url = ENDPOINTS.stationAqi(stationId);
  const { data, loading, error, refetch } = useFetch(url);
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const current = data?.current || station || {};
  const aqiVal = current.overall_aqi ?? current.aqi ?? 0;
  const aqiCat = current.aqi_category ?? current.category ?? 'Unknown';
  const aqiColor = getAQIColor(aqiCat);
  const healthMsg = getHealthAdvice(aqiCat);

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={THEME.bg} />
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={THEME.primary} />}
      >
        {/* Header Banner */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
            <Text style={styles.backButtonText}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.stationTitle}>{stationName}</Text>
          <Text style={styles.stationCode}>ID: {stationId}</Text>
        </View>

        {loading && !refreshing ? (
          <LoadingCard />
        ) : error ? (
          <ErrorCard message={error} onRetry={refetch} />
        ) : (
          <>
            {/* Live AQI Score Card */}
            <View style={styles.cardContainer}>
              <AQIBadge aqi={aqiVal} category={aqiCat} size="lg" />
              <View style={[styles.badgePill, { backgroundColor: aqiColor + '20', borderColor: aqiColor }]}>
                <Text style={[styles.badgeText, { color: aqiColor }]}>Prominent Pollutant: {current.prominent_pollutant || 'N/A'}</Text>
              </View>
            </View>

            {/* Health Advisory */}
            <View style={[styles.advisoryCard, { borderLeftColor: aqiColor }]}>
              <Text style={styles.advisoryTitle}>Health Advisory</Text>
              <Text style={styles.advisoryText}>{healthMsg}</Text>
            </View>

            {/* Pollutants Breakdown */}
            <SectionHeader
              title="Pollutant Concentrations"
              subtitle="Calculated sub-indices & physical values"
            />
            <View style={styles.metricsGrid}>
              <MetricPill label="PM2.5" value={current.raw_pm25 ?? current.pm25} unit="µg/m³" color="#f87171" />
              <MetricPill label="PM10"  value={current.raw_pm10 ?? current.pm10} unit="µg/m³" color="#fb923c" />
            </View>
            <View style={styles.metricsGrid}>
              <MetricPill label="NO₂"  value={current.raw_no2 ?? current.no2} unit="µg/m³" color="#a78bfa" />
              <MetricPill label="SO₂"  value={current.raw_so2 ?? current.so2} unit="µg/m³" color="#fbbf24" />
            </View>
            <View style={styles.metricsGrid}>
              <MetricPill label="CO"   value={current.raw_co ?? current.co}   unit="mg/m³" color="#4ade80" />
              <MetricPill label="O₃"   value={current.raw_o3 ?? current.o3}   unit="µg/m³" color="#38bdf8" />
            </View>

            {/* Weather / Atmospheric */}
            <SectionHeader
              title="Atmospheric Conditions"
              subtitle="Surface meteorology at station"
            />
            <View style={styles.weatherGrid}>
              <View style={styles.weatherCard}>
                <Text style={styles.weatherIcon}>🌡️</Text>
                <Text style={styles.weatherLabel}>Temperature</Text>
                <Text style={styles.weatherValue}>
                  {current.temperature != null ? Number(current.temperature).toFixed(1) + ' °C' : '--'}
                </Text>
              </View>
              <View style={styles.weatherCard}>
                <Text style={styles.weatherIcon}>💧</Text>
                <Text style={styles.weatherLabel}>Humidity</Text>
                <Text style={styles.weatherValue}>
                  {current.humidity != null ? Number(current.humidity).toFixed(0) + ' %' : '--'}
                </Text>
              </View>
              <View style={styles.weatherCard}>
                <Text style={styles.weatherIcon}>💨</Text>
                <Text style={styles.weatherLabel}>Wind Speed</Text>
                <Text style={styles.weatherValue}>
                  {current.wind_speed != null ? Number(current.wind_speed).toFixed(1) + ' km/h' : '--'}
                </Text>
              </View>
            </View>
          </>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: THEME.bg },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
  },
  backButton: { marginBottom: 8 },
  backButtonText: { color: THEME.primary, fontSize: 15, fontWeight: '700' },
  stationTitle: { color: THEME.textPrimary, fontSize: 20, fontWeight: '800' },
  stationCode: { color: THEME.textMuted, fontSize: 12, marginTop: 2 },
  cardContainer: {
    alignItems: 'center',
    padding: 20,
    gap: 12,
  },
  badgePill: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
  },
  badgeText: { fontSize: 12, fontWeight: '700' },
  advisoryCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 14,
    padding: 16,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  advisoryTitle: { color: THEME.textPrimary, fontWeight: '700', fontSize: 14, marginBottom: 4 },
  advisoryText:  { color: THEME.textSecondary, fontSize: 13, lineHeight: 18 },
  metricsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 10,
  },
  weatherGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
  },
  weatherCard: {
    flex: 1,
    backgroundColor: THEME.surface,
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: THEME.border,
  },
  weatherIcon: { fontSize: 22, marginBottom: 4 },
  weatherLabel: { color: THEME.textMuted, fontSize: 10, fontWeight: '600', textTransform: 'uppercase' },
  weatherValue: { color: THEME.textPrimary, fontSize: 14, fontWeight: '700', marginTop: 4 },
});
