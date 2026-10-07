// The planner site in a WebView, plus native reminders for your Going sessions.
// See README.md for how the page and the app talk to each other.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, AppState, BackHandler, Linking, Platform, Pressable, StyleSheet, Text, View, useColorScheme } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';
import * as Notifications from 'expo-notifications';
import * as Sharing from 'expo-sharing';
import { File, Paths } from 'expo-file-system';
import { Camera, CameraView } from 'expo-camera';
import { PAGE_SCRIPT, PASTE_LINK, SHOW_NOW, receiveLink } from './src/bridge';
import { buildReminders, parsePlan } from './src/reminders';
import { applyReminders } from './src/notify';

// EXPO_PUBLIC_PLANNER_URL points a build at another https copy of the site.
const OVERRIDE = process.env.EXPO_PUBLIC_PLANNER_URL;
const SITE = (OVERRIDE && /^https:\/\/[a-z0-9.-]+(\/[^?#]*)?$/.test(OVERRIDE) ? OVERRIDE : 'https://cc26plan.nb-cs.net').replace(/\/+$/, '');
const ORIGIN = SITE.match(/^https:\/\/[^/]+/)[0]; // lower case: that's how WebViews report URLs
// Exactly the planner's origin: a prefix test would also pass https://cc26plan.nb-cs.net.evil.com.
const isPlanner = url => typeof url === 'string' && url.startsWith(ORIGIN) && /^([/?#]|$)/.test(url.slice(ORIGIN.length));
// EXPO_PUBLIC_WEBVIEW_DEBUG=1 lets chrome://inspect attach over USB (local test builds only; .env files are gitignored).
const WEB_DEBUG = __DEV__ || process.env.EXPO_PUBLIC_WEBVIEW_DEBUG === '1';
// The page only talks to a WebView that identifies as this app (see nativeApp() in src/planner.html).
const USER_AGENT_TAG = 'CC26PlannerApp/1';

// Is a CSS colour dark? Picks the status bar text colour to match the page.
function isDark(css) {
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(css || '');
  return m ? 0.299 * m[1] + 0.587 * m[2] + 0.114 * m[3] < 128 : null;
}

function Planner() {
  const web = useRef(null);
  const canGoBack = useRef(false);
  const pendingNow = useRef(false);
  const loaded = useRef(false);
  const failed = useRef(false);
  const scheme = useColorScheme();
  const [bg, setBg] = useState(null);
  // Bumped to remount the WebView: after Android kills its renderer the old one can't be reused.
  const [generation, setGeneration] = useState(0);
  const pageBg = bg || (scheme === 'light' ? '#f4f5fb' : '#0f1220');
  const dark = isDark(bg) ?? scheme !== 'light';

  const run = useCallback(js => web.current?.injectJavaScript(js), []);
  const showNow = useCallback(() => { if (loaded.current) run(SHOW_NOW); else pendingNow.current = true; }, [run]);

  // Tapping a reminder opens the Now tab, whether the app was running or not.
  useEffect(() => {
    if (Notifications.getLastNotificationResponse()?.notification.request.identifier.startsWith('cc26-')) {
      Notifications.clearLastNotificationResponse(); // so a recreated activity doesn't jump to Now again
      showNow();
    }
    const sub = Notifications.addNotificationResponseReceivedListener(() => {
      Notifications.clearLastNotificationResponse();
      showNow();
    });
    return () => sub.remove();
  }, [showNow]);

  // Back to the foreground: resync, which also picks up a newly granted exact-alarm permission.
  // If the page never loaded (no network on first launch), try again.
  useEffect(() => {
    const sub = AppState.addEventListener('change', s => {
      if (s !== 'active') return;
      if (failed.current) web.current?.reload();
      else if (loaded.current) run(PAGE_SCRIPT);
    });
    return () => sub.remove();
  }, [run]);

  // Receive from another device: scan the QR code the other device shows, or paste its link.
  // The scanner is the system one (Google code scanner / iOS VisionKit), so the app needs no camera
  // access on Android. Only a planner transfer link (…#x=…) is handed to the page, which then shows
  // what would change and waits for "Use it on this device".
  const scanning = useRef(false);
  useEffect(() => {
    const sub = CameraView.onModernBarcodeScanned(({ data }) => {
      if (!scanning.current) return;
      scanning.current = false;
      CameraView.dismissScanner().catch(() => {});
      if (isPlanner(data) && /#x=[\w-]+$/.test(data)) run(receiveLink(data));
      else Alert.alert('Not a transfer link', 'Scan the QR code from My plan › More › Send to another device on the other device.');
    });
    return () => sub.remove();
  }, [run]);
  const receive = useCallback(() => {
    const paste = () => run(PASTE_LINK);
    const cantScan = msg => Alert.alert("Can't scan", msg, [{ text: 'Cancel', style: 'cancel' }, { text: 'Paste link', onPress: paste }]);
    const scan = async () => {
      // iOS's scanner only opens once the app has camera access, and doesn't ask for it itself.
      // (Android's runs in Play services and needs none; the app doesn't even declare it.)
      if (Platform.OS === 'ios' && !(await Camera.requestCameraPermissionsAsync()).granted) {
        return cantScan('Camera access is off for CC26 Planner (Settings › CC26 Planner › Camera). You can paste the link instead.');
      }
      scanning.current = true;
      CameraView.launchScanner({ barcodeTypes: ['qr'] }).catch(e => {
        scanning.current = false;
        if (!/cancel/i.test(`${e?.code} ${e?.message}`)) cantScan("The QR scanner isn't available on this phone. You can paste the link instead.");
      });
    };
    if (!CameraView.isModernBarcodeScannerAvailable) return paste();
    Alert.alert('Receive from another device', 'On the other device, open My plan › More › Send to another device.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Paste link', onPress: paste },
      { text: 'Scan QR code', onPress: scan },
    ]);
  }, [run]);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (!canGoBack.current) return false;
      web.current?.goBack();
      return true;
    });
    return () => sub.remove();
  }, []);

  const onMessage = useCallback(async e => {
    // The bridge accepts messages from any frame or origin; only the planner itself gets a hearing.
    if (!isPlanner(e.nativeEvent.url)) return;
    const raw = e.nativeEvent.data;
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }
    // The page is up once it talks to us (an error page never does; on Android onLoadEnd fires
    // before onError, so it can't tell us). The bridge script reports the theme on every load.
    if (!loaded.current) {
      loaded.current = true;
      if (pendingNow.current) { pendingNow.current = false; run(SHOW_NOW); }
    }
    if (msg.type === 'cc26-plan') {
      const plan = parsePlan(msg);
      if (plan) applyReminders(buildReminders(plan));
    } else if (msg.type === 'cc26-receive') {
      receive();
    } else if (msg.type === 'cc26-theme') {
      if (typeof msg.bg === 'string' && /^rgba?\([\d.,\s]+\)$/.test(msg.bg)) setBg(msg.bg);
    } else if (msg.type === 'cc26-file' && typeof msg.name === 'string') {
      // Backup, calendar and CSV exports: the page would download a blob, which a WebView can't.
      try {
        const file = new File(Paths.cache, msg.name.replace(/[^\w.-]/g, '_'));
        file.create({ overwrite: true });
        file.write(String(msg.text ?? ''));
        await Sharing.shareAsync(file.uri, { mimeType: msg.mime, dialogTitle: msg.name });
      } catch (err) {
        console.warn('share failed', err);
      }
    }
  }, [run, receive]);

  // The planner stays in the app. Other https links the user follows (official session pages, GitHub
  // feedback) open in the browser; every other scheme (intent:, market:, file:, ...) and any subframe
  // navigation away from the planner is dropped. originWhitelist ['*'] routes everything through here.
  const onShouldStart = useCallback(req => {
    if (isPlanner(req.url) || req.url === 'about:blank') return true;
    if (req.isTopFrame !== false && /^https:\/\//i.test(req.url)) Linking.openURL(req.url).catch(() => {});
    return false;
  }, []);

  return (
    // Edge to edge: the page pads for the status bar and gesture bar itself (viewport-fit=cover + env(safe-area-inset-*)).
    <View style={[styles.fill, { backgroundColor: pageBg }]}>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <WebView
        key={generation}
        ref={web}
        style={[styles.fill, { backgroundColor: pageBg }]}
        source={{ uri: `${SITE}/` }}
        originWhitelist={['*']}
        applicationNameForUserAgent={USER_AGENT_TAG}
        injectedJavaScript={PAGE_SCRIPT}
        onMessage={onMessage}
        onShouldStartLoadWithRequest={onShouldStart}
        onNavigationStateChange={s => { canGoBack.current = s.canGoBack; }}
        onLoadStart={() => { loaded.current = false; failed.current = false; }}
        onError={() => { failed.current = true; loaded.current = false; }}
        renderError={() => <LoadError dark={dark} onRetry={() => web.current?.reload()} />}
        // The library's default loading overlay is white; the page background shows through instead.
        renderLoading={() => null}
        // The renderer was killed (memory pressure) or crashed. Android: a new WebView is needed.
        onRenderProcessGone={() => { loaded.current = false; failed.current = false; setGeneration(g => g + 1); }}
        onContentProcessDidTerminate={() => web.current?.reload()}
        // iOS: the site's service worker (offline use) only runs on an app-bound domain (app.config.js).
        // Other hosts never load in here anyway: onShouldStart hands them to the browser.
        limitsNavigationsToAppBoundDomains
        setSupportMultipleWindows={false}
        allowFileAccess={false}
        domStorageEnabled
        cacheEnabled
        pullToRefreshEnabled={false}
        overScrollMode="never"
        textZoom={100}
        webviewDebuggingEnabled={WEB_DEBUG}
      />
    </View>
  );
}

// First launch without a connection: the site's service worker hasn't cached anything yet.
function LoadError({ dark, onRetry }) {
  const fg = dark ? '#e8eaf6' : '#1b1f3a';
  return (
    <View style={[StyleSheet.absoluteFill, styles.error, { backgroundColor: dark ? '#0f1220' : '#f4f5fb' }]}>
      <Text style={[styles.errorTitle, { color: fg }]}>Can't reach the planner</Text>
      <Text style={[styles.errorText, { color: fg }]}>It needs a connection the first time it opens. After that it works offline.</Text>
      <Pressable onPress={onRetry} style={styles.retry}><Text style={styles.retryText}>Try again</Text></Pressable>
    </View>
  );
}

export default Planner;

const styles = StyleSheet.create({
  fill: { flex: 1 },
  error: { alignItems: 'center', justifyContent: 'center', padding: 32, gap: 12 },
  errorTitle: { fontSize: 18, fontWeight: '600' },
  errorText: { fontSize: 15, textAlign: 'center', opacity: 0.8 },
  retry: { marginTop: 8, backgroundColor: '#3355dd', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 24 },
  retryText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
