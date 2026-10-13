/**
 * Tab 2: GIS Map Screen
 * Displays Mumbai monitoring stations and IDW spatial interpolation.
 * Uses a bulletproof, self-contained HTML renderer directly inside WebView,
 * eliminating network iframe / X-Frame-Options failures.
 */
import React, { useState, useMemo } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { ENDPOINTS, THEME } from '../config';

export default function MapScreen() {
  const [key, setKey] = useState(1);
  const [filterHotspots, setFilterHotspots] = useState(true);

  // Build the complete Leaflet map HTML inline to avoid external embedding failures
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

        .pin {
            display:flex; align-items:center; justify-content:center;
            width:40px; height:40px; border-radius:50%;
            font-weight:800; font-size:13px; color:#ffffff;
            border:2.5px solid #ffffff; box-shadow:0 4px 12px rgba(0,0,0,0.5);
            cursor:pointer; transition:transform 0.15s ease;
        }
        .pin.dark { color:#090d16 !important; border-color:#090d16 !important; }
        .pin:hover { transform:scale(1.15); }

        .popup-card {
            background:#111827; color:#f8fafc; padding:12px;
            border-radius:12px; min-width:200px;
        }
        .popup-title { font-size:13px; font-weight:700; margin-bottom:4px; }
        .popup-badge {
            display:inline-block; padding:3px 8px; border-radius:6px;
            font-size:11px; font-weight:700; color:#fff; margin-bottom:8px;
        }
        .popup-grid {
            display:grid; grid-template-columns:1fr 1fr; gap:6px;
            background:#090d16; padding:8px; border-radius:8px; font-size:11px;
        }
        .popup-cell { color:#94a3b8; }
        .popup-cell b { display:block; color:#f8fafc; font-size:12px; margin-top:2px; }

        .leaflet-popup-content-wrapper {
            background:#111827 !important; border-radius:12px !important;
            border:1px solid #1f293d; box-shadow:0 12px 24px rgba(0,0,0,0.6) !important;
            padding:0 !important;
        }
        .leaflet-popup-tip { background:#111827 !important; }
        .leaflet-popup-content { margin:0 !important; }
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map', {
            center: [19.0760, 72.8777],
            zoom: 11,
            zoomControl: false,
            attributionControl: false
        });

        // Crisp OpenStreetMap Basemap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18
        }).addTo(map);

        const stationsLayer = L.featureGroup().addTo(map);
        const hotspotsLayer = L.featureGroup().addTo(map);

        fetch('${ENDPOINTS.mapLayers}?threshold=140')
            .then(r => r.json())
            .then(data => {
                const stations = data.stations_geojson && data.stations_geojson.features || [];
                const hotspots = data.hotspots_geojson && data.hotspots_geojson.features || [];

                // Render Stations
                stations.forEach(st => {
                    const [lon, lat] = st.geometry.coordinates;
                    const p = st.properties;
                    const aqi = Math.round(p.current_aqi || 0);
                    const color = p.color_hex || '#0284c7';
                    const isDark = p.category === 'Moderate' || p.category === 'Satisfactory' || color === '#FFFF00' || color === '#F59E0B';

                    const icon = L.divIcon({
                        className: '',
                        html: '<div class="pin ' + (isDark ? 'dark' : '') + '" style="background:' + color + '">' + aqi + '</div>',
                        iconSize: [40, 40],
                        iconAnchor: [20, 20]
                    });

                    const popup = '<div class="popup-card">' +
                        '<div class="popup-title">' + p.name + '</div>' +
                        '<div class="popup-badge" style="background:' + color + ';' + (isDark ? 'color:#090d16;' : '') + '">' + aqi + ' · ' + p.category + '</div>' +
                        '<div class="popup-grid">' +
                            '<div class="popup-cell">PM2.5<b>' + (p.pm25 != null ? p.pm25 : '--') + ' µg</b></div>' +
                            '<div class="popup-cell">PM10<b>' + (p.pm10 != null ? p.pm10 : '--') + ' µg</b></div>' +
                            '<div class="popup-cell">Temp<b>' + (p.temperature != null ? p.temperature + '°C' : '--') + '</b></div>' +
                            '<div class="popup-cell">Wind<b>' + (p.wind_speed != null ? p.wind_speed + ' km/h' : '--') + '</b></div>' +
                        '</div>' +
                    '</div>';

                    L.marker([lat, lon], { icon }).bindPopup(popup).addTo(stationsLayer);
                });

                // Render Land-Bounded Hotspots
                const pts = hotspots.filter(h => h.geometry && h.geometry.type === 'Point');
                pts.forEach(pt => {
                    const [lon, lat] = pt.geometry.coordinates;
                    const p = pt.properties;
                    const color = p.color_hex || '#ea580c';

                    L.circle([lat, lon], {
                        radius: 1200,
                        stroke: false,
                        fillColor: color,
                        fillOpacity: 0.12,
                        interactive: false
                    }).addTo(hotspotsLayer);

                    L.circle([lat, lon], {
                        radius: 650,
                        color: color,
                        weight: 1,
                        opacity: 0.4,
                        fillColor: color,
                        fillOpacity: 0.25,
                        interactive: true
                    }).bindTooltip('Interpolated AQI: ' + Math.round(p.interpolated_aqi) + ' (' + p.category + ')').addTo(hotspotsLayer);
                });
            })
            .catch(err => console.error('Map loading error:', err));
    </script>
</body>
</html>
  `, [key]);

  return (
    <View style={styles.container}>
      {/* Sleek Mobile Control Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Spatial GIS Map</Text>
          <Text style={styles.headerSubtitle}>Real-time ground sensors and IDW hotspot contours</Text>
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

      {/* Embedded Map Canvas */}
      <View style={styles.mapWrapper}>
        <WebView
          key={key}
          source={{ html: mapHtml }}
          style={styles.webview}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          originWhitelist={['*']}
          startInLoadingState={true}
          renderLoading={() => (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color={THEME.primaryLight} />
              <Text style={styles.loadingText}>Loading spatial map...</Text>
            </View>
          )}
        />
      </View>

      {/* Legend Footer */}
      <View style={styles.legendBar}>
        <Text style={styles.legendLabel}>CPCB Scale</Text>
        <View style={styles.legendScale}>
          <View style={[styles.legendBlock, { backgroundColor: '#15803d' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#65a30d' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#d97706' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#ea580c' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#dc2626' }]} />
          <View style={[styles.legendBlock, { backgroundColor: '#991b1b' }]} />
        </View>
        <View style={styles.legendMarks}>
          <Text style={styles.legendMarkText}>0 Good</Text>
          <Text style={styles.legendMarkText}>200 Moderate</Text>
          <Text style={styles.legendMarkText}>500 Severe</Text>
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
    paddingBottom: 10,
    backgroundColor: THEME.bg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
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
  legendLabel: {
    color: THEME.textMuted,
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  legendScale: {
    flexDirection: 'row',
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
    gap: 2,
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
    fontSize: 10,
  },
});
