// Schedules the session reminders on the phone. Nothing leaves the device.
import { Alert, Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import AsyncStorage from '@react-native-async-storage/async-storage';
import ExactAlarm from '../modules/exact-alarm';
import { scheduleKey } from './reminders';

const CHANNEL = 'sessions';
const PREFIX = 'cc26-';
const ASKED_EXACT = 'cc26.askedExactAlarm';

// Show reminders even while the app is open (the default hides them in the foreground).
Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

// Android drops notifications posted to a channel that doesn't exist yet, so scheduling awaits this.
let channel = null;
function setupChannel() {
  if (Platform.OS !== 'android') return Promise.resolve();
  return (channel ??= Notifications.setNotificationChannelAsync(CHANNEL, {
    name: 'Session reminders',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 150, 250],
    lightColor: '#3355dd',
  }).catch(e => { channel = null; throw e; }));
}

// Ask at most once per launch: after "Don't allow", later plan changes don't prompt again.
let askedThisLaunch = false;
async function ensurePermission() {
  const now = await Notifications.getPermissionsAsync();
  if (now.granted) return true;
  if (!now.canAskAgain || askedThisLaunch) return false;
  askedThisLaunch = true;
  return (await Notifications.requestPermissionsAsync()).granted;
}

// Android 14 turns exact alarms off by default; without them a reminder can arrive minutes late.
// Ask once; the switch stays reachable from the app's system settings.
async function offerExactAlarms() {
  if (ExactAlarm.canSchedule()) return;
  try { if (await AsyncStorage.getItem(ASKED_EXACT)) return; await AsyncStorage.setItem(ASKED_EXACT, '1'); } catch {}
  Alert.alert(
    'On-time reminders',
    'Android may deliver reminders a few minutes late unless you allow "Alarms & reminders" for this app.',
    [{ text: 'Not now', style: 'cancel' }, { text: 'Open settings', onPress: () => ExactAlarm.openSettings() }],
  );
}

let applied = null;
let queue = Promise.resolve();
// What this launch scheduled: id -> signature. Lets a resync leave unchanged reminders alone.
const live = new Map();
let liveExact = null;
const MIN_LEAD = 2000; // too close to schedule reliably

// Replaces our scheduled reminders with `list` (from buildReminders). Calls run one at a time, since
// the page can post several plans in a row. Skips the work when nothing changed, which is most page
// loads; exact-alarm access is part of the key so that granting it reschedules everything as exact.
export function applyReminders(list) {
  queue = queue.then(() => replace(list)).catch(e => console.warn('reminders', e));
  return queue;
}

async function replace(list) {
  const exact = ExactAlarm.canSchedule();
  const key = `${exact}\n${scheduleKey(list)}`;
  if (key === applied) return;
  if (list.length) {
    if (!(await ensurePermission())) return;
    await offerExactAlarms();
  }
  await setupChannel();
  if (exact !== liveExact) { live.clear(); liveExact = exact; } // reschedule them all as exact alarms
  const want = new Map(list.map(r => [r.id, `${r.at}|${r.title}|${r.body}`]));
  const pending = (await Notifications.getAllScheduledNotificationsAsync())
    .map(n => n.identifier).filter(id => id.startsWith(PREFIX));
  // Keep a reminder that is unchanged: cancelling one due in a moment could lose it.
  const keep = new Set(pending.filter(id => want.has(id) && live.get(id) === want.get(id)));
  for (const id of pending) if (!keep.has(id)) await Notifications.cancelScheduledNotificationAsync(id);
  for (const id of [...live.keys()]) if (!keep.has(id)) live.delete(id);
  for (const r of list) {
    if (keep.has(r.id) || r.at < Date.now() + MIN_LEAD) continue;
    await Notifications.scheduleNotificationAsync({
      identifier: r.id,
      content: { title: r.title, body: r.body, data: r.data },
      trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: r.at, channelId: CHANNEL },
    });
    live.set(r.id, want.get(r.id));
  }
  applied = key;
}
