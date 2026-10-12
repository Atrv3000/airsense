/**
 * Tab 4: Alerts & Health Recommendations Screen
 * Shows AQI category health matrix, active warnings, and safety guidelines.
 */
import React from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl
} from 'react-native';
import { useFetch } from '../hooks/useFetch';
import { LoadingCard, SectionHeader, getAQIColor } from '../components/SharedComponents';
import { ENDPOINTS, THEME, CPCB_COLORS } from '../config';

const AQI_HEALTH_MATRIX = [
  {
    category: 'Good',
    range: '0–50',
    color: CPCB_COLORS['Good'],
    icon: '😊',
    groups: { general: 'Safe for all activities.', sensitive: 'No restrictions.', outdoor: 'Ideal for exercise.', mask: 'Not required.' }
  },
  {
    category: 'Satisfactory',
    range: '51–100',
    color: CPCB_COLORS['Satisfactory'],
    icon: '🙂',
    groups: { general: 'Acceptable for most.', sensitive: 'May experience minor discomfort.', outdoor: 'Generally safe.', mask: 'Not required.' }
  },
  {
    category: 'Moderate',
    range: '101–200',
    color: CPCB_COLORS['Moderate'],
    icon: '😐',
    groups: { general: 'Minor impact on sensitive individuals.', sensitive: 'Reduce prolonged outdoor activities.', outdoor: 'Limit heavy outdoor exercise.', mask: 'Recommended for sensitive groups.' }
  },
  {
    category: 'Poor',
    range: '201–300',
    color: CPCB_COLORS['Poor'],
    icon: '😷',
    groups: { general: 'Health discomfort likely.', sensitive: 'Avoid outdoor activities.', outdoor: 'Avoid strenuous outdoor exercise.', mask: 'N95 mask recommended.' }
  },
  {
    category: 'Very Poor',
    range: '301–400',
    color: CPCB_COLORS['Very Poor'],
    icon: '🚫',
    groups: { general: 'Health alert — everyone affected.', sensitive: 'Stay indoors.', outdoor: 'Avoid all outdoor activities.', mask: 'N95 mask essential.' }
  },
  {
    category: 'Severe',
    range: '401–500',
    color: CPCB_COLORS['Severe'],
    icon: '🆘',
    groups: { general: 'Emergency health conditions.', sensitive: 'Do not go outdoors.', outdoor: 'All outdoor activities banned.', mask: 'Double mask / respirator indoors.' }
  },
];

const GENERAL_TIPS = [
  { icon: '🌿', title: 'Use air purifiers indoors',    desc: 'HEPA-grade purifiers reduce indoor PM2.5 by up to 85%.' },
  { icon: '🪟', title: 'Close windows during spikes', desc: 'Seal gaps during Very Poor/Severe episodes.' },
  { icon: '🚶', title: 'Prefer mornings for exercise', desc: 'AQI is typically 15–25% lower before 8 AM.' },
  { icon: '🌲', title: 'Choose greener routes',        desc: 'Tree-lined roads have 40% lower roadside PM2.5.' },
  { icon: '🧴', title: 'Stay hydrated',                desc: 'Water helps flush inhaled particulates from airways.' },
  { icon: '🏥', title: 'Consult a doctor',             desc: 'Asthmatics & cardiac patients should adjust medication during Poor+ days.' },
];

