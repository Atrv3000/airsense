/**
 * Tab 1: Home Dashboard Screen
 * Shows city-wide Mumbai AQI, worst/cleanest stations, pollutant metrics, and health advisory.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  RefreshControl, TouchableOpacity, StatusBar
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
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

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  if (loading && !refreshing) return <LoadingCard />;
  if (error) return <ErrorCard message={error} onRetry={refetch} />;
  if (!data) return null;

  const cityAQI = data.city_average_aqi;
  const cityCat = data.city_category;
  const cityColor = getAQIColor(cityCat);
  const healthMsg = getHealthAdvice(cityCat);
  const stations = data.stations || [];
  const worst = data.worst_location;
  const cleanest = data.cleanest_location;

  // Latest pollutant readings from worst station for demo grid
  const raw = worst || (stations.length > 0 ? stations[0] : null);

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={THEME.bg} />
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={THEME.primary} />}
      >
        {/* Hero City Card */}
        <LinearGradient
          colors={['#0f172a', '#1e293b']}
          style={styles.heroCard}
        >
          <Text style={styles.heroRegion}>Greater Mumbai</Text>
          <Text style={styles.heroLabel}>CITY AIR QUALITY INDEX</Text>
          <AQIBadge aqi={cityAQI} category={cityCat} size="lg" />
          <View style={[styles.heroCatPill, { backgroundColor: cityColor + '22', borderColor: cityColor }]}>
            <Text style={[styles.heroCatText, { color: cityColor }]}>{cityCat}</Text>
          </View>
          <Text style={styles.heroSubtext}>
            {data.monitored_stations_count} active monitoring stations
          </Text>
        </LinearGradient>

        {/* Health Advisory */}
        <View style={[styles.advisoryCard, { borderLeftColor: cityColor }]}>
          <Text style={styles.advisoryTitle}>🏥 Health Advisory</Text>
          <Text style={styles.advisoryText}>{healthMsg}</Text>
        </View>

        {/* Worst & Cleanest */}
        {(worst || cleanest) && (
          <>
            <SectionHeader title="Station Highlights" subtitle="Best & worst readings right now" />
            <View style={styles.highlightRow}>
              {worst && (
                <View style={[styles.highlightCard, { borderColor: '#FF000044' }]}>
                  <Text style={styles.hlLabel}>🔴 Most Polluted</Text>
                  <Text style={styles.hlName} numberOfLines={2}>{worst.station_name}</Text>
                  <Text style={[styles.hlAqi, { color: getAQIColor(worst.aqi_category) }]}>
                    {Math.round(worst.overall_aqi)} AQI
                  </Text>
                  <Text style={styles.hlCat}>{worst.aqi_category}</Text>
                </View>
              )}
              {cleanest && (
                <View style={[styles.highlightCard, { borderColor: '#00B05044' }]}>
                  <Text style={styles.hlLabel}>🟢 Cleanest Air</Text>
                  <Text style={styles.hlName} numberOfLines={2}>{cleanest.station_name}</Text>
                  <Text style={[styles.hlAqi, { color: getAQIColor(cleanest.aqi_category) }]}>
                    {Math.round(cleanest.overall_aqi)} AQI
                  </Text>
                  <Text style={styles.hlCat}>{cleanest.aqi_category}</Text>
                </View>
              )}
            </View>
          </>
        )}

        {/* Pollutant Concentration Grid */}
        {raw && (
          <>
            <SectionHeader
              title="Pollutant Concentrations"
              subtitle={`Live readings · ${raw.station_name || 'Mumbai'}`}
            />
            <View style={styles.metricsGrid}>
              <MetricPill label="PM2.5" value={raw.raw_pm25} unit="µg/m³" color="#f87171" />
              <MetricPill label="PM10"  value={raw.raw_pm10} unit="µg/m³" color="#fb923c" />
            </View>
            <View style={styles.metricsGrid}>
              <MetricPill label="NO₂"  value={raw.raw_no2} unit="µg/m³" color="#a78bfa" />
              <MetricPill label="SO₂"  value={raw.raw_so2} unit="µg/m³" color="#fbbf24" />
            </View>
            <View style={styles.metricsGrid}>
              <MetricPill label="CO"   value={raw.raw_co}  unit="mg/m³" color="#4ade80" />
              <MetricPill label="O₃"   value={raw.raw_o3}  unit="µg/m³" color="#38bdf8" />
            </View>

            {/* Weather Row */}
            <View style={styles.weatherRow}>
              <Text style={styles.weatherChip}>🌡️ {raw.temperature ? raw.temperature.toFixed(1) + ' °C' : '--'}</Text>
              <Text style={styles.weatherChip}>💧 {raw.humidity ? raw.humidity.toFixed(0) + ' %' : '--'}</Text>
              <Text style={styles.weatherChip}>💨 {raw.wind_speed ? raw.wind_speed.toFixed(1) + ' km/h' : '--'}</Text>
            </View>
          </>
        )}

        {/* All Stations List */}
        <SectionHeader title="All Monitoring Stations" subtitle="Tap a station for detailed view" />
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

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: THEME.bg },
  heroCard: {
    margin: 16,
    borderRadius: 20,
    padding: 28,
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  heroRegion:  { color: THEME.primary, fontWeight: '700', fontSize: 13, letterSpacing: 1, textTransform: 'uppercase' },
  heroLabel:   { color: THEME.textMuted, fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase' },
  heroCatPill: { paddingHorizontal: 20, paddingVertical: 6, borderRadius: 9999, borderWidth: 1.5, marginTop: 4 },
  heroCatText: { fontWeight: '700', fontSize: 13 },
  heroSubtext: { color: THEME.textMuted, fontSize: 11 },
  advisoryCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 14,
    padding: 16,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: THEME.border,
    gap: 6,
  },
  advisoryTitle: { color: THEME.textPrimary, fontWeight: '700', fontSize: 14 },
  advisoryText:  { color: THEME.textSecondary, fontSize: 13, lineHeight: 20 },
  highlightRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 12,
    marginBottom: 8,
  },
  highlightCard: {
    flex: 1,
    backgroundColor: THEME.surface,
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    gap: 4,
  },
  hlLabel:  { color: THEME.textMuted, fontSize: 11, fontWeight: '600' },
  hlName:   { color: THEME.textPrimary, fontWeight: '700', fontSize: 13 },
  hlAqi:    { fontSize: 22, fontWeight: '800' },
  hlCat:    { color: THEME.textSecondary, fontSize: 11 },
  metricsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 10,
  },
  weatherRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginBottom: 8,
    gap: 8,
    flexWrap: 'wrap',
  },
  weatherChip: {
    backgroundColor: THEME.surface,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    color: THEME.textSecondary,
    fontSize: 13,
    borderWidth: 1,
    borderColor: THEME.border,
  },
});
