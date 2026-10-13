/**
 * StationDetailScreen.js
 * Shows granular continuous air quality & surface meteorology readings
 * for a specific monitoring station. Redesigned with clean SaaS typography,
 * consistent cards, and zero emojis.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, StatusBar, RefreshControl
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
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
        <View style={styles.navBar}>
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

        {/* Station Title */}
        <View style={styles.titleSection}>
          <Text style={styles.stationTitle}>{stationName}</Text>
          <Text style={styles.stationSubtitle}>Continuous Ambient Air Quality Monitoring Station (CAAQMS)</Text>
        </View>

        {loading && !refreshing ? (
          <LoadingCard message="Querying station sensors..." />
        ) : error ? (
          <ErrorCard message={error} onRetry={refetch} />
        ) : (
          <>
            {/* Live AQI Score Card */}
            <View style={styles.heroCard}>
              <AQIBadge aqi={aqiVal} category={aqiCat} size="lg" />
              <View style={styles.heroMeta}>
                <View style={styles.heroMetaItem}>
                  <Text style={styles.heroMetaLabel}>Prominent Pollutant</Text>
                  <Text style={styles.heroMetaVal}>{current.prominent_pollutant || 'PM2.5'}</Text>
                </View>
                <View style={styles.heroMetaDivider} />
                <View style={styles.heroMetaItem}>
                  <Text style={styles.heroMetaLabel}>Sensor Authority</Text>
                  <Text style={styles.heroMetaVal}>CPCB / MPCB</Text>
                </View>
              </View>
            </View>

            {/* Health Advisory */}
            <View style={[styles.advisoryCard, { borderLeftColor: aqiColor }]}>
              <View style={styles.advisoryHeader}>
                <Ionicons name="medical-outline" size={16} color={THEME.primaryLight} />
                <Text style={styles.advisoryTitle}>Health Advisory</Text>
              </View>
              <Text style={styles.advisoryText}>{healthMsg}</Text>
            </View>

            {/* Granular Pollutant Concentrations */}
            <SectionHeader
              title="Pollutant Concentrations"
              subtitle="Calibrated microgram concentrations and gas sub-indices"
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
              subtitle="Co-located automatic weather station telemetry"
            />
            <View style={styles.weatherSummaryRow}>
              <View style={styles.weatherItem}>
                <Text style={styles.weatherLabel}>Temperature</Text>
                <Text style={styles.weatherValue}>
                  {current.temperature ? current.temperature.toFixed(1) + ' °C' : '--'}
                </Text>
              </View>
              <View style={styles.weatherItemDivider} />
              <View style={styles.weatherItem}>
                <Text style={styles.weatherLabel}>Relative Humidity</Text>
                <Text style={styles.weatherValue}>
                  {current.humidity ? current.humidity.toFixed(0) + ' %' : '--'}
                </Text>
              </View>
              <View style={styles.weatherItemDivider} />
              <View style={styles.weatherItem}>
                <Text style={styles.weatherLabel}>Wind Velocity</Text>
                <Text style={styles.weatherValue}>
                  {current.wind_speed ? current.wind_speed.toFixed(1) + ' km/h' : '--'}
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
    paddingVertical: 6,
    paddingRight: 12,
  },
  backBtnText: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: '600',
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
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
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
  },
  stationSubtitle: {
    color: THEME.textMuted,
    fontSize: 12,
    marginTop: 2,
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
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  heroMetaVal: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: '700',
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
    fontSize: 13,
    fontWeight: '700',
  },
  advisoryText: {
    color: THEME.textSecondary,
    fontSize: 12,
    lineHeight: 17,
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
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  weatherValue: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: '700',
  },
});
