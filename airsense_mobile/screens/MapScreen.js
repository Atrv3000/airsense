/**
 * Tab 2: Spatial GIS Map Screen
 * Displays a continuous AQI heatmap gradient across Greater Mumbai,
 * high-contrast CAAQMS monitoring station pins (measured vs modelled),
 * active pollution hotspot polygons (AQI >= 201), and spatial estimation uncertainty.
 * Bundled with local Leaflet and Leaflet-Heat assets for instant offline-first rendering.
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity, ScrollView } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useUnifiedMapLayers } from '../hooks/useApi';
import { MAP_HTML } from '../assets/mapHtml';
import { ErrorBanner } from '../components/SharedComponents';
import { THEME, TYPOGRAPHY } from '../config';

const HORIZONS = [
  { id: 'current', label: 'Current' },
  { id: '3', label: '+3h' },
  { id: '6', label: '+6h' },
  { id: '24', label: '+24h' },
];

export default function MapScreen() {
  const insets = useSafeAreaInsets();
  const webViewRef = useRef(null);
  const mapReadyRef = useRef(false);

  const [horizon, setHorizon] = useState('current');
  const [showStations, setShowStations] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showHotspots, setShowHotspots] = useState(true);
  const [showUncertainty, setShowUncertainty] = useState(false);

  const [aqiRange, setAqiRange] = useState({ min: 40, max: 280, count: 16, hotspotsCount: 0 });
  const [mapError, setMapError] = useState(null);

  const { data: mapData, isLoading, error: fetchError, refetch } = useUnifiedMapLayers();

  const pushLayersToMap = useCallback(() => {
    if (!mapReadyRef.current || !webViewRef.current || !mapData) return;
    const payload = {
      type: 'SET_LAYERS',
      data: mapData,
      horizon,
      showStations,
      showHeatmap,
      showHotspots,
      showUncertainty,
    };
    const script = `window.updateMapLayers && window.updateMapLayers(${JSON.stringify(payload)}); true;`;
    webViewRef.current.injectJavaScript(script);
  }, [mapData, horizon, showStations, showHeatmap, showHotspots, showUncertainty]);

  useEffect(() => {
    pushLayersToMap();
  }, [pushLayersToMap]);

  const handleMessage = useCallback((event) => {
    try {
      const payload = JSON.parse(event.nativeEvent.data);
      if (payload && payload.type === 'MAP_READY') {
        mapReadyRef.current = true;
        pushLayersToMap();
      } else if (payload && payload.type === 'RANGE_UPDATE') {
        setMapError(null);
        setAqiRange({
          min: payload.minAqi ?? 0,
          max: payload.maxAqi ?? 250,
          count: payload.stationCount ?? 16,
          hotspotsCount: payload.hotspotsCount ?? 0,
        });
      } else if (payload && payload.type === 'MAP_ERROR') {
        setMapError(payload.error || 'Failed to render spatial GIS layers');
      }
    } catch (e) {
      // Ignore non-json messages
    }
  }, [pushLayersToMap]);

  const activeError = fetchError ? (fetchError.message || 'Failed to fetch map data') : mapError;

  return (
    <View style={styles.container}>
      {/* Mobile Control Header */}
      <View style={[styles.header, { paddingTop: Math.max(16, insets.top) }]}>
        <View>
          <Text style={styles.headerTitle}>Spatial GIS Map</Text>
          <Text style={styles.headerSubtitle}>
            Continuous AQI gradient, station pins & hotspot clusters
          </Text>
        </View>
        <TouchableOpacity
          style={styles.reloadBtn}
          onPress={() => {
            setMapError(null);
            refetch().then(() => pushLayersToMap());
          }}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Reload spatial map layers"
        >
          <Ionicons name="refresh-outline" size={16} color={THEME.textSecondary} />
          <Text style={styles.reloadText}>Reload</Text>
        </TouchableOpacity>
      </View>

      {/* Map Error Banner with Retry */}
      {activeError && (
        <ErrorBanner
          message={activeError}
          onRetry={() => {
            setMapError(null);
            refetch().then(() => pushLayersToMap());
          }}
        />
      )}

      {/* Horizon Selector Bar */}
      <View style={styles.horizonBar}>
        <Text style={styles.barLabel}>Horizon:</Text>
        <View style={styles.horizonButtons}>
          {HORIZONS.map((h) => {
            const active = horizon === h.id;
            return (
              <TouchableOpacity
                key={h.id}
                style={[styles.horizonBtn, active && styles.horizonBtnActive]}
                onPress={() => setHorizon(h.id)}
                activeOpacity={0.7}
                accessibilityRole="tab"
                accessibilityLabel={`Forecast horizon: ${h.label}`}
              >
                <Text style={[styles.horizonBtnText, active && styles.horizonBtnTextActive]}>
                  {h.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Layer Visibility Selector */}
      <View style={styles.layerBar}>
        <Text style={styles.barLabel}>Layers:</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.layerButtons}>
          <TouchableOpacity
            style={[styles.layerChip, showStations && styles.layerChipActive]}
            onPress={() => setShowStations(v => !v)}
            activeOpacity={0.7}
          >
            <Ionicons name="radio" size={12} color={showStations ? '#ffffff' : THEME.textMuted} />
            <Text style={[styles.layerChipText, showStations && styles.layerChipTextActive]}>
              Stations ({aqiRange.count})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.layerChip, showHeatmap && styles.layerChipActive]}
            onPress={() => setShowHeatmap(v => !v)}
            activeOpacity={0.7}
          >
            <Ionicons name="color-palette-outline" size={12} color={showHeatmap ? '#ffffff' : THEME.textMuted} />
            <Text style={[styles.layerChipText, showHeatmap && styles.layerChipTextActive]}>
              Heatmap
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.layerChip, showHotspots && styles.layerChipActive]}
            onPress={() => setShowHotspots(v => !v)}
            activeOpacity={0.7}
          >
            <Ionicons name="warning-outline" size={12} color={showHotspots ? '#ffffff' : THEME.textMuted} />
            <Text style={[styles.layerChipText, showHotspots && styles.layerChipTextActive]}>
              Hotspots (≥201)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.layerChip, showUncertainty && styles.layerChipActive]}
            onPress={() => setShowUncertainty(v => !v)}
            activeOpacity={0.7}
          >
            <Ionicons name="analytics-outline" size={12} color={showUncertainty ? '#ffffff' : THEME.textMuted} />
            <Text style={[styles.layerChipText, showUncertainty && styles.layerChipTextActive]}>
              Uncertainty Grid
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </View>

      {/* Embedded Map Canvas */}
      <View style={styles.mapWrapper}>
        <WebView
          ref={webViewRef}
          key="airsense-map-webview"
          source={{ html: MAP_HTML }}
          style={styles.webview}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          originWhitelist={['*']}
          onMessage={handleMessage}
          onLoadEnd={() => {
            mapReadyRef.current = true;
            pushLayersToMap();
          }}
          startInLoadingState={true}
          renderLoading={() => (
            <View style={styles.loadingContainer} accessibilityRole="progressbar" accessibilityLabel="Rendering spatial AQI gradient">
              <ActivityIndicator size="small" color={THEME.primaryLight} />
              <Text style={styles.loadingText}>Rendering spatial AQI gradient & station pins...</Text>
            </View>
          )}
        />
      </View>

      {/* Heatmap Legend Footer */}
      <View style={styles.legendBar}>
        <View style={styles.legendHeaderRow}>
          <Text style={styles.legendLabel}>Spatial Classification</Text>
          <Text style={styles.legendSubtext}>
            AQI Range: {aqiRange.min} → {aqiRange.max}
          </Text>
        </View>

        {/* Continuous Color Gradient Scale */}
        <View style={styles.legendScale}>
          <View style={[styles.legendBlock, { backgroundColor: '#1e40af' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#0284c7' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#eab308' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#f97316' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#dc2626' }]} />
        </View>

        <View style={styles.legendMarks}>
          <Text style={styles.legendMarkText}>Good (≤50)</Text>
          <Text style={styles.legendMarkText}>Moderate (101-200)</Text>
          <Text style={styles.legendMarkText}>Poor/Severe (≥201)</Text>
        </View>

        {/* Monitoring Station Marker Item */}
        <View style={styles.legendStationRow}>
          <View style={styles.legendStationIndicator}>
            <View style={[styles.legendStationDot, { borderColor: '#10b981' }]} />
            <Text style={styles.legendStationText}>Ground Measured</Text>
          </View>
          <View style={styles.legendStationIndicator}>
            <View style={[styles.legendStationDot, { borderColor: '#f59e0b' }]} />
            <Text style={styles.legendStationText}>Stale Ground</Text>
          </View>
          <View style={styles.legendStationIndicator}>
            <View style={[styles.legendStationDot, { borderColor: '#38bdf8', borderStyle: 'dashed' }]} />
            <Text style={styles.legendStationText}>Modelled</Text>
          </View>
          <View style={styles.legendStationIndicator}>
            <View style={[styles.legendStationDot, { borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.4)' }]} />
            <Text style={styles.legendStationText}>Hotspot (≥201)</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.bg,
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    backgroundColor: THEME.bg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    color: THEME.textPrimary,
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: -0.3,
  },
  headerSubtitle: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.caption,
    marginTop: 2,
  },
  reloadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: THEME.surface,
    paddingHorizontal: 12,
    paddingVertical: 8,
    minHeight: 36,
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  reloadText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.captionBold,
  },
  horizonBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
    backgroundColor: THEME.surface,
    borderTopWidth: 1,
    borderColor: THEME.border,
    gap: 10,
  },
  layerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
    backgroundColor: THEME.surface,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: THEME.border,
    gap: 10,
  },
  barLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
    minWidth: 50,
  },
  horizonButtons: {
    flexDirection: 'row',
    gap: 6,
    flex: 1,
  },
  horizonBtn: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    minHeight: 30,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: THEME.radiusXs,
    backgroundColor: THEME.surfaceElevated,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  horizonBtnActive: {
    backgroundColor: THEME.primary,
    borderColor: THEME.primary,
  },
  horizonBtnText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.captionBold,
  },
  horizonBtnTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  layerButtons: {
    flexDirection: 'row',
    gap: 6,
    paddingVertical: 2,
  },
  layerChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: THEME.radiusXs,
    backgroundColor: THEME.surfaceElevated,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  layerChipActive: {
    backgroundColor: THEME.primaryDark,
    borderColor: THEME.primary,
  },
  layerChipText: {
    color: THEME.textMuted,
    fontSize: 11,
    fontWeight: '600',
  },
  layerChipTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  mapWrapper: {
    flex: 1,
    backgroundColor: THEME.bg,
  },
  webview: {
    flex: 1,
    backgroundColor: THEME.bg,
  },
  loadingContainer: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: THEME.bg,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  loadingText: {
    color: THEME.textSecondary,
    fontSize: 12,
  },
  legendBar: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: THEME.surface,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    gap: 5,
  },
  legendHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  legendLabel: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.overline,
  },
  legendSubtext: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.subBadge,
  },
  legendScale: {
    flexDirection: 'row',
    height: 5,
    borderRadius: THEME.radiusXs,
    overflow: 'hidden',
  },
  legendBlock: {
    flex: 1,
  },
  legendMarks: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  legendMarkText: {
    color: THEME.textMuted,
    ...TYPOGRAPHY.subBadge,
  },
  legendStationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 5,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    marginTop: 2,
  },
  legendStationIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  legendStationDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: THEME.bg,
    borderWidth: 1.5,
  },
  legendStationText: {
    color: THEME.textSecondary,
    ...TYPOGRAPHY.subBadge,
  },
});
