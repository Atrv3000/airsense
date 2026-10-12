/**
 * Tab 2: Interactive GIS Map Screen
 * Renders Mumbai monitoring stations and hotspot zones using a WebView-based Leaflet map
 * that fetches GeoJSON from the Django backend.
 */
import React, { useMemo } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { WebView } from 'react-native-webview';
import { ENDPOINTS, THEME } from '../config';

export default function MapScreen() {
  // Generate a self-contained Leaflet HTML page that fetches live data from the backend
  const mapHtml = useMemo(() => `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:#0f172a; }
    #map { width:100vw; height:100vh; }
    .marker-pin {
      display:flex; align-items:center; justify-content:center;
      width:42px; height:42px; border-radius:50%; color:#fff;
      font-weight:900; font-size:13px; border:3px solid rgba(255,255,255,0.8);
      box-shadow:0 3px 12px rgba(0,0,0,0.5); cursor:pointer;
    }
    .popup-inner { padding:10px 12px; background:#1e293b; color:#f8fafc; min-width:200px; border-radius:10px; }
    .popup-inner h3 { font-size:14px; font-weight:700; margin-bottom:6px; }
    .popup-badge {
      display:inline-block; padding:3px 10px; border-radius:6px;
      font-weight:700; font-size:12px; color:#fff; margin-bottom:8px;
    }
    .popup-grid { display:grid; grid-template-columns:1fr 1fr; gap:6px; background:#0f172a; padding:8px; border-radius:8px; }
    .popup-item { font-size:11px; color:#94a3b8; }
    .popup-item span { display:block; font-weight:700; color:#f8fafc; font-size:13px; }
    .fc-strip { margin-top:8px; border-top:1px solid #334155; padding-top:6px; font-size:11px; color:#38bdf8; font-weight:700; }
    .fc-chips { display:flex; gap:4px; margin-top:4px; overflow-x:auto; }
    .fc-chip { background:#0f172a; border:1px solid #334155; border-radius:6px; padding:3px 6px; text-align:center; min-width:44px; font-size:10px; }
    .leaflet-popup-content-wrapper { background:#1e293b !important; border-radius:14px !important; border:1px solid #334155; box-shadow:0 8px 24px rgba(0,0,0,0.6) !important; padding:0 !important; }
    .leaflet-popup-tip { background:#1e293b !important; }
    .leaflet-popup-content { margin:0 !important; }
    .legend { background:rgba(15,23,42,0.92); padding:10px 14px; border-radius:10px; border:1px solid #334155; color:#f1f5f9; font-size:11px; }
    .lg-row { display:flex; align-items:center; gap:6px; margin-bottom:3px; }
    .lg-dot { width:12px; height:12px; border-radius:3px; }
  </style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const map = L.map('map', { center:[19.0760,72.8777], zoom:11, zoomControl:true });
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution:'&copy; OpenStreetMap &copy; CARTO',
    subdomains:'abcd', maxZoom:19
  }).addTo(map);

  const stationsLayer = L.featureGroup().addTo(map);
  const hotspotsLayer = L.featureGroup().addTo(map);

  fetch('${ENDPOINTS.mapLayers}')
    .then(r => r.json())
    .then(d => {
      const stations = d.stations_geojson && d.stations_geojson.features || [];
      const hotspots = d.hotspots_geojson && d.hotspots_geojson.features || [];
      const legend   = d.legend || [];

      stations.forEach(st => {
        const [lon,lat] = st.geometry.coordinates;
        const p = st.properties;
        const icon = L.divIcon({
          className: '',
          html: '<div class="marker-pin" style="background:'+p.color_hex+'">'+Math.round(p.current_aqi||0)+'</div>',
          iconSize:[42,42], iconAnchor:[21,21]
        });

        let fcHtml = '';
        if(p.forecast_24h && p.forecast_24h.length) {
          const chips = p.forecast_24h.slice(0,4).map(f=>
            '<div class="fc-chip"><div style="color:#94a3b8">+'+f.step_ahead_hours+'h</div><div style="font-weight:700;color:'+f.color_hex+'">'+Math.round(f.predicted_aqi)+'</div></div>'
          ).join('');
          fcHtml = '<div class="fc-strip">ML Forecast (Next 4h)<div class="fc-chips">'+chips+'</div></div>';
        }

        const popup = '<div class="popup-inner"><h3>'+p.name+'</h3><span class="popup-badge" style="background:'+p.color_hex+'">AQI '+Math.round(p.current_aqi||0)+' · '+p.category+'</span><div class="popup-grid"><div class="popup-item">PM2.5<span>'+fmt(p.pm25)+' µg</span></div><div class="popup-item">PM10<span>'+fmt(p.pm10)+' µg</span></div><div class="popup-item">Temp<span>'+fmt(p.temperature)+'°C</span></div><div class="popup-item">Wind<span>'+fmt(p.wind_speed)+' km/h</span></div></div>'+fcHtml+'</div>';

        L.marker([lat,lon],{icon}).bindPopup(popup).addTo(stationsLayer);
      });

      hotspots.forEach(hs => {
        if(hs.geometry.type==='Polygon') {
          const llngs = hs.geometry.coordinates[0].map(c=>[c[1],c[0]]);
          const p = hs.properties;
          L.polygon(llngs,{
            color:p.stroke_color||p.color_hex,weight:1,
            fillColor:p.color_hex,fillOpacity:p.fill_opacity||0.25
          }).bindTooltip('Hotspot: AQI '+p.interpolated_aqi+' ('+p.category+')').addTo(hotspotsLayer);
        }
      });

      // Layer toggle
      L.control.layers(null,{'Stations':stationsLayer,'Hotspots':hotspotsLayer},{collapsed:false,position:'topright'}).addTo(map);

      // Legend
      const lc = L.control({position:'bottomright'});
      lc.onAdd = function(){
        const d = L.DomUtil.create('div','legend');
        d.innerHTML = legend.map(l=>'<div class="lg-row"><span class="lg-dot" style="background:'+l.color_hex+'"></span>'+l.category+'</div>').join('');
        return d;
      };
      lc.addTo(map);
    })
    .catch(e => console.error('Map error:', e));

  function fmt(v) { return v!=null ? Number(v).toFixed(1) : '--'; }
</script>
</body>
</html>
  `, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Mumbai Air Quality Map</Text>
        <Text style={styles.headerSubtitle}>Live stations & IDW hotspot zones</Text>
      </View>
      <WebView
        source={{ html: mapHtml }}
        style={styles.webview}
        javaScriptEnabled
        originWhitelist={['*']}
        startInLoadingState
        renderLoading={() => (
          <View style={styles.mapLoading}>
            <ActivityIndicator size="large" color={THEME.primary} />
            <Text style={styles.mapLoadText}>Loading interactive map…</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container:     { flex: 1, backgroundColor: THEME.bg },
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 10,
    backgroundColor: THEME.bg,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
  },
  headerTitle:    { color: THEME.textPrimary, fontSize: 17, fontWeight: '700' },
  headerSubtitle: { color: THEME.textSecondary, fontSize: 12, marginTop: 2 },
  webview:        { flex: 1 },
  mapLoading: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: THEME.bg, alignItems: 'center', justifyContent: 'center', gap: 12,
  },
  mapLoadText:    { color: THEME.textSecondary, fontSize: 14 },
});
