/**
 * Tab 3: Forecast & Analytics Screen
 * Shows historical AQI trend chart + 24-hour ML prediction chart
 * with model transparency card (MAE, RMSE, R²).
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  Dimensions, TouchableOpacity, RefreshControl
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { useFetch } from '../hooks/useFetch';
import { LoadingCard, ErrorCard, SectionHeader, getAQIColor } from '../components/SharedComponents';
import { ENDPOINTS, THEME, CPCB_COLORS } from '../config';

const { width: SCREEN_W } = Dimensions.get('window');
const CHART_WIDTH = SCREEN_W - 40;

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
  color: (opacity = 1) => `rgba(56,189,248,${opacity})`,
  labelColor: (opacity = 1) => `rgba(148,163,184,${opacity})`,
  propsForDots: { r: '3', strokeWidth: '1.5', stroke: '#38bdf8' },
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
    await Promise.all([hist.refetch(), pred.refetch()]);
    setRefreshing(false);
  };

  // Build Historical Chart data
  const histData = hist.data?.history?.filter(r => r.overall_aqi != null) || [];
  const histLabels = histData
    .filter((_, i) => i % 4 === 0)
    .map(r => {
      const d = new Date(r.recorded_at);
      return `${d.getHours()}:00`;
    });
  const histValues = histData.map(r => r.overall_aqi);
  const histChartData = histValues.length > 1 ? {
    labels: histData.filter((_, i) => i % 4 === 0).map(r => {
      const d = new Date(r.recorded_at); return `${d.getHours()}h`;
    }),
    datasets: [{ data: histValues, strokeWidth: 2 }]
  } : null;

  // Build Forecast Chart data
  const forecasts = pred.data?.forecasts || [];
  const predValues = forecasts.map(f => f.predicted_aqi);
  const predChartData = predValues.length > 1 ? {
    labels: forecasts.filter((_, i) => i % 4 === 0).map(f => `+${f.step_ahead_hours}h`),
    datasets: [
      { data: predValues, strokeWidth: 2, color: (o=1) => `rgba(129,140,248,${o})` },
    ]
  } : null;

  // Model Metrics
  const metrics = model.data;

  return (
    <View style={styles.container}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={THEME.primary} />}
      >
        {/* Station Selector Chips */}
        <View style={styles.chipRow}>
          {STATIONS.map(s => (
            <TouchableOpacity
              key={s.id}
              style={[styles.chip, selectedStation === s.id && styles.chipActive]}
              onPress={() => setSelectedStation(s.id)}
            >
              <Text style={[styles.chipText, selectedStation === s.id && styles.chipTextActive]}>
                {s.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Historical Chart */}
        <SectionHeader
          title="Historical AQI (Last 24h)"
          subtitle={`Station: ${selectedStation}`}
        />
        {hist.loading ? (
          <View style={styles.chartPlaceholder}><LoadingCard /></View>
        ) : hist.error ? (
          <ErrorCard message={hist.error} onRetry={hist.refetch} />
        ) : histChartData ? (
          <View style={styles.chartCard}>
            <LineChart
              data={histChartData}
              width={CHART_WIDTH - 32}
              height={200}
              chartConfig={CHART_CONFIG}
              bezier
              style={{ borderRadius: 10 }}
              withShadow={false}
            />
            <View style={styles.thresholdRow}>
              {[
                { label: 'Good',    val: 50,  color: CPCB_COLORS.Good },
                { label: 'Mod.',    val: 150, color: CPCB_COLORS.Moderate },
                { label: 'Poor',    val: 250, color: CPCB_COLORS.Poor },
                { label: 'V.Poor',  val: 350, color: CPCB_COLORS['Very Poor'] },
              ].map(t => (
                <View key={t.label} style={styles.tRow}>
                  <View style={[styles.tDot, { backgroundColor: t.color }]} />
                  <Text style={styles.tLabel}>{t.label}: {t.val}</Text>
                </View>
              ))}
            </View>
          </View>
        ) : (
          <Text style={styles.noData}>No historical data available.</Text>
        )}

        {/* Forecast Chart */}
        <SectionHeader
          title="ML Forecast (Next 24h)"
          subtitle={`Model: ${pred.data?.model_used || 'Loading...'}`}
        />
        {pred.loading ? (
          <View style={styles.chartPlaceholder}><LoadingCard /></View>
        ) : pred.error ? (
          <ErrorCard message={pred.error} onRetry={pred.refetch} />
        ) : predChartData ? (
          <View style={styles.chartCard}>
            <LineChart
              data={predChartData}
              width={CHART_WIDTH - 32}
              height={200}
              chartConfig={{
                ...CHART_CONFIG,
                color: (o=1) => `rgba(129,140,248,${o})`,
                propsForDots: { r: '3', strokeWidth: '1.5', stroke: '#818cf8' },
              }}
              bezier
              style={{ borderRadius: 10 }}
              withShadow={false}
            />
            {/* Forecast Hour Cards */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.forecastHourRow}>
                {forecasts.slice(0, 12).map((fc, i) => (
                  <View key={i} style={[styles.forecastHourCard, { borderColor: fc.color_hex }]}>
                    <Text style={styles.fhHour}>+{fc.step_ahead_hours}h</Text>
                    <Text style={[styles.fhAqi, { color: fc.color_hex }]}>{Math.round(fc.predicted_aqi)}</Text>
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
          <Text style={styles.noData}>No forecast data available.</Text>
        )}

        {/* Model Transparency Card */}
        {metrics && (
          <>
            <SectionHeader
              title="Model Transparency"
              subtitle="Benchmark comparison across 4 ML models"
            />
            <View style={styles.metricsCard}>
              <View style={styles.champRow}>
                <Text style={styles.champLabel}>🏆 Champion Model:</Text>
                <Text style={styles.champVal}>{metrics.champion_model}</Text>
              </View>
              <View style={styles.metricsTable}>
                <View style={styles.tableHeader}>
                  <Text style={[styles.tcell, styles.theader, { flex: 2 }]}>Model</Text>
                  <Text style={[styles.tcell, styles.theader]}>MAE</Text>
                  <Text style={[styles.tcell, styles.theader]}>RMSE</Text>
                  <Text style={[styles.tcell, styles.theader]}>R²</Text>
                </View>
                {Object.entries(metrics.metrics_comparison || {}).map(([name, m], i) => (
                  <View key={name} style={[styles.tableRow, i % 2 === 0 && styles.tableRowAlt]}>
                    <Text style={[styles.tcell, { flex: 2, color: name === metrics.champion_model ? THEME.primary : THEME.textSecondary, fontWeight: name === metrics.champion_model ? '700' : '400' }]} numberOfLines={2}>
                      {name.replace('_', ' ')}
                    </Text>
                    <Text style={styles.tcell}>{m.MAE}</Text>
                    <Text style={styles.tcell}>{m.RMSE}</Text>
                    <Text style={styles.tcell}>{m.R2_Score}</Text>
                  </View>
                ))}
              </View>
              <Text style={styles.metricsNote}>
                * All errors in AQI points. Models trained on 80% historical data; evaluated on the last 20%.
              </Text>
            </View>
          </>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: THEME.bg },
  chipRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 8,
    flexWrap: 'wrap',
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 9999,
    backgroundColor: THEME.surface,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  chipActive:    { backgroundColor: THEME.primaryDark, borderColor: THEME.primary },
  chipText:      { color: THEME.textSecondary, fontSize: 13, fontWeight: '600' },
  chipTextActive:{ color: '#fff' },
  chartCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  chartPlaceholder: { height: 220 },
  thresholdRow:  { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  tRow:          { flexDirection: 'row', alignItems: 'center', gap: 4 },
  tDot:          { width: 8, height: 8, borderRadius: 4 },
  tLabel:        { color: THEME.textMuted, fontSize: 10 },
  forecastHourRow: { flexDirection: 'row', gap: 8, marginTop: 12, paddingBottom: 4 },
  forecastHourCard: {
    backgroundColor: THEME.surfaceAlt,
    borderRadius: 10,
    padding: 10,
    alignItems: 'center',
    borderWidth: 1.5,
    minWidth: 60,
  },
  fhHour:  { color: THEME.textMuted, fontSize: 10, fontWeight: '600' },
  fhAqi:   { fontSize: 18, fontWeight: '800', marginTop: 4 },
  fhCat:   { fontSize: 9, color: THEME.textSecondary, marginTop: 2 },
  fhBound: { fontSize: 8, color: THEME.textMuted, marginTop: 2 },
  metricsCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: THEME.border,
    marginBottom: 8,
  },
  champRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  champLabel:{ color: THEME.textSecondary, fontSize: 13, fontWeight: '600' },
  champVal:  { color: THEME.primary, fontWeight: '800', fontSize: 14 },
  metricsTable: { borderRadius: 10, overflow: 'hidden', borderWidth: 1, borderColor: THEME.border },
  tableHeader: {
    flexDirection: 'row',
    backgroundColor: THEME.surfaceAlt,
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  tableRow:    { flexDirection: 'row', paddingVertical: 8, paddingHorizontal: 10 },
  tableRowAlt: { backgroundColor: THEME.surfaceAlt },
  tcell:  { flex: 1, color: THEME.textSecondary, fontSize: 12 },
  theader:{ color: THEME.textMuted, fontWeight: '700', fontSize: 11 },
  metricsNote: { color: THEME.textMuted, fontSize: 10, marginTop: 10, lineHeight: 14 },
  noData: { color: THEME.textMuted, textAlign: 'center', padding: 20, fontSize: 13 },
});
