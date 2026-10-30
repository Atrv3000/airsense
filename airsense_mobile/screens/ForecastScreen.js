/**
 * Tab 3: Forecast & Analytics Screen
 * Redesigned for production SaaS: clean typography, clear model metrics table,
 * dynamic station selection from backend, multi-horizon forecast strip, and zero emojis.
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  Dimensions, TouchableOpacity, RefreshControl
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFetch } from '../hooks/useFetch';
import { LoadingCard, ErrorCard, ErrorBanner, EmptyCard, SectionHeader, getAQIColor } from '../components/SharedComponents';
import { ENDPOINTS, THEME, CPCB_COLORS, TYPOGRAPHY, SPACING } from '../config';

const { width: SCREEN_W } = Dimensions.get('window');
// Card has marginHorizontal: 16 (32px total) and padding: 14 (28px total). Inner width is SCREEN_W - 60.
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

export default function ForecastScreen() {
  const insets = useSafeAreaInsets();
  const stationsFetch = useFetch(ENDPOINTS.stations);
  const stationList = Array.isArray(stationsFetch.data)
    ? stationsFetch.data
    : (stationsFetch.data?.results || stationsFetch.data?.stations || []);

  const [selectedStation, setSelectedStation] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Set default station once stations are loaded
  useEffect(() => {
    if (stationList.length > 0 && !selectedStation) {
      setSelectedStation(stationList[0].station_id || stationList[0].id);
    }
  }, [stationList, selectedStation]);

  // Update clock every minute instead of every second to conserve CPU/battery
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

  const currentStationId = selectedStation || (stationList[0]?.station_id || 'OPENAQ_6927');

  const histUrl = `${ENDPOINTS.historicalAqi}?station_id=${currentStationId}&limit=24`;
  const predUrl = `${ENDPOINTS.predict}?station_id=${currentStationId}&hours=24`;
  const metricsUrl = ENDPOINTS.modelMetrics;
  const verifUrl = `${ENDPOINTS.forecastVerification}?days=7`;

  const hist  = useFetch(currentStationId ? histUrl : null);
  const pred  = useFetch(currentStationId ? predUrl : null);
  const model = useFetch(metricsUrl);
  const verif = useFetch(verifUrl);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      stationsFetch.refetch(),
      hist.refetch(),
      pred.refetch(),
      model.refetch(),
      verif.refetch(),
    ]);
    setRefreshing(false);
  };

  // Historical data series: evenly sample 7-8 points across 24h so labels.length === data.length
  const histData = hist.data?.history?.filter(r => r.overall_aqi != null) || [];
  const histStep = Math.max(1, Math.floor(histData.length / 7));
  const sampledHist = histData.length > 7
    ? histData.filter((_, i) => i % histStep === 0 || i === histData.length - 1).slice(0, 8)
    : histData;
  const histValues = sampledHist.map(r => Math.round(r.overall_aqi));
  const histLabels = sampledHist.map(r => {
    const d = new Date(r.recorded_at);
    return `${d.getHours()}:00`;
  });
  const histChartData = histValues.length > 1 ? {
    labels: histLabels,
    datasets: [{ data: histValues, strokeWidth: 2 }]
  } : null;

  // Forecast data series: deduplicate by horizon and evenly sample 7-8 points
  const rawForecasts = pred.data?.forecasts || [];
  const seenHorizons = new Set();
  const forecasts = rawForecasts.filter(f => {
    if (seenHorizons.has(f.step_ahead_hours)) return false;
    seenHorizons.add(f.step_ahead_hours);
    return true;
  });

  const predStep = Math.max(1, Math.floor(forecasts.length / 7));
  const sampledForecasts = forecasts.length > 7
    ? forecasts.filter((_, i) => i % predStep === 0 || i === forecasts.length - 1).slice(0, 8)
    : forecasts;
  const predValues = sampledForecasts.map(f => Math.round(f.predicted_aqi));
  const predLabels = sampledForecasts.map(f => `+${f.step_ahead_hours}h`);

  const predChartData = predValues.length > 1 ? {
    labels: predLabels,
    datasets: [
      { data: predValues, strokeWidth: 2, color: (o = 1) => `rgba(56, 189, 248, ${o})` },
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
        {/* Header Title with Real Date & Minute Clock */}
        <View style={[styles.headerBar, { paddingTop: Math.max(16, insets.top) }]}>
          <View>
            <Text style={styles.headerSubtitle}>{formattedDate}</Text>
            <Text style={styles.headerTitle}>Forecast & Analytics</Text>
          </View>
          <View style={styles.clockPill}>
            <View style={styles.clockDot} />
            <Text style={styles.clockText}>{formattedClock}</Text>
          </View>
        </View>

        {/* Failed background refresh banner */}
        {(pred.error || hist.error || stationsFetch.error) && (predChartData || histChartData) && (
          <ErrorBanner message={pred.error || hist.error || stationsFetch.error} onRetry={onRefresh} />
        )}

        {/* Dynamic Station Filter Tabs */}
        {stationList.length > 0 && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipRow}
          >
            {stationList.map(s => {
              const sId = s.station_id || s.id;
              const active = currentStationId === sId;
              return (
                <TouchableOpacity
                  key={sId}
                  style={[styles.chip, active && styles.chipActive]}
                  onPress={() => setSelectedStation(sId)}
                  activeOpacity={0.7}
                  accessibilityRole="tab"
                  accessibilityLabel={`Filter analytics to station ${s.name || sId}`}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]} numberOfLines={1}>
                    {s.name || sId}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        )}

        {/* 24-Hour ML Forecast Section */}
        <SectionHeader
          title="Predicted 24h Trend"
          subtitle={`Forecast horizon via ${pred.data?.model_used || 'Precomputed Model'}`}
        />
        {pred.loading ? (
          <View style={styles.chartPlaceholder}><LoadingCard message="Computing 24-hour forecast horizon..." /></View>
        ) : pred.error && !predChartData ? (
          <ErrorCard message={pred.error} onRetry={pred.refetch} />
        ) : predChartData ? (
          <View style={styles.card}>
            <LineChart
              data={predChartData}
              width={CHART_WIDTH}
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

            {/* Hourly Horizon Horizontal List with Target Time */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 14 }}>
              <View style={styles.forecastHourRow}>
                {forecasts.slice(0, 8).map((fc, i) => {
                  const targetD = fc.target_timestamp ? new Date(fc.target_timestamp) : null;
                  const timeStr = targetD
                    ? targetD.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
                    : `+${fc.step_ahead_hours}h`;
                  const low = fc.lower_bound ?? fc.confidence_lower ?? 0;
                  const high = fc.upper_bound ?? fc.confidence_upper ?? 0;
                  const cat = fc.category || fc.aqi_category || '--';

                  return (
                    <View key={i} style={[styles.forecastHourCard, { borderLeftColor: fc.color_hex || THEME.primary, borderLeftWidth: 3 }]}>
                      <Text style={styles.fhHour}>{timeStr}</Text>
                      <Text style={[styles.fhAqi, { color: fc.color_hex || THEME.primaryLight }]}>
                        {Math.round(fc.predicted_aqi)}
                      </Text>
                      <Text style={styles.fhCat} numberOfLines={1}>{cat}</Text>
                      <Text style={styles.fhBound}>
                        ±{Math.round(fc.expected_error_band ?? (high - low) / 2)}
                      </Text>
                    </View>
                  );
                })}
              </View>
            </ScrollView>
          </View>
        ) : (
          <EmptyCard
            title="Forecast Model Output Pending"
            message="Machine learning models have not produced multi-horizon predictions for this station coordinate yet."
            icon="trending-up-outline"
            actionLabel="Recalculate Predictions"
            onAction={pred.refetch}
          />
        )}

        {/* Historical 24-Hour Observation Section */}
        <SectionHeader
          title="Observed 24h Trend"
          subtitle={`Sensor measurements for ${stationList.find(s => (s.station_id || s.id) === currentStationId)?.name || currentStationId}`}
        />
        {hist.loading ? (
          <View style={styles.chartPlaceholder}><LoadingCard message="Retrieving station sensor history..." /></View>
        ) : hist.error && !histChartData ? (
          <ErrorCard message={hist.error} onRetry={hist.refetch} />
        ) : histChartData ? (
          <View style={styles.card}>
            <LineChart
              data={histChartData}
              width={CHART_WIDTH}
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
          <EmptyCard
            title="No Recent Station History"
            message="Ground sensor measurements have not been recorded for this station within the preceding 24-hour window."
            icon="time-outline"
            actionLabel="Reload Sensor History"
            onAction={hist.refetch}
          />
        )}

        {/* Model Transparency & Benchmark Evaluation */}
        {metrics && (
          <>
            <SectionHeader
              title="Benchmark Evaluation"
              subtitle="Holdout cross-validation comparison across candidate architectures"
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
                Errors reported in AQI index units. Evaluated using expanding-window TimeSeriesSplit cross-validation against persistence baseline.
              </Text>
            </View>
          </>
        )}

        {/* Rolling Forecast Verification (Continuous Model Monitoring) */}
        {verif.data && (
          <>
            <SectionHeader
              title="Forecast Verification (Monitoring)"
              subtitle="Realized ground-truth error across horizons (Past 7 Days)"
            />
            <View style={styles.card}>
              <View style={styles.champRow}>
                <Ionicons name="analytics-outline" size={18} color={THEME.primaryLight} />
                <Text style={styles.champLabel}>Verified Observations:</Text>
                <Text style={styles.champVal}>{verif.data.total_verified || 0} evaluated</Text>
              </View>

              {verif.data.total_verified > 0 && Object.keys(verif.data.horizons || {}).length > 0 ? (
                <>
                  <View style={styles.metricsTable}>
                    <View style={styles.tableHeader}>
                      <Text style={[styles.tcell, styles.theader, { flex: 1.5 }]}>Horizon</Text>
                      <Text style={[styles.tcell, styles.theader]}>Samples</Text>
                      <Text style={[styles.tcell, styles.theader]}>MAE</Text>
                      <Text style={[styles.tcell, styles.theader]}>RMSE</Text>
                      <Text style={[styles.tcell, styles.theader]}>Bias</Text>
                    </View>
                    {Object.entries(verif.data.horizons).map(([hKey, hData], i) => (
                      <View key={hKey} style={[styles.tableRow, i % 2 === 1 && styles.tableRowAlt]}>
                        <Text style={[styles.tcell, { flex: 1.5, color: THEME.primaryLight, fontWeight: '600' }]}>
                          +{hData.horizon}h
                        </Text>
                        <Text style={styles.tcell}>{hData.samples}</Text>
                        <Text style={styles.tcell}>{hData.mae}</Text>
                        <Text style={styles.tcell}>{hData.rmse}</Text>
                        <Text style={[styles.tcell, { color: hData.bias > 0 ? THEME.warning : THEME.textSecondary }]}>
                          {hData.bias > 0 ? `+${hData.bias}` : hData.bias}
                        </Text>
                      </View>
                    ))}
                  </View>
                  <Text style={styles.metricsNote}>
                    Continuous monitoring compares past model predictions with CPCB ground measurements recorded once target timestamps elapse.
                  </Text>
                </>
              ) : (
                <Text style={[styles.metricsNote, { fontStyle: 'italic', marginTop: 8 }]}>
                  Awaiting elapsed target timestamps to compute rolling verification metrics against incoming CPCB ground observations.
                </Text>
              )}
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  clockPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: THEME.surface,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: THEME.radiusFull,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  clockDot: {
    width: 6,
    height: 6,
    borderRadius: THEME.radiusFull,
    backgroundColor: THEME.primaryLight,
  },
  clockText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.captionBold,
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
  chipRow: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    minHeight: 36,
    justifyContent: 'center',
    alignItems: 'center',
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
    ...TYPOGRAPHY.bodySecondary,
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
    borderRadius: THEME.radiusFull,
  },
  tLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.subBadge,
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
    minWidth: 68,
    gap: 3,
  },
  fhHour: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  fhAqi: {
    fontSize: 16,
    fontWeight: '800',
  },
  fhCat: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.subBadge,
    maxWidth: 64,
  },
  fhBound: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.subBadge,
  },
  champRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  champLabel: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.bodySecondary,
    fontWeight: '600',
  },
  champVal: {
    color: THEME.textPrimary,
    ...TYPOGRAPHY.bodyMedium,
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
    ...TYPOGRAPHY.caption,
  },
  theader: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  metricsNote: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
    marginTop: 10,
  },
  noData: {
    color: THEME.textMuted,
    textAlign: 'center',
    padding: 20,
    ...TYPOGRAPHY.bodySecondary,
  },
});