export default function AlertsScreen() {
  const { data, loading, refetch } = useFetch(ENDPOINTS.liveAqi);
  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const cityAQI  = data?.city_average_aqi;
  const cityCat  = data?.city_category;
  const cityColor = getAQIColor(cityCat);

  // Determine current alert level
  let alertLevel = null;
  if (cityAQI >= 301) alertLevel = 'CRITICAL';
  else if (cityAQI >= 201) alertLevel = 'WARNING';
  else if (cityAQI >= 101) alertLevel = 'CAUTION';

  return (
    <View style={styles.container}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={THEME.primary} />}
      >
        {/* Live Alert Banner */}
        {alertLevel && (
          <View style={[styles.alertBanner, {
            backgroundColor: cityColor + '18',
            borderColor: cityColor,
          }]}>
            <Text style={styles.alertIcon}>
              {alertLevel === 'CRITICAL' ? '🆘' : alertLevel === 'WARNING' ? '⚠️' : 'ℹ️'}
            </Text>
            <View style={{ flex: 1 }}>
              <Text style={[styles.alertTitle, { color: cityColor }]}>
                {alertLevel} — City AQI: {cityAQI ? Math.round(cityAQI) : '--'}
              </Text>
              <Text style={styles.alertMsg}>
                {cityCat} air quality detected across Mumbai.{' '}
                {alertLevel === 'CRITICAL'
                  ? 'Remain indoors. Wear masks.'
                  : alertLevel === 'WARNING'
                  ? 'Limit outdoor exposure. Use N95 masks.'
                  : 'Sensitive groups should take precautions.'}
              </Text>
            </View>
          </View>
        )}

        {/* CPCB Health Matrix */}
        <SectionHeader
          title="CPCB AQI Health Matrix"
          subtitle="Official health guidelines by index category"
        />
        {AQI_HEALTH_MATRIX.map((item) => {
          const isCurrent = cityCat && cityCat.toLowerCase().includes(item.category.toLowerCase());
          return (
            <View
              key={item.category}
              style={[
                styles.matrixCard,
                { borderColor: item.color + (isCurrent ? 'ff' : '44') },
                isCurrent && { backgroundColor: item.color + '12' }
              ]}
            >
              <View style={styles.matrixHeader}>
                <Text style={styles.matrixIcon}>{item.icon}</Text>
                <View>
                  <Text style={[styles.matrixCategory, { color: item.color }]}>{item.category}</Text>
                  <Text style={styles.matrixRange}>AQI {item.range}</Text>
                </View>
                {isCurrent && (
                  <View style={[styles.currentPill, { backgroundColor: item.color }]}>
                    <Text style={styles.currentPillText}>NOW</Text>
                  </View>
                )}
              </View>
              <View style={styles.matrixBody}>
                {[
                  { k: '👥 General',    v: item.groups.general },
                  { k: '🤧 Sensitive',  v: item.groups.sensitive },
                  { k: '🏃 Outdoors',   v: item.groups.outdoor },
                  { k: '😷 Masks',      v: item.groups.mask },
                ].map(row => (
                  <View key={row.k} style={styles.matrixRow}>
                    <Text style={styles.matrixKey}>{row.k}</Text>
                    <Text style={styles.matrixVal}>{row.v}</Text>
                  </View>
                ))}
              </View>
            </View>
          );
        })}

        {/* General Safety Tips */}
        <SectionHeader
          title="Safety Tips"
          subtitle="Year-round air quality hygiene"
        />
        {GENERAL_TIPS.map((tip, i) => (
          <View key={i} style={styles.tipCard}>
            <Text style={styles.tipIcon}>{tip.icon}</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.tipTitle}>{tip.title}</Text>
              <Text style={styles.tipDesc}>{tip.desc}</Text>
            </View>
          </View>
        ))}

        {/* Disclaimer */}
        <View style={styles.disclaimer}>
          <Text style={styles.disclaimerText}>
            ⚠️ AQI values computed using official CPCB NAQI breakpoints. Health advisory follows MoEFCC / CPCB published guidelines.
            This app is for educational and informational purposes. Consult a physician for medical advice.
          </Text>
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container:  { flex: 1, backgroundColor: THEME.bg },
  alertBanner: {
    margin: 16,
    borderRadius: 14,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    borderWidth: 1.5,
  },
  alertIcon:  { fontSize: 28 },
  alertTitle: { fontWeight: '800', fontSize: 15, marginBottom: 4 },
  alertMsg:   { color: THEME.textSecondary, fontSize: 12, lineHeight: 18 },
  matrixCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 10,
    borderRadius: 14,
    borderWidth: 1.5,
    overflow: 'hidden',
  },
  matrixHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    paddingBottom: 8,
  },
  matrixIcon:     { fontSize: 24 },
  matrixCategory: { fontWeight: '800', fontSize: 15 },
  matrixRange:    { color: THEME.textMuted, fontSize: 11, marginTop: 2 },
  currentPill: {
    marginLeft: 'auto',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 9999,
  },
  currentPillText: { color: '#fff', fontWeight: '800', fontSize: 10 },
  matrixBody:   { paddingHorizontal: 14, paddingBottom: 12, gap: 6 },
  matrixRow:    { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  matrixKey:    { color: THEME.textSecondary, fontSize: 11, fontWeight: '700', width: 90 },
  matrixVal:    { color: THEME.textPrimary, fontSize: 11, flex: 1, lineHeight: 16 },
  tipCard: {
    backgroundColor: THEME.surface,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  tipIcon:  { fontSize: 22 },
  tipTitle: { color: THEME.textPrimary, fontWeight: '700', fontSize: 13, marginBottom: 4 },
  tipDesc:  { color: THEME.textSecondary, fontSize: 12, lineHeight: 17 },
  disclaimer: {
    margin: 16,
    padding: 14,
    backgroundColor: THEME.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: THEME.border,
  },
  disclaimerText: { color: THEME.textMuted, fontSize: 10, lineHeight: 15 },
});
