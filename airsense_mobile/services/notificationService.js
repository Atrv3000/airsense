import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { ENDPOINTS } from '../config';

// Configure how incoming notifications are presented while the app is foregrounded
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/**
 * Requests push notification permissions and registers the device's Expo push token
 * with the AirSense Django backend (POST /api/v1/alerts/device-token/).
 */
export async function registerForPushNotificationsAsync() {
  let token = null;

  if (Platform.OS === 'web') {
    return null;
  }

  // Set up Android notification channel
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Air Quality Alerts',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#ef4444',
      sound: 'default',
    });
  }

  if (Device.isDevice) {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') {
      console.log('[AirSense] Push notification permission not granted.');
      return null;
    }

    try {
      const pushTokenData = await Notifications.getExpoPushTokenAsync();
      token = pushTokenData.data;

      // Register device token with AirSense backend
      await fetch(ENDPOINTS.deviceToken, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          token: token,
          platform: Platform.OS.toUpperCase(),
        }),
      });

      console.log('[AirSense] Registered Expo push token:', token);
    } catch (error) {
      console.warn('[AirSense] Failed to retrieve or register Expo push token:', error);
    }
  } else {
    console.log('[AirSense] Physical device required for remote push notifications.');
  }

  return token;
}
