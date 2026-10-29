/**
 * Tab 2: Spatial GIS Map Screen
 * Displays a continuous red-to-blue AQI heatmap gradient across Greater Mumbai
 * along with high-contrast monitoring station beacon pins and dynamic legend.
 *
 * Visual hierarchy:
 * - Heatmap Gradient: Spatially continuous IDW/Kriging surface (Red: Highest AQI/Worst -> Blue: Lowest AQI/Best)
 * - Monitoring Station Markers: High-contrast beacon pins at exact station coordinates (tap for metadata)
 * - Dynamic Map Legend: Shows exact numeric bounds and station marker identifier
 * - Horizon Toggling: Current, +3h, +6h, +24h
 */
import React, { useState, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { ENDPOINTS, THEME, HOTSPOT_THRESHOLD } from '../config';

const HORIZONS = [
  { id: 'current', label: 'Current' },
  { id: '3', label: '+3h' },
  { id: '6', label: '+6h' },
  { id: '24', label: '+24h' },
];

export default function MapScreen() {
  const [key, setKey] = useState(1);
  const [horizon, setHorizon] = useState('current');
  const [aqiRange, setAqiRange] = useState({ min: 40, max: 280, count: 15 });

  const handleMessage = useCallback((event) => {
    try {
      const payload = JSON.parse(event.nativeEvent.data);
      if (payload && payload.type === 'RANGE_UPDATE') {
        setAqiRange({
          min: payload.minAqi ?? 0,
          max: payload.maxAqi ?? 250,
          count: payload.stationCount ?? 15,
        });
      }
    } catch (e) {
      // Ignore non-json WebView messages
    }
  }, []);

  // Build the complete Leaflet map HTML with embedded continuous heatmap
  const mapHtml = useMemo(() => `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background:#090d16; color:#f8fafc; overflow:hidden; }
        #map { width:100vw; height:100vh; background:#090d16; }

        /* Station Marker Styling - Distinct high-contrast beacon pin */
        .station-pin-wrap {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }
        .station-beacon {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #090d16;
            border: 2px solid #38bdf8;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4), 0 3px 8px rgba(0,0,0,0.8);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .station-beacon.unavailable {
            border-color: #64748b;
            box-shadow: 0 2px 6px rgba(0,0,0,0.6);
        }
        .station-pin-wrap:hover .station-beacon,
        .station-pin-wrap:active .station-beacon {
            transform: scale(1.15);
            box-shadow: 0 0 14px rgba(56, 189, 248, 0.8);
        }
        .station-stem {
            width: 2px;
            height: 6px;
            background: #38bdf8;
            box-shadow: 0 1px 3px rgba(0,0,0,0.6);
        }
        .station-beacon.unavailable + .station-stem {
            background: #64748b;
        }

        /* Popup Cards */
        .popup-card {
            background: #0f172a;
            color: #f8fafc;
            padding: 14px;
            border-radius: 12px;
            min-width: 220px;
            max-width: 280px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.7);
        }
        .popup-title {
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 2px;
            color: #f8fafc;
            line-height: 1.3;
        }
        .popup-subid {
            font-size: 11px;
            color: #38bdf8;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .popup-feed {
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.3px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .popup-aqi-box {
            display: flex;
            align-items: baseline;
            gap: 8px;
            background: #1e293b;
            padding: 8px 10px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .popup-aqi-val {
            font-size: 24px;
            font-weight: 800;
            color: #f8fafc;
        }
        .popup-aqi-meta {
            display: flex;
            flex-direction: column;
        }
        .popup-cat-label {
            font-size: 12px;
            font-weight: 700;
        }
        .popup-horizon-tag {
            font-size: 10px;
            color: #94a3b8;
        }
        .popup-unavailable {
            background: #1e293b;
            padding: 8px 10px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .popup-unavail-title {
            font-size: 12px;
            font-weight: 700;
            color: #f87171;
            display: block;
        }
        .popup-unavail-desc {
            font-size: 10px;
            color: #94a3b8;
            display: block;
            margin-top: 2px;
        }
        .popup-time {
            font-size: 10px;
            color: #94a3b8;
            margin-bottom: 8px;
        }
        .popup-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            background: #090d16;
            padding: 8px;
            border-radius: 8px;
            font-size: 10px;
        }
        .popup-cell { color: #94a3b8; }
        .popup-cell b { display: block; color: #f8fafc; font-size: 11px; margin-top: 1px; }

        .leaflet-popup-content-wrapper {
            background: #0f172a !important;
            border-radius: 12px !important;
            border: 1px solid #1e293b;
            padding: 0 !important;
        }
        .leaflet-popup-tip { background: #0f172a !important; }
        .leaflet-popup-content { margin: 0 !important; }

        /* On-Map Floating Watermark Legend */
        .map-legend-overlay {
            position: absolute;
            top: 14px;
            right: 14px;
            z-index: 999;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 10px;
            color: #f8fafc;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
            max-width: 170px;
        }
        .map-legend-title {
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            color: #94a3b8;
            margin-bottom: 4px;
        }
        .map-legend-bar {
            height: 6px;
            border-radius: 3px;
            background: linear-gradient(to right, #1e40af, #0284c7, #eab308, #f97316, #dc2626);
            margin-bottom: 4px;
        }
        .map-legend-endpoints {
            display: flex;
            justify-content: space-between;
            font-size: 9px;
            font-weight: 600;
            color: #cbd5e1;
        }
        .map-legend-station-info {
            display: flex;
            align-items: center;
            gap: 5px;
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px solid rgba(255,255,255,0.1);
            color: #94a3b8;
            font-size: 9px;
        }
        .station-dot-sample {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #090d16;
            border: 1.5px solid #38bdf8;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="map-legend-overlay" id="mapLegend">
        <div class="map-legend-title">AQI Gradient</div>
        <div class="map-legend-bar"></div>
        <div class="map-legend-endpoints">
            <span id="legendMinLabel">Blue (Best)</span>
            <span id="legendMaxLabel">Red (Worst)</span>
        </div>
        <div class="map-legend-station-info">
            <div class="station-dot-sample"></div>
            <span id="legendStationCount">CAAQMS Station</span>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        // Initialize base Leaflet map
        const map = L.map('map', {
            center: [19.0760, 72.8777],
            zoom: 11,
            zoomControl: false,
            attributionControl: false
        });

        // High-contrast dark basemap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18
        }).addTo(map);

        const stationsLayer = L.featureGroup().addTo(map);
        let heatLayer = null;

        const activeHorizon = '${horizon}';

        fetch('${ENDPOINTS.mapLayers}?threshold=${HOTSPOT_THRESHOLD}')
            .then(r => r.json())
            .then(data => {
                const stations = (data.stations_geojson && data.stations_geojson.features) || [];

                // 1. Determine Interpolated Grid for Active Horizon
                let gridFeatures = [];
                if (activeHorizon === 'current') {
                    gridFeatures = (data.grid_geojson && data.grid_geojson.features) || [];
                } else {
                    const hKey = 'plus_' + activeHorizon + 'h';
                    if (data.predicted_grids && data.predicted_grids[hKey]) {
                        gridFeatures = data.predicted_grids[hKey].features || [];
                    }
                }

                // 2. Build Source Points for Heatmap Overlay
                let sourcePoints = [];
                if (gridFeatures.length > 0) {
                    sourcePoints = gridFeatures.map(f => {
                        const [lon, lat] = f.geometry.coordinates;
                        return { lat, lon, aqi: f.properties.interpolated_aqi };
                    });
                } else {
                    // Graceful fallback to stations with valid AQIs
                    stations.forEach(st => {
                        const [lon, lat] = st.geometry.coordinates;
                        const p = st.properties;
                        let aqi = p.current_aqi;
                        if (activeHorizon !== 'current' && p.forecast_24h) {
                            const hInt = parseInt(activeHorizon, 10);
                            const fc = p.forecast_24h.find(f => f.step_ahead_hours === hInt);
                            if (fc && fc.predicted_aqi != null) aqi = fc.predicted_aqi;
                        }
                        if (aqi != null && !isNaN(aqi)) {
                            sourcePoints.push({ lat, lon, aqi });
                        }
                    });
                }

                // 3. Compute Dynamic AQI Range Across Active Snapshot
                let minAqi = Infinity;
                let maxAqi = -Infinity;
                sourcePoints.forEach(pt => {
                    if (pt.aqi != null && !isNaN(pt.aqi)) {
                        if (pt.aqi < minAqi) minAqi = pt.aqi;
                        if (pt.aqi > maxAqi) maxAqi = pt.aqi;
                    }
                });
                if (!isFinite(minAqi)) { minAqi = 40; maxAqi = 250; }
                if (maxAqi <= minAqi) { maxAqi = minAqi + 50; }

                // 4. Render Spatially Continuous Red-to-Blue Heatmap
                // Scale: 0.0 -> Deep Blue (Best AQI) to 1.0 -> Red (Worst AQI)
                const heatPoints = sourcePoints.map(pt => {
                    const norm = Math.max(0.01, Math.min(1.0, (pt.aqi - minAqi) / (maxAqi - minAqi)));
                    return [pt.lat, pt.lon, norm];
                });

                if (window.L && L.heatLayer && heatPoints.length > 0) {
                    if (heatLayer) {
                        map.removeLayer(heatLayer);
                    }
                    heatLayer = L.heatLayer(heatPoints, {
                        minOpacity: 0.40,
                        maxZoom: 14,
                        radius: 34,
                        blur: 24,
                        max: 1.0,
                        gradient: {
                            0.0:  '#1e40af', // Deep Blue (Lowest AQI / Best air quality)
                            0.25: '#0284c7', // Light Blue / Cyan
                            0.5:  '#eab308', // Warm Yellow
                            0.75: '#f97316', // Orange
                            1.0:  '#dc2626'  // Red (Highest AQI / Worst air quality)
                        }
                    }).addTo(map);
                }

                // 5. Render Distinct High-Contrast Markers for Every Monitoring Station
                const seenStationIds = new Set();
                let renderedStationCount = 0;

                stations.forEach(st => {
                    const [lon, lat] = st.geometry.coordinates;
                    const p = st.properties || {};
                    const stationId = p.station_id || (lon + '_' + lat);

                    // Prevent duplicate station markers using stable station IDs
                    if (seenStationIds.has(stationId)) return;
                    seenStationIds.add(stationId);
                    renderedStationCount++;

                    let displayAqi = (p.current_aqi != null && !isNaN(p.current_aqi)) ? Math.round(p.current_aqi) : null;
                    let displayCat = p.category || 'Unavailable';
                    let isReadingAvailable = (displayAqi !== null);

                    if (activeHorizon !== 'current' && p.forecast_24h) {
                        const hInt = parseInt(activeHorizon, 10);
                        const fc = p.forecast_24h.find(f => f.step_ahead_hours === hInt);
                        if (fc && fc.predicted_aqi != null) {
                            displayAqi = Math.round(fc.predicted_aqi);
                            displayCat = fc.category || displayCat;
                            isReadingAvailable = true;
                        }
                    }

                    const isMeasured = p.is_measured;
                    const sourceText = p.source_label || (p.source === 'CPCB_OFFICIAL' ? 'Official CPCB CAAQMS' : (isMeasured ? 'Measured (OpenAQ)' : 'Modelled (Open-Meteo)'));
                    const sourceColor = p.source === 'CPCB_OFFICIAL' ? '#10b981' : (isMeasured ? '#34d399' : '#38bdf8');
                    const beaconClass = isReadingAvailable ? '' : 'unavailable';
                    const iconColor = isReadingAvailable ? '#38bdf8' : '#64748b';

                    const icon = L.divIcon({
                        className: '',
                        html: '<div class="station-pin-wrap">' +
                                '<div class="station-beacon ' + beaconClass + '">' +
                                    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="' + iconColor + '" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
                                        '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/>' +
                                        '<path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/>' +
                                        '<circle cx="12" cy="12" r="2.5" fill="' + iconColor + '"/>' +
                                        '<path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/>' +
                                        '<path d="M19.1 4.9C23 8.8 23 15.2 19.1 19.1"/>' +
                                    '</svg>' +
                                '</div>' +
                                '<div class="station-stem"></div>' +
                              '</div>',
                        iconSize: [28, 34],
                        iconAnchor: [14, 34],
                        popupAnchor: [0, -32]
                    });

                    // Build Detailed Metadata Popup
                    const formattedTime = p.recorded_at 
                        ? new Date(p.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
                        : 'Timestamp unavailable';

                    let aqiSectionHtml = '';
                    if (isReadingAvailable) {
                        const horizonPrefix = activeHorizon === 'current' ? 'Current AQI' : ('+' + activeHorizon + 'h Forecast');
                        aqiSectionHtml = '<div class="popup-aqi-box">' +
                            '<div class="popup-aqi-val">' + displayAqi + '</div>' +
                            '<div class="popup-aqi-meta">' +
                                '<span class="popup-cat-label" style="color:' + (p.color_hex || '#38bdf8') + '">' + displayCat + '</span>' +
                                '<span class="popup-horizon-tag">' + horizonPrefix + '</span>' +
                            '</div>' +
                        '</div>';
                    } else {
                        aqiSectionHtml = '<div class="popup-unavailable">' +
                            '<span class="popup-unavail-title">Reading Currently Unavailable</span>' +
                            '<span class="popup-unavail-desc">Station is registered and active, but no validated reading is reported for this hour.</span>' +
                        '</div>';
                    }

                    const popup = '<div class="popup-card">' +
                        '<div class="popup-title">' + p.name + '</div>' +
                        '<div class="popup-subid">' + stationId + (p.zone_type ? ' · ' + p.zone_type : '') + '</div>' +
                        '<div class="popup-feed" style="color:' + sourceColor + '">' + sourceText + '</div>' +
                        aqiSectionHtml +
                        '<div class="popup-time">🕒 ' + formattedTime + '</div>' +
                        '<div class="popup-grid">' +
                            '<div class="popup-cell">PM2.5<b>' + (p.pm25 != null ? p.pm25 + ' µg' : '--') + '</b></div>' +
                            '<div class="popup-cell">PM10<b>' + (p.pm10 != null ? p.pm10 + ' µg' : '--') + '</b></div>' +
                            '<div class="popup-cell">Temp<b>' + (p.temperature != null ? p.temperature + '°C' : '--') + '</b></div>' +
                            '<div class="popup-cell">Wind<b>' + (p.wind_speed != null ? p.wind_speed + ' km/h' : '--') + '</b></div>' +
                        '</div>' +
                    '</div>';

                    L.marker([lat, lon], { icon }).bindPopup(popup).addTo(stationsLayer);
                });

                // Update On-Map Legend Overlay
                const minEl = document.getElementById('legendMinLabel');
                const maxEl = document.getElementById('legendMaxLabel');
                const cntEl = document.getElementById('legendStationCount');
                if (minEl) minEl.innerText = 'Blue (' + Math.round(minAqi) + ')';
                if (maxEl) maxEl.innerText = 'Red (' + Math.round(maxAqi) + ')';
                if (cntEl) cntEl.innerText = renderedStationCount + ' Active Stations';

                // Post range update to React Native component
                if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {
                    window.ReactNativeWebView.postMessage(JSON.stringify({
                        type: 'RANGE_UPDATE',
                        minAqi: Math.round(minAqi),
                        maxAqi: Math.round(maxAqi),
                        stationCount: renderedStationCount
                    }));
                }
            })
            .catch(err => console.error('Map loading error:', err));
    </script>
</body>
</html>
  `, [key, horizon]);

  return (
    <View style={styles.container}>
      {/* Mobile Control Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Spatial GIS Map</Text>
          <Text style={styles.headerSubtitle}>
            Continuous AQI gradient & ground station pins
          </Text>
        </View>
        <TouchableOpacity
          style={styles.reloadBtn}
          onPress={() => setKey(k => k + 1)}
          activeOpacity={0.7}
        >
          <Ionicons name="refresh-outline" size={16} color={THEME.textSecondary} />
          <Text style={styles.reloadText}>Refresh</Text>
        </TouchableOpacity>
      </View>

      {/* Horizon Selector Bar */}
      <View style={styles.horizonBar}>
        <Text style={styles.horizonLabel}>Horizon:</Text>
        <View style={styles.horizonButtons}>
          {HORIZONS.map((h) => {
            const active = horizon === h.id;
            return (
              <TouchableOpacity
                key={h.id}
                style={[styles.horizonBtn, active && styles.horizonBtnActive]}
                onPress={() => setHorizon(h.id)}
                activeOpacity={0.7}
              >
                <Text style={[styles.horizonBtnText, active && styles.horizonBtnTextActive]}>
                  {h.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {/* Embedded Map Canvas */}
      <View style={styles.mapWrapper}>
        <WebView
          key={`${key}-${horizon}`}
          source={{ html: mapHtml }}
          style={styles.webview}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          originWhitelist={['*']}
          onMessage={handleMessage}
          startInLoadingState={true}
          renderLoading={() => (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color={THEME.primaryLight} />
              <Text style={styles.loadingText}>Rendering spatial gradient...</Text>
            </View>
          )}
        />
      </View>

      {/* Heatmap Legend Footer */}
      <View style={styles.legendBar}>
        <View style={styles.legendHeaderRow}>
          <Text style={styles.legendLabel}>AQI Heatmap Gradient</Text>
          <Text style={styles.legendSubtext}>
            Dynamic Range: {aqiRange.min} → {aqiRange.max} AQI
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
          <Text style={styles.legendMarkText}>Blue ({aqiRange.min} · Lowest/Best)</Text>
          <Text style={styles.legendMarkText}>Intermediate</Text>
          <Text style={styles.legendMarkText}>Red ({aqiRange.max} · Highest/Worst)</Text>
        </View>

        {/* Monitoring Station Marker Item */}
        <View style={styles.legendStationRow}>
          <View style={styles.legendStationIndicator}>
            <View style={styles.legendStationDot}>
              <Ionicons name="radio" size={11} color="#38bdf8" />
            </View>
            <Text style={styles.legendStationText}>
              Monitoring Station ({aqiRange.count} active pins · tap for metadata)
            </Text>
          </View>
          <Text style={styles.legendNormalizedNote}>Dynamic normalization</Text>
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
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  headerSubtitle: {
    color: THEME.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  reloadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: THEME.surface,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: THEME.radiusSm,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  reloadText: {
    color: THEME.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  horizonBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: THEME.surface,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: THEME.border,
    gap: 10,
  },
  horizonLabel: {
    color: THEME.textMuted,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  horizonButtons: {
    flexDirection: 'row',
    gap: 6,
    flex: 1,
  },
  horizonBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
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
    fontSize: 11,
    fontWeight: '600',
  },
  horizonBtnTextActive: {
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
    paddingVertical: 10,
    backgroundColor: THEME.surface,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    gap: 6,
  },
  legendHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  legendLabel: {
    color: THEME.textMuted,
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  legendSubtext: {
    color: THEME.textSecondary,
    fontSize: 10,
    fontWeight: '600',
  },
  legendScale: {
    flexDirection: 'row',
    height: 6,
    borderRadius: 3,
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
    fontSize: 9,
  },
  legendStationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: THEME.border,
    marginTop: 2,
  },
  legendStationIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendStationDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: THEME.bg,
    borderWidth: 1.5,
    borderColor: THEME.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  legendStationText: {
    color: THEME.textSecondary,
    fontSize: 10,
    fontWeight: '500',
  },
  legendNormalizedNote: {
    color: THEME.textMuted,
    fontSize: 9,
    fontStyle: 'italic',
  },
});
