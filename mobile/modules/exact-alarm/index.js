// Android-only native module (see ExactAlarmModule.kt). Elsewhere, and if the native side is
// missing, the stub says exact alarms are fine: iOS has no such permission.
import { Platform } from 'react-native';
import { requireNativeModule } from 'expo-modules-core';

const stub = { canSchedule: () => true, openSettings: () => false };

export default (() => {
  if (Platform.OS !== 'android') return stub;
  try {
    return requireNativeModule('ExactAlarm');
  } catch {
    return stub;
  }
})();
