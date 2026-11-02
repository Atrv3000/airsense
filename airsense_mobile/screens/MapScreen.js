/**
 * Tab 2: Spatial GIS Map Screen
 * Displays a continuous AQI heatmap gradient across Greater Mumbai,
 * high-contrast CAAQMS monitoring station pins (measured vs modelled),
 * active pollution hotspot polygons (AQI >= 201), and spatial estimation uncertainty.
 */
import React, { useState, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity, ScrollView } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ErrorBanner } from '../components/SharedComponents';
import { ENDPOINTS, THEME, HOTSPOT_THRESHOLD, TYPOGRAPHY, SPACING } from '../config';

const HORIZONS = [
  { id: 'current', label: 'Current' },
  { id: '3', label: '+3h' },
  { id: '6', label: '+6h' },
  { id: '24', label: '+24h' },
];

export default function MapScreen() {
  const insets = useSafeAreaInsets();
  const [key, setKey] = useState(1);
  const [horizon, setHorizon] = useState('current');
  const [showStations, setShowStations] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showHotspots, setShowHotspots] = useState(true);
  const [showUncertainty, setShowUncertainty] = useState(false);

  const [aqiRange, setAqiRange] = useState({ min: 40, max: 280, count: 16, hotspotsCount: 0 });
  const [mapError, setMapError] = useState(null);

  const handleMessage = useCallback((event) => {
    try {
      const payload = JSON.parse(event.nativeEvent.data);
      if (payload && payload.type === 'RANGE_UPDATE') {
        setMapError(null);
        setAqiRange({
          min: payload.minAqi ?? 0,
          max: payload.maxAqi ?? 250,
          count: payload.stationCount ?? 16,
          hotspotsCount: payload.hotspotsCount ?? 0,
        });
      } else if (payload && payload.type === 'MAP_ERROR') {
        setMapError(payload.error || 'Failed to retrieve spatial GIS layers');
      }
    } catch (e) {
      // Ignore non-json WebView messages
    }
  }, []);

  // Build the complete Leaflet map HTML with embedded layers
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

        /* Station Marker Styling */
        .station-pin-wrap {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }
        .station-beacon {
            min-width: 32px;
            height: 32px;
            padding: 0 4px;
            border-radius: 16px;
            background: #090d16;
            border: 2px solid #38bdf8;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 2px;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4), 0 3px 8px rgba(0,0,0,0.8);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .station-beacon.ground-measured {
            border-color: #10b981;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.5), 0 3px 8px rgba(0,0,0,0.8);
        }
        .station-beacon.modelled {
            border-color: #38bdf8;
            border-style: dashed;
            box-shadow: 0 0 8px rgba(56, 189, 248, 0.4), 0 3px 8px rgba(0,0,0,0.8);
        }
        .station-beacon.unavailable {
            border-color: #64748b;
            box-shadow: 0 2px 6px rgba(0,0,0,0.6);
        }
        .station-pin-wrap:hover .station-beacon,
        .station-pin-wrap:active .station-beacon {
            transform: scale(1.15);
        }
        .station-aqi-txt {
            font-size: 11px;
            font-weight: 800;
            color: #f8fafc;
            margin-left: 1px;
        }
        .station-stem {
            width: 2px;
            height: 5px;
            background: #38bdf8;
            box-shadow: 0 1px 3px rgba(0,0,0,0.6);
        }
        .station-beacon.ground-measured + .station-stem {
            background: #10b981;
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
            min-width: 230px;
            max-width: 290px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.8);
        }
        .popup-title {
            font-size: 14px;
            font-weight: 800;
            margin-bottom: 2px;
            color: #f8fafc;
            line-height: 1.3;
        }
        .popup-subid {
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .popup-badge-row {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }
        .popup-badge {
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.3px;
            text-transform: uppercase;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .badge-measured {
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }
        .badge-modelled {
            background: rgba(56, 189, 248, 0.2);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.4);
        }
        .badge-estimated {
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.4);
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
            background: rgba(15, 23, 42, 0.94);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 10px;
            color: #f8fafc;
            box-shadow: 0 4px 16px rgba(0,0,0,0.6);
            max-width: 180px;
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
        .map-legend-items {
            display: flex;
            flex-direction: column;
            gap: 4px;
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .legend-item-row {
            display: flex;
            align-items: center;
            gap: 6px;
            color: #cbd5e1;
            font-size: 9px;
        }
        .dot-measured {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            border: 1px solid #34d399;
        }
        .dot-modelled {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #38bdf8;
            border: 1px dashed #ffffff;
        }
        .dot-hotspot {
            width: 10px;
            height: 6px;
            border-radius: 2px;
            background: rgba(239, 68, 68, 0.5);
            border: 1px solid #ef4444;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="map-legend-overlay" id="mapLegend">
        <div class="map-legend-title">AQI Gradient</div>
        <div class="map-legend-bar"></div>
        <div class="map-legend-endpoints">
            <span id="legendMinLabel">Blue (Low)</span>
            <span id="legendMaxLabel">Red (High)</span>
        </div>
        <div class="map-legend-items">
            <div class="legend-item-row">
                <div class="dot-measured"></div>
                <span>Ground Measured CAAQMS</span>
            </div>
            <div class="legend-item-row">
                <div class="dot-modelled"></div>
                <span>Modelled Station</span>
            </div>
            <div class="legend-item-row">
                <div class="dot-hotspot"></div>
                <span>Hotspot (AQI ≥ 201)</span>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        // Layer visibility flags from React Native state
        const VIS_STATIONS = ${showStations};
        const VIS_HEATMAP = ${showHeatmap};
        const VIS_HOTSPOTS = ${showHotspots};
        const VIS_UNCERTAINTY = ${showUncertainty};
        const activeHorizon = '${horizon}';

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

        const stationsLayer = L.featureGroup();
        const hotspotsLayer = L.featureGroup();
        const uncertaintyLayer = L.featureGroup();
        let heatLayer = null;

        if (VIS_STATIONS) stationsLayer.addTo(map);
        if (VIS_HOTSPOTS) hotspotsLayer.addTo(map);
        if (VIS_UNCERTAINTY) uncertaintyLayer.addTo(map);

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
                        return {
                            lat, lon,
                            aqi: f.properties.interpolated_aqi,
                            uncertainty: f.properties.spatial_uncertainty || 12.0,
                            nearestStationKm: f.properties.nearest_station_km || 2.5
                        };
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
                            sourcePoints.push({ lat, lon, aqi, uncertainty: 10.0, nearestStationKm: 0.0 });
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

                // 4. Render Continuous Pollution Heatmap
                if (VIS_HEATMAP && window.L && L.heatLayer && sourcePoints.length > 0) {
                    const heatPoints = sourcePoints.map(pt => {
                        const norm = Math.max(0.01, Math.min(1.0, (pt.aqi - minAqi) / (maxAqi - minAqi)));
                        return [pt.lat, pt.lon, norm];
                    });
                    heatLayer = L.heatLayer(heatPoints, {
                        minOpacity: 0.40,
                        maxZoom: 14,
                        radius: 34,
                        blur: 24,
                        max: 1.0,
                        gradient: {
                            0.0:  '#1e40af', // Deep Blue (Lowest AQI / Best)
                            0.25: '#0284c7', // Cyan
                            0.5:  '#eab308', // Warm Yellow
                            0.75: '#f97316', // Orange
                            1.0:  '#dc2626'  // Red (Highest AQI / Worst)
                        }
                    }).addTo(map);
                }

                // 5. Render Hotspot Polygons (AQI >= 201)
                let activeHotspotsGeojson = null;
                if (activeHorizon === 'current') {
                    activeHotspotsGeojson = data.hotspots_geojson;
                } else {
                    const hKey = 'plus_' + activeHorizon + 'h';
                    if (data.predicted_hotspots && data.predicted_hotspots[hKey]) {
                        activeHotspotsGeojson = data.predicted_hotspots[hKey];
                    }
                }

                let hotspotCount = 0;
                if (activeHotspotsGeojson && activeHotspotsGeojson.features) {
                    activeHotspotsGeojson.features.forEach(feat => {
                        if (feat.geometry.type === 'Polygon') {
                            hotspotCount++;
                            const p = feat.properties || {};
                            const polyCoords = feat.geometry.coordinates[0].map(coord => [coord[1], coord[0]]); // [lat, lon]
                            const poly = L.polygon(polyCoords, {
                                color: p.color_hex || '#ef4444',
                                weight: 2,
                                dashArray: '4, 4',
                                fillColor: p.color_hex || '#ef4444',
                                fillOpacity: p.fill_opacity || 0.28
                            });

                            const popupContent = '<div class="popup-card">' +
                                '<div class="popup-title">Spatial Hotspot Area</div>' +
                                '<div class="popup-badge-row">' +
                                    '<span class="popup-badge badge-estimated">Spatially estimated</span>' +
                                    '<span class="popup-badge" style="background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.4)">AQI ≥ 201</span>' +
                                '</div>' +
                                '<div class="popup-aqi-box">' +
                                    '<div class="popup-aqi-val">' + Math.round(p.interpolated_aqi) + '</div>' +
                                    '<div class="popup-aqi-meta">' +
                                        '<span class="popup-cat-label" style="color:' + (p.color_hex || '#ef4444') + '">' + (p.category || 'Poor') + '</span>' +
                                        '<span class="popup-horizon-tag">Estimated Hotspot</span>' +
                                    '</div>' +
                                '</div>' +
                                '<div class="popup-grid">' +
                                    '<div class="popup-cell">Spatial Uncertainty<b>±' + (p.spatial_uncertainty != null ? p.spatial_uncertainty.toFixed(1) : '12.0') + ' AQI</b></div>' +
                                    '<div class="popup-cell">Nearest CAAQMS<b>' + (p.nearest_station_km != null ? p.nearest_station_km.toFixed(1) + ' km' : '2.5 km') + '</b></div>' +
                                '</div>' +
                            '</div>';

                            poly.bindPopup(popupContent);
                            hotspotsLayer.addLayer(poly);
                        }
                    });
                }

                // 6. Optional Spatial Uncertainty Grid
                if (VIS_UNCERTAINTY && sourcePoints.length > 0) {
                    sourcePoints.forEach(pt => {
                        const circle = L.circleMarker([pt.lat, pt.lon], {
                            radius: 12,
                            fillColor: pt.uncertainty > 20 ? '#dc2626' : (pt.uncertainty > 12 ? '#f59e0b' : '#10b981'),
                            color: '#ffffff',
                            weight: 1,
                            opacity: 0.6,
                            fillOpacity: 0.35
                        });
                        const uncertPopup = '<div class="popup-card">' +
                            '<div class="popup-title">Spatial Estimation Uncertainty</div>' +
                            '<div class="popup-badge-row">' +
                                '<span class="popup-badge badge-estimated">Kriging GP Model</span>' +
                            '</div>' +
                            '<div class="popup-grid">' +
                                '<div class="popup-cell">Estimated AQI<b>' + Math.round(pt.aqi) + '</b></div>' +
                                '<div class="popup-cell">Posterior Std<b>±' + pt.uncertainty.toFixed(1) + ' AQI</b></div>' +
                                '<div class="popup-cell" style="grid-column:span 2">Nearest CAAQMS Station<b>' + pt.nearestStationKm.toFixed(1) + ' km away</b></div>' +
                            '</div>' +
                        '</div>';
                        circle.bindPopup(uncertPopup);
                        uncertaintyLayer.addLayer(circle);
                    });
                }

                // 7. Render Monitoring Station Pins (Measured vs Modelled)
                const seenStationIds = new Set();
                let renderedStationCount = 0;

                stations.forEach(st => {
                    const [lon, lat] = st.geometry.coordinates;
                    const p = st.properties || {};
                    const stationId = p.station_id || (lon + '_' + lat);

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
                    const classification = p.data_classification || (isMeasured ? 'Ground measured' : 'Modelled');
                    const badgeClass = isMeasured ? 'badge-measured' : 'badge-modelled';
                    const beaconTypeClass = isReadingAvailable ? (isMeasured ? 'ground-measured' : 'modelled') : 'unavailable';

                    const icon = L.divIcon({
                        className: '',
                        html: '<div class="station-pin-wrap">' +
                                '<div class="station-beacon ' + beaconTypeClass + '">' +
                                    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="' + (isMeasured ? '#10b981' : '#38bdf8') + '" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
                                        '<circle cx="12" cy="12" r="3"/>' +
                                        '<path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>' +
                                    '</svg>' +
                                    (isReadingAvailable ? '<span class="station-aqi-txt">' + displayAqi + '</span>' : '') +
                                '</div>' +
                                '<div class="station-stem"></div>' +
                              '</div>',
                        iconSize: [40, 38],
                        iconAnchor: [20, 38],
                        popupAnchor: [0, -36]
                    });

                    // Build Detailed Metadata Popup
                    const formattedTime = p.recorded_at 
                        ? new Date(p.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
                        : 'Timestamp unavailable';

                    let aqiSectionHtml = '';
                    if (isReadingAvailable) {
                        const horizonPrefix = activeHorizon === 'current' ? 'Observed AQI' : ('+' + activeHorizon + 'h Forecast');
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
                            '<span class="popup-unavail-desc">Station is registered and active, awaiting verified hourly observation.</span>' +
                        '</div>';
                    }

                    const popup = '<div class="popup-card">' +
                        '<div class="popup-title">' + p.name + '</div>' +
                        '<div class="popup-subid">' + stationId + (p.zone_type ? ' · ' + p.zone_type : '') + '</div>' +
                        '<div class="popup-badge-row">' +
                            '<span class="popup-badge ' + badgeClass + '">' + classification + '</span>' +
                            '<span class="popup-badge" style="background:#1e293b;color:#94a3b8;">' + (p.source_label || p.source) + '</span>' +
                        '</div>' +
                        aqiSectionHtml +
                        '<div class="popup-time">' +
                            '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:4px;">' +
                                '<circle cx="12" cy="12" r="10"/>' +
                                '<polyline points="12 6 12 12 16 14"/>' +
                            '</svg>' +
                            formattedTime +
                        '</div>' +
                        '<div class="popup-grid">' +
                            '<div class="popup-cell">PM2.5<b>' + (p.pm25 != null ? p.pm25 + ' µg/m³' : '--') + '</b></div>' +
                            '<div class="popup-cell">PM10<b>' + (p.pm10 != null ? p.pm10 + ' µg/m³' : '--') + '</b></div>' +
                            '<div class="popup-cell">NO2<b>' + (p.no2 != null ? p.no2 + ' µg/m³' : '--') + '</b></div>' +
                            '<div class="popup-cell">Wind<b>' + (p.wind_speed != null ? p.wind_speed + ' km/h' : '--') + '</b></div>' +
                        '</div>' +
                    '</div>';

                    L.marker([lat, lon], { icon }).bindPopup(popup).addTo(stationsLayer);
                });

                // Update On-Map Legend Overlay
                const minEl = document.getElementById('legendMinLabel');
                const maxEl = document.getElementById('legendMaxLabel');
                if (minEl) minEl.innerText = 'Blue (' + Math.round(minAqi) + ')';
                if (maxEl) maxEl.innerText = 'Red (' + Math.round(maxAqi) + ')';

                // Post range update to React Native component
                if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {
                    window.ReactNativeWebView.postMessage(JSON.stringify({
                        type: 'RANGE_UPDATE',
                        minAqi: Math.round(minAqi),
                        maxAqi: Math.round(maxAqi),
                        stationCount: renderedStationCount,
                        hotspotsCount: hotspotCount
                    }));
                }
            })
            .catch(err => {
                console.error('Map loading error:', err);
                if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {
                    window.ReactNativeWebView.postMessage(JSON.stringify({
                        type: 'MAP_ERROR',
                        error: 'Unable to render spatial gradient: ' + (err.message || 'Map tiles or layer service unreachable')
                    }));
                }
            });
    </script>
</body>
</html>
  `, [key, horizon, showStations, showHeatmap, showHotspots, showUncertainty]);

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
            setKey(k => k + 1);
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
      {mapError && (
        <ErrorBanner
          message={mapError}
          onRetry={() => {
            setMapError(null);
            setKey(k => k + 1);
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
          key={`${key}-${horizon}-${showStations}-${showHeatmap}-${showHotspots}-${showUncertainty}`}
          source={{ html: mapHtml }}
          style={styles.webview}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          originWhitelist={['*']}
          onMessage={handleMessage}
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
