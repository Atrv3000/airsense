import os

leaflet_css = open('airsense_mobile/assets/leaflet.css', 'r', encoding='utf-8').read()
leaflet_js = open('airsense_mobile/assets/leaflet.js', 'r', encoding='utf-8').read()
leaflet_heat = open('airsense_mobile/assets/leaflet-heat.js', 'r', encoding='utf-8').read()

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AirSense Mumbai Spatial Map</title>
    <style>
        {leaflet_css}
    </style>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background:#090d16; color:#f8fafc; overflow:hidden; }}
        #map {{ width:100vw; height:100vh; background:#090d16; }}

        .leaflet-tile {{
            filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7);
        }}

        /* Station Marker Styling */
        .station-pin-wrap {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }}
        .station-beacon {{
            min-width: 32px;
            height: 32px;
            padding: 0 5px;
            border-radius: 16px;
            background: #090d16;
            border: 2px solid #38bdf8;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 2px;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4), 0 3px 8px rgba(0,0,0,0.8);
            transition: transform 0.15s ease;
        }}
        .station-beacon.ground-measured {{
            border-color: #10b981;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.5), 0 3px 8px rgba(0,0,0,0.8);
        }}
        .station-beacon.ground-measured.stale {{
            border-color: #f59e0b;
            box-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
        }}
        .station-beacon.modelled {{
            border-color: #38bdf8;
            border-style: dashed;
            box-shadow: 0 0 8px rgba(56, 189, 248, 0.4);
        }}
        .station-beacon.unavailable {{
            border-color: #64748b;
            box-shadow: 0 2px 6px rgba(0,0,0,0.6);
        }}
        .station-pin-wrap:hover .station-beacon,
        .station-pin-wrap:active .station-beacon {{
            transform: scale(1.15);
        }}
        .station-aqi-txt {{
            font-size: 11px;
            font-weight: 800;
            color: #f8fafc;
            margin-left: 2px;
        }}
        .station-stem {{
            width: 2px;
            height: 5px;
            background: #38bdf8;
            box-shadow: 0 1px 3px rgba(0,0,0,0.6);
        }}
        .station-beacon.ground-measured + .station-stem {{
            background: #10b981;
        }}
        .station-beacon.ground-measured.stale + .station-stem {{
            background: #f59e0b;
        }}
        .station-beacon.unavailable + .station-stem {{
            background: #64748b;
        }}

        /* Popup Cards */
        .popup-card {{
            background: #0f172a;
            color: #f8fafc;
            padding: 14px;
            border-radius: 12px;
            min-width: 230px;
            max-width: 290px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.8);
        }}
        .popup-title {{
            font-size: 14px;
            font-weight: 800;
            margin-bottom: 2px;
            color: #f8fafc;
            line-height: 1.3;
        }}
        .popup-subid {{
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .popup-badge-row {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .popup-badge {{
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.3px;
            text-transform: uppercase;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .badge-measured {{
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }}
        .badge-stale {{
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }}
        .badge-modelled {{
            background: rgba(56, 189, 248, 0.2);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.4);
        }}
        .badge-estimated {{
            background: rgba(168, 85, 247, 0.2);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.4);
        }}
        .popup-aqi-box {{
            display: flex;
            align-items: baseline;
            gap: 8px;
            background: #1e293b;
            padding: 8px 10px;
            border-radius: 8px;
            margin-bottom: 8px;
        }}
        .popup-aqi-val {{
            font-size: 24px;
            font-weight: 800;
            color: #f8fafc;
        }}
        .popup-aqi-meta {{
            display: flex;
            flex-direction: column;
        }}
        .popup-cat-label {{
            font-size: 12px;
            font-weight: 700;
        }}
        .popup-horizon-tag {{
            font-size: 10px;
            color: #94a3b8;
        }}
        .popup-time {{
            font-size: 10px;
            color: #94a3b8;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .popup-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            background: #090d16;
            padding: 8px;
            border-radius: 8px;
            font-size: 10px;
        }}
        .popup-cell {{ color: #94a3b8; }}
        .popup-cell b {{ display: block; color: #f8fafc; font-size: 11px; margin-top: 1px; }}

        .leaflet-popup-content-wrapper {{
            background: #0f172a !important;
            border-radius: 12px !important;
            border: 1px solid #1e293b;
            padding: 0 !important;
        }}
        .leaflet-popup-tip {{ background: #0f172a !important; }}
        .leaflet-popup-content {{ margin: 0 !important; }}

        /* On-Map Floating Legend */
        .map-legend-overlay {{
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
        }}
        .map-legend-title {{
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            color: #94a3b8;
            margin-bottom: 4px;
        }}
        .map-legend-bar {{
            height: 6px;
            border-radius: 3px;
            background: linear-gradient(to right, #1e40af, #0284c7, #eab308, #f97316, #dc2626);
            margin-bottom: 4px;
        }}
        .map-legend-endpoints {{
            display: flex;
            justify-content: space-between;
            font-size: 9px;
            color: #64748b;
            margin-bottom: 6px;
        }}
        .map-legend-items {{
            display: flex;
            flex-direction: column;
            gap: 3px;
        }}
        .legend-item-row {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .dot-measured {{
            width: 8px;
            height: 8px;
            border-radius: 4px;
            border: 1.5px solid #10b981;
            background: #090d16;
        }}
        .dot-modelled {{
            width: 8px;
            height: 8px;
            border-radius: 4px;
            border: 1.5px dashed #38bdf8;
            background: #090d16;
        }}
        .dot-hotspot {{
            width: 8px;
            height: 8px;
            border-radius: 4px;
            border: 1.5px solid #ef4444;
            background: rgba(239, 68, 68, 0.4);
        }}
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

    <script>
        {leaflet_js}
    </script>
    <script>
        {leaflet_heat}
    </script>
    <script>
        // Initialize base Leaflet map centered on Mumbai
        const map = L.map('map', {{
            center: [19.0760, 72.8777],
            zoom: 11,
            zoomControl: false,
            attributionControl: false
        }});

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 18
        }}).addTo(map);

        const stationsLayer = L.featureGroup().addTo(map);
        const hotspotsLayer = L.featureGroup().addTo(map);
        const uncertaintyLayer = L.featureGroup().addTo(map);
        let heatLayer = null;

        window.updateMapLayers = function(payload) {{
            try {{
                const data = payload.data || {{}};
                const horizon = payload.horizon || 'current';
                const showStations = payload.showStations !== false;
                const showHeatmap = payload.showHeatmap !== false;
                const showHotspots = payload.showHotspots !== false;
                const showUncertainty = !!payload.showUncertainty;

                stationsLayer.clearLayers();
                hotspotsLayer.clearLayers();
                uncertaintyLayer.clearLayers();
                if (heatLayer) {{
                    map.removeLayer(heatLayer);
                    heatLayer = null;
                }}

                const stations = (data.stations_geojson && data.stations_geojson.features) || [];

                // 1. Determine Interpolated Grid
                let gridFeatures = [];
                if (horizon === 'current') {{
                    gridFeatures = (data.grid_geojson && data.grid_geojson.features) || [];
                }} else {{
                    const hKey = 'plus_' + horizon + 'h';
                    if (data.predicted_grids && data.predicted_grids[hKey]) {{
                        gridFeatures = data.predicted_grids[hKey].features || [];
                    }}
                }}

                // 2. Source Points for Heatmap & Range
                let sourcePoints = [];
                if (gridFeatures.length > 0) {{
                    sourcePoints = gridFeatures.map(f => {{
                        const [lon, lat] = f.geometry.coordinates;
                        return {{
                            lat, lon,
                            aqi: f.properties.interpolated_aqi,
                            uncertainty: f.properties.spatial_uncertainty || 12.0,
                            nearestStationKm: f.properties.nearest_station_km || 2.5
                        }};
                    }});
                }} else {{
                    stations.forEach(st => {{
                        const [lon, lat] = st.geometry.coordinates;
                        const p = st.properties || {{}};
                        let aqi = p.current_aqi;
                        if (horizon !== 'current' && p.forecast_24h) {{
                            const hInt = parseInt(horizon, 10);
                            const fc = p.forecast_24h.find(f => f.step_ahead_hours === hInt);
                            if (fc && fc.predicted_aqi != null) aqi = fc.predicted_aqi;
                        }}
                        if (aqi != null && !isNaN(aqi)) {{
                            sourcePoints.push({{ lat, lon, aqi, uncertainty: 10.0, nearestStationKm: 0.0 }});
                        }}
                    }});
                }}

                let minAqi = Infinity;
                let maxAqi = -Infinity;
                sourcePoints.forEach(pt => {{
                    if (pt.aqi != null && !isNaN(pt.aqi)) {{
                        if (pt.aqi < minAqi) minAqi = pt.aqi;
                        if (pt.aqi > maxAqi) maxAqi = pt.aqi;
                    }}
                }});
                if (!isFinite(minAqi)) {{ minAqi = 40; maxAqi = 250; }}
                if (maxAqi <= minAqi) {{ maxAqi = minAqi + 50; }}

                // 3. Continuous Heatmap
                if (showHeatmap && window.L && L.heatLayer && sourcePoints.length > 0) {{
                    const heatPoints = sourcePoints.map(pt => {{
                        const norm = Math.max(0.01, Math.min(1.0, (pt.aqi - minAqi) / (maxAqi - minAqi)));
                        return [pt.lat, pt.lon, norm];
                    }});
                    heatLayer = L.heatLayer(heatPoints, {{
                        minOpacity: 0.40,
                        maxZoom: 14,
                        radius: 34,
                        blur: 24,
                        max: 1.0,
                        gradient: {{
                            0.0:  '#1e40af',
                            0.25: '#0284c7',
                            0.5:  '#eab308',
                            0.75: '#f97316',
                            1.0:  '#dc2626'
                        }}
                    }}).addTo(map);
                }}

                // 4. Hotspots (AQI >= 201)
                let activeHotspots = null;
                if (horizon === 'current') {{
                    activeHotspots = data.hotspots_geojson;
                }} else {{
                    const hKey = 'plus_' + horizon + 'h';
                    if (data.predicted_hotspots && data.predicted_hotspots[hKey]) {{
                        activeHotspots = data.predicted_hotspots[hKey];
                    }}
                }}

                let hotspotCount = 0;
                if (showHotspots && activeHotspots && activeHotspots.features) {{
                    activeHotspots.features.forEach(feat => {{
                        hotspotCount++;
                        L.geoJSON(feat, {{
                            style: {{
                                color: '#ef4444',
                                weight: 2,
                                opacity: 0.9,
                                fillColor: '#dc2626',
                                fillOpacity: 0.25,
                                dashArray: '4, 4'
                            }},
                            onEachFeature: (f, layer) => {{
                                const props = f.properties || {{}};
                                const hsPopup = '<div class="popup-card">' +
                                    '<div class="popup-title">' + (props.name || 'Identified Hotspot') + '</div>' +
                                    '<div class="popup-badge-row">' +
                                        '<span class="popup-badge" style="background:rgba(239,68,68,0.25);color:#ef4444;border:1px solid #ef4444">' + (props.classification || 'Severe Exceedance') + '</span>' +
                                    '</div>' +
                                    '<div class="popup-grid">' +
                                        '<div class="popup-cell">Peak AQI<b>' + Math.round(props.peak_aqi || 205) + '</b></div>' +
                                        '<div class="popup-cell">Affected Area<b>' + (props.area_sq_km ? props.area_sq_km.toFixed(1) + ' km²' : 'Local Cluster') + '</b></div>' +
                                    '</div>' +
                                '</div>';
                                layer.bindPopup(hsPopup);
                            }}
                        }}).addTo(hotspotsLayer);
                    }});
                }}

                // 5. Kriging Uncertainty Grid
                if (showUncertainty && gridFeatures.length > 0) {{
                    gridFeatures.forEach(f => {{
                        const [lon, lat] = f.geometry.coordinates;
                        const pt = {{
                            aqi: f.properties.interpolated_aqi,
                            uncertainty: f.properties.spatial_uncertainty || 12.0,
                            nearestStationKm: f.properties.nearest_station_km || 2.5
                        }};
                        const normUncert = Math.min(1.0, pt.uncertainty / 30.0);
                        const circle = L.circleMarker([lat, lon], {{
                            radius: 6,
                            fillColor: '#a855f7',
                            color: '#9333ea',
                            weight: 1,
                            opacity: 0.6,
                            fillOpacity: 0.2 + (normUncert * 0.5)
                        }});
                        const uncertPopup = '<div class="popup-card">' +
                            '<div class="popup-title">Spatial Estimation Uncertainty</div>' +
                            '<div class="popup-badge-row">' +
                                '<span class="popup-badge badge-estimated">Kriging GP Model</span>' +
                            '</div>' +
                            '<div class="popup-grid">' +
                                '<div class="popup-cell">Estimated AQI<b>' + Math.round(pt.aqi) + '</b></div>' +
                                '<div class="popup-cell">Posterior Std<b>±' + pt.uncertainty.toFixed(1) + ' AQI</b></div>' +
                                '<div class="popup-cell" style="grid-column:span 2">Nearest Station<b>' + pt.nearestStationKm.toFixed(1) + ' km away</b></div>' +
                            '</div>' +
                        '</div>';
                        circle.bindPopup(uncertPopup);
                        uncertaintyLayer.addLayer(circle);
                    }});
                }}

                // 6. Monitoring Station Pins (Honest Measured vs Modelled)
                const seenStationIds = new Set();
                let renderedStationCount = 0;

                if (showStations) {{
                    stations.forEach(st => {{
                        const [lon, lat] = st.geometry.coordinates;
                        const p = st.properties || {{}};
                        const stationId = p.station_id || (lon + '_' + lat);

                        if (seenStationIds.has(stationId)) return;
                        seenStationIds.add(stationId);
                        renderedStationCount++;

                        let displayAqi = (p.current_aqi != null && !isNaN(p.current_aqi)) ? Math.round(p.current_aqi) : null;
                        let displayCat = p.category || 'Unavailable';
                        let isReadingAvailable = (displayAqi !== null);

                        if (horizon !== 'current' && p.forecast_24h) {{
                            const hInt = parseInt(horizon, 10);
                            const fc = p.forecast_24h.find(f => f.step_ahead_hours === hInt);
                            if (fc && fc.predicted_aqi != null) {{
                                displayAqi = Math.round(fc.predicted_aqi);
                                displayCat = fc.category || displayCat;
                                isReadingAvailable = true;
                            }}
                        }}

                        const isMeasured = !!p.is_measured;
                        const isStale = !!p.is_ground_stale;
                        const badgeClass = isMeasured ? (isStale ? 'badge-stale' : 'badge-measured') : 'badge-modelled';
                        const beaconTypeClass = isReadingAvailable 
                            ? (isMeasured ? (isStale ? 'ground-measured stale' : 'ground-measured') : 'modelled') 
                            : 'unavailable';

                        const strokeColor = isMeasured ? (isStale ? '#f59e0b' : '#10b981') : '#38bdf8';

                        const icon = L.divIcon({{
                            className: '',
                            html: '<div class="station-pin-wrap">' +
                                    '<div class="station-beacon ' + beaconTypeClass + '">' +
                                        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="' + strokeColor + '" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
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
                        }});

                        const formattedTime = p.recorded_at 
                            ? new Date(p.recorded_at).toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }})
                            : 'Timestamp unavailable';

                        let aqiSectionHtml = '';
                        if (isReadingAvailable) {{
                            const horizonPrefix = horizon === 'current' ? 'Observed AQI' : ('+' + horizon + 'h Forecast');
                            aqiSectionHtml = '<div class="popup-aqi-box">' +
                                '<div class="popup-aqi-val">' + displayAqi + '</div>' +
                                '<div class="popup-aqi-meta">' +
                                    '<span class="popup-cat-label" style="color:' + (p.color_hex || '#38bdf8') + '">' + displayCat + '</span>' +
                                    '<span class="popup-horizon-tag">' + horizonPrefix + '</span>' +
                                '</div>' +
                            '</div>';
                        }}

                        const groundAgeStr = p.ground_age_hours != null ? (p.ground_age_hours < 1 ? '<1h ago' : Math.round(p.ground_age_hours) + 'h ago') : '--';
                        const providerLabel = p.data_provider || (isMeasured ? 'CPCB / OpenAQ CAAQMS' : 'Open-Meteo Model');

                        const popup = '<div class="popup-card">' +
                            '<div class="popup-title">' + (p.name || 'Monitoring Station') + '</div>' +
                            '<div class="popup-subid">' + (p.station_id || 'CAAQMS Station') + '</div>' +
                            '<div class="popup-badge-row">' +
                                '<span class="popup-badge ' + badgeClass + '">' + (isMeasured ? (isStale ? 'Ground Measured (Stale)' : 'Ground Measured') : 'Modelled') + '</span>' +
                                '<span class="popup-badge" style="background:#1e293b;color:#94a3b8">' + providerLabel + '</span>' +
                            '</div>' +
                            aqiSectionHtml +
                            '<div class="popup-time">' +
                                '<span>Observation: ' + formattedTime + '</span>' +
                                (isMeasured ? ' • <span>Ground: ' + groundAgeStr + '</span>' : '') +
                            '</div>' +
                            '<div class="popup-grid">' +
                                '<div class="popup-cell">PM2.5<b>' + (p.pm25 != null ? p.pm25 + ' µg/m³' : '--') + '</b></div>' +
                                '<div class="popup-cell">PM10<b>' + (p.pm10 != null ? p.pm10 + ' µg/m³' : '--') + '</b></div>' +
                                '<div class="popup-cell">NO2<b>' + (p.no2 != null ? p.no2 + ' µg/m³' : '--') + '</b></div>' +
                                '<div class="popup-cell">Wind<b>' + (p.wind_speed != null ? p.wind_speed + ' km/h' : '--') + '</b></div>' +
                            '</div>' +
                        '</div>';

                        L.marker([lat, lon], {{ icon }}).bindPopup(popup).addTo(stationsLayer);
                    }});
                }}

                // 7. Update on-map legend labels
                const minEl = document.getElementById('legendMinLabel');
                const maxEl = document.getElementById('legendMaxLabel');
                if (minEl) minEl.innerText = 'Blue (' + Math.round(minAqi) + ')';
                if (maxEl) maxEl.innerText = 'Red (' + Math.round(maxAqi) + ')';

                // 8. Post back range update
                if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {{
                    window.ReactNativeWebView.postMessage(JSON.stringify({{
                        type: 'RANGE_UPDATE',
                        minAqi: Math.round(minAqi),
                        maxAqi: Math.round(maxAqi),
                        stationCount: renderedStationCount,
                        hotspotsCount: hotspotCount
                    }}));
                }}
            }} catch (err) {{
                console.error('Error updating map layers:', err);
                if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {{
                    window.ReactNativeWebView.postMessage(JSON.stringify({{
                        type: 'MAP_ERROR',
                        error: 'Failed to render map layers: ' + (err.message || 'Unknown error')
                    }}));
                }}
            }}
        }};

        // Listen for messages from React Native WebView
        function handleMsg(event) {{
            try {{
                var raw = event.data;
                var msg = typeof raw === 'string' ? JSON.parse(raw) : raw;
                if (msg && msg.type === 'SET_LAYERS') {{
                    window.updateMapLayers(msg);
                }}
            }} catch(e) {{}}
        }}
        window.addEventListener('message', handleMsg);
        document.addEventListener('message', handleMsg);

        // Tell React Native the map DOM is ready
        setTimeout(function() {{
            if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {{
                window.ReactNativeWebView.postMessage(JSON.stringify({{ type: 'MAP_READY' }}));
            }}
        }}, 100);
    </script>
</body>
</html>"""

with open('airsense_mobile/assets/map.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print('Generated airsense_mobile/assets/map.html! Size:', len(html_content), 'bytes')
