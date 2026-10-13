/**
 * Tab 3: Forecast & Analytics Screen
 * Redesigned for production SaaS: clean typography, clear model metrics table,
 * responsive multi-step forecast strip, and zero emojis.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  Dimensions, TouchableOpacity, RefreshControl
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { Ionicons } from '@expo/vector-icons';
import { useFetch } from '../hooks/useFetch';
import { LoadingCard, ErrorCard, SectionHeader, getAQIColor } from '../components/SharedComponents';
import { ENDPOINTS, THEME, CPCB_COLORS } from '../config';

const { width: SCREEN_W } = Dimensions.get('window');
const CHART_WIDTH = SCREEN_W - 32;

const STATIONS = [
  { id: 'MUM_BKC',      label: 'BKC' },
  { id: 'MUM_COLABA',   label: 'Colaba' },
  { id: 'MUM_CHEMBUR',  label: 'Chembur' },
  { id: 'MUM_WORLI',    label: 'Worli' },
  { id: 'MUM_KURLA',    label: 'Kurla' },
];

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

export default function ForecastScreen() {
  const [selectedStation, setSelectedStation] = useState('MUM_BKC');
  const [refreshing, setRefreshing] = useState(false);

  const histUrl = `${ENDPOINTS.historicalAqi}?station_id=${selectedStation}&limit=24`;
  const predUrl = `${ENDPOINTS.predict}?station_id=${selectedStation}&hours=24`;
  const metricsUrl = ENDPOINTS.modelMetrics;

  const hist  = useFetch(histUrl);
  const pred  = useFetch(predUrl);
  const model = useFetch(metricsUrl);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([hist.refetch(), pred.refetch(), model.refetch()]);
    setRefreshing(false);
  };

  // Historical data series
  const histData = hist.data?.history?.filter(r => r.overall_aqi != null) || [];
  const histValues = histData.map(r => r.overall_aqi);
  const histChartData = histValues.length > 1 ? {
    labels: histData.filter((_, i) => i % 6 === 0).map(r => {
      const d = new Date(r.recorded_at);
      return `${d.getHours()}:00`;
    }),
    datasets: [{ data: histValues, strokeWidth: 2 }]
  } : null;

  // Forecast data series
  const forecasts = pred.data?.forecasts || [];
  const predValues = forecasts.map(f => f.predicted_aqi);
  const predChartData = predValues.length > 1 ? {
    labels: forecasts.filter((_, i) => i % 6 === 0).map(f => `+${f.step_ahead_hours}h`),
    datasets: [
      { data: predValues, strokeWidth: 2, color: (o=1) => `rgba(56, 189, 248, ${o})` },
    ]
  } : null;

  const metrics = model.data;

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
        <View style={styles.headerBar}>
          <Text style={styles.headerSubtitle}>Predictive Modeling</Text>
          <Text style={styles.headerTitle}>Forecast & Analytics</Text>
        </View>

        {/* Station Filter Tabs */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {STATIONS.map(s => {
            const active = selectedStation === s.id;
            return (
              <TouchableOpacity
                key={s.id}
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => setSelectedStation(s.id)}
                activeOpacity={0.7}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>
                  {s.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* 24-Hour ML Forecast Section */}
        <SectionHeader
          title="Predicted 24h Trend"
          subtitle={`Autonomous inference via ${pred.data?.model_used || 'Champion Model'}`}
        />
        {pred.loading ? (
          <View style={styles.chartPlaceholder}><LoadingCard message="Running inference pipeline..." /></View>
        ) : pred.error ? (
          <ErrorCard message={pred.error} onRetry={pred.refetch} />
        ) : predChartData ? (
          <View style={styles.card}>
            <LineChart
              data={predChartData}
              width={CHART_WIDTH - 24}
              height={190}
              chartConfig={{
                ...CHART_CONFIG,
                color: (o=1) => `rgba(56, 189, 248, ${o})`,
                propsForDots: { r: '3', strokeWidth: '1.5', stroke: '#38bdf8' },
              }}
              bezier
              style={{ borderRadius: THEME.radiusSm }}
              withShadow={false}
            />

            {/* Hourly Horizon Horizontal List */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 14 }}>
              <View style={styles.forecastHourRow}>
                {forecasts.slice(0, 8).map((fc, i) => (
                  <View key={i} style={[styles.forecastHourCard, { borderLeftColor: fc.color_hex, borderLeftWidth: 3 }]}>
                    <Text style={styles.fhHour}>+{fc.step_ahead_hours}h</Text>
                    <Text style={[styles.fhAqi, { color: fc.color_hex }]}>
                      {Math.round(fc.predicted_aqi)}
                    </Text>
                    <Text style={styles.fhCat}>{fc.category?.split(' ')[0]}</Text>
                    <Text style={styles.fhBound}>
                      {Math.round(fc.confidence_lower)}–{Math.round(fc.confidence_upper)}
                    </Text>
                  </View>
                ))}
              </View>
            </ScrollView>
          </View>
        ) : (
          <Text style={styles.noData}>No forecast records found for this station.</Text>
        )}

        {/* Historical 24-Hour Observation Section */}
        <SectionHeader
          title="Observed 24h Trend"
          subtitle={`Continuous sensor logs for ${selectedStation}`}
        />
        {hist.loading ? (
          <View style={styles.chartPlaceholder}><LoadingCard message="Retrieving station history..." /></View>
        ) : hist.error ? (
          <ErrorCard message={hist.error} onRetry={hist.refetch} />
        ) : histChartData ? (
          <View style={styles.card}>
            <LineChart
              data={histChartData}
              width={CHART_WIDTH - 24}
              height={180}
              chartConfig={CHART_CONFIG}
              bezier
              style={{ borderRadius: THEME.radiusSm }}
              withShadow={false}
            />
            <View style={styles.thresholdRow}>
              {[
                { label: 'Good',    val: 50,  color: CPCB_COLORS.Good },
                { label: 'Moderate',val: 200, color: CPCB_COLORS.Moderate },
                { label: 'Poor',    val: 300, color: CPCB_COLORS.Poor },
                { label: 'Severe',  val: 500, color: CPCB_COLORS.Severe },
              ].map(t => (
                <View key={t.label} style={styles.tRow}>
                  <View style={[styles.tDot, { backgroundColor: t.color }]} />
                  <Text style={styles.tLabel}>{t.label} (≤{t.val})</Text>
                </View>
              ))}
            </View>
          </View>
        ) : (
          <Text style={styles.noData}>No historical data available.</Text>
        )}

        {/* Model Transparency & Benchmark Evaluation */}
        {metrics && (
          <>
            <SectionHeader
              title="Benchmark Evaluation"
              subtitle="Holdout test set comparison across candidate architectures"
            />
            <View style={styles.card}>
              <View style={styles.champRow}>
                <Ionicons name="checkmark-circle-outline" size={18} color={THEME.success} />
                <Text style={styles.champLabel}>Champion Architecture:</Text>
                <Text style={styles.champVal}>{metrics.champion_model?.replace('_', ' ')}</Text>
              </View>

              <View style={styles.metricsTable}>
                <View style={styles.tableHeader}>
                  <Text style={[styles.tcell, styles.theader, { flex: 2 }]}>Model</Text>
                  <Text style={[styles.tcell, styles.theader]}>MAE</Text>
                  <Text style={[styles.tcell, styles.theader]}>RMSE</Text>
                  <Text style={[styles.tcell, styles.theader]}>R²</Text>
                </View>
                {Object.entries(metrics.metrics_comparison || {}).map(([name, m], i) => {
                  const isChamp = name === metrics.champion_model;
                  return (
                    <View key={name} style={[styles.tableRow, i % 2 === 1 && styles.tableRowAlt]}>
                      <Text style={[styles.tcell, { flex: 2, color: isChamp ? THEME.primaryLight : THEME.textSecondary, fontWeight: isChamp ? '700' : '400' }]} numberOfLines={1}>
                        {name.replace('_', ' ')}
                      </Text>
                      <Text style={styles.tcell}>{m.MAE}</Text>
                      <Text style={styles.tcell}>{m.RMSE}</Text>
                      <Text style={styles.tcell}>{m.R2_Score}</Text>
                    </View>
                  );
                })}
              </View>
              <Text style={styles.metricsNote}>
                Errors reported in AQI index units. Evaluated using a strict temporal 80/20 train-test split without data leakage.
              </Text>
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
  headerBar: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 6,
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
  chipRow: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: THEME.radiusSm,
    backgroundColor: THEME.surface,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  chipActive: {
    backgroundColor: THEME.surfaceElevated,
    borderColor: THEME.primary,
  },
  chipText: {
    color: THEME.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  chipTextActive: {
    color: THEME.textPrimary,
  },
  card: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    borderRadius: THEME.radiusMd,
    padding: 14,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  chartPlaceholder: {
    height: 180,
    justifyContent: 'center',
  },
  thresholdRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 10,
    paddingTop: 10,
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
    fontSize: 10,
  },
  forecastHourRow: {
    flexDirection: 'row',
    gap: 8,
  },
  forecastHourCard: {
    backgroundColor: THEME.surfaceElevated,
    borderRadius: THEME.radiusSm,
    padding: 10,
    alignItems: 'center',
    minWidth: 62,
    gap: 3,
  },
  fhHour: {
    color: THEME.textMuted,
    fontSize: 10,
    fontWeight: '600',
  },
  fhAqi: {
    fontSize: 16,
    fontWeight: '800',
  },
  fhCat: {
    fontSize: 9,
    color: THEME.textSecondary,
  },
  fhBound: {
    fontSize: 8,
    color: THEME.textMuted,
  },
  champRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  champLabel: {
    color: THEME.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  champVal: {
    color: THEME.textPrimary,
    fontWeight: '700',
    fontSize: 13,
  },
  metricsTable: {
    borderRadius: THEME.radiusSm,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: THEME.border,
  },
  tableHeader: {
    flexDirection: 'row',
    backgroundColor: THEME.surfaceElevated,
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  tableRowAlt: {
    backgroundColor: THEME.surfaceElevated + '55',
  },
  tcell: {
    flex: 1,
    color: THEME.textSecondary,
    fontSize: 11,
  },
  theader: {
    color: THEME.textMuted,
    fontWeight: '700',
    fontSize: 10,
    textTransform: 'uppercase',
  },
  metricsNote: {
    color: THEME.textMuted,
    fontSize: 10,
    marginTop: 10,
    lineHeight: 14,
  },
  noData: {
    color: THEME.textMuted,
    textAlign: 'center',
    padding: 20,
    fontSize: 12,
  },
});
