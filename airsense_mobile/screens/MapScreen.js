/**
 * Tab 2: Interactive GIS Map Screen
 * Displays Mumbai monitoring stations and IDW hotspot polygons.
 * Loads the backend-rendered Leaflet map URL or direct fallback HTML for maximum compatibility.
 */
import React, { useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity, Platform } from 'react-native';
import { WebView } from 'react-native-webview';
import { API_BASE_URL, THEME } from '../config';

export default function MapScreen() {
  const [loadError, setLoadError] = useState(false);
  const [key, setKey] = useState(1);

  // The Django backend serves the Leaflet map at /map/
  const mapUrl = `${API_BASE_URL}/map/`;

  const reloadMap = () => {
    setLoadError(false);
    setKey(prev => prev + 1);
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Mumbai Air Quality Map</Text>
          <Text style={styles.headerSubtitle}>Real-time stations & IDW hotspot zones</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={reloadMap}>
          <Text style={styles.refreshText}>🔄 Reload</Text>
        </TouchableOpacity>
      </View>

      {loadError ? (
        <View style={styles.errorContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorTitle}>Could not load Map</Text>
          <Text style={styles.errorSubtitle}>
            Failed to connect to: {mapUrl}
          </Text>
          <Text style={styles.errorHint}>
            Please ensure your Django backend is running with:
            {'\n'}python manage.py runserver 0.0.0.0:8000
          </Text>
          <TouchableOpacity style={styles.retryBtn} onPress={reloadMap}>
            <Text style={styles.retryBtnText}>Retry Connection</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.webWrapper}>
          <WebView
            key={key}
            source={{ uri: mapUrl }}
            style={styles.webview}
            javaScriptEnabled={true}
            domStorageEnabled={true}
            startInLoadingState={true}
            mixedContentMode="always"
            allowFileAccess={true}
            scalesPageToFit={true}
            onError={(syntheticEvent) => {
              const { nativeEvent } = syntheticEvent;
              console.warn('WebView error: ', nativeEvent);
              setLoadError(true);
            }}
            onHttpError={(syntheticEvent) => {
              const { nativeEvent } = syntheticEvent;
              console.warn('WebView HTTP error: ', nativeEvent.statusCode);
              if (nativeEvent.statusCode >= 400) {
                setLoadError(true);
              }
            }}
            renderLoading={() => (
              <View style={styles.mapLoading}>
                <ActivityIndicator size="large" color={THEME.primary} />
                <Text style={styles.mapLoadText}>Loading Mumbai GIS Map...</Text>
              </View>
            )}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.bg,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 10,
    backgroundColor: THEME.bg,
    borderBottomWidth: 1,
    borderBottomColor: THEME.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    color: THEME.textPrimary,
    fontSize: 17,
    fontWeight: '700',
  },
  headerSubtitle: {
    color: THEME.textSecondary,
    fontSize: 12,
    marginTop: 2,
  },
  refreshBtn: {
    backgroundColor: THEME.surface,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  refreshText: {
    color: THEME.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  webWrapper: {
    flex: 1,
    width: '100%',
    height: '100%',
    backgroundColor: '#0f172a',
  },
  webview: {
    flex: 1,
    width: '100%',
    height: '100%',
    backgroundColor: '#0f172a',
  },
  mapLoading: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: THEME.bg,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  mapLoadText: {
    color: THEME.textSecondary,
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 30,
    gap: 12,
  },
  errorIcon: {
    fontSize: 40,
  },
  errorTitle: {
    color: THEME.error,
    fontSize: 18,
    fontWeight: '700',
  },
  errorSubtitle: {
    color: THEME.textSecondary,
    fontSize: 13,
    textAlign: 'center',
  },
  errorHint: {
    color: THEME.textMuted,
    fontSize: 12,
    textAlign: 'center',
    lineHeight: 18,
  },
  retryBtn: {
    marginTop: 10,
    backgroundColor: THEME.primaryDark,
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 14,
  },
});
