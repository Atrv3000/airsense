import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants, { ExecutionEnvironment } from 'expo-constants';
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
 *
 * Gracefully detects Expo Go on Android (where remote push notifications were removed in SDK 53+)
 * and avoids throwing unhandled native NullPointerExceptions.
 */
export async function registerForPushNotificationsAsync() {
  let token = null;

  if (Platform.OS === 'web') {
    return null;
  }

  // Detect Expo Go where remote push notifications are unsupported on Android since SDK 53
  const isExpoGo =
    Constants.appOwnership === 'expo' ||
    Constants.executionEnvironment === ExecutionEnvironment?.StoreClient;

  if (Platform.OS === 'android' && isExpoGo) {
    console.log(
      '[AirSense] Notice: Remote push notifications are disabled in Expo Go on Android (SDK 53+). ' +
      'All live data, maps, and forecasts remain fully functional. ' +
      'For remote push, use a development build (npx expo run:android).'
    );
    return null;
  }

  try {
    // Set up Android notification channel (supported on development & production builds)
    if (Platform.OS === 'android') {
      try {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'Air Quality Alerts',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#ef4444',
          sound: 'default',
        });
      } catch (channelError) {
        console.warn(
          '[AirSense] Notification channel setup skipped:',
          channelError?.message || channelError
        );
      }
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
        const projectId =
          Constants?.expoConfig?.extra?.eas?.projectId ??
          Constants?.easConfig?.projectId;

        const pushTokenData = await Notifications.getExpoPushTokenAsync(
          projectId ? { projectId } : undefined
        );
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
        console.warn('[AirSense] Push token retrieval skipped:', error?.message || error);
      }
    } else {
      console.log('[AirSense] Physical device required for remote push notifications.');
    }
  } catch (err) {
    console.warn('[AirSense] Push notification registration error:', err?.message || err);
  }

  return token;
}
