# CC26 Planner app (Android / iOS)

A small native wrapper around the planner site that adds **reminders on the phone** for your Going
sessions: "In 10 min: Agentic AI · 11:10 am · Room 204 · 7 min walk from Plenary Theatre".
It uses the planner's own **Alert before each session** setting (More menu); "None" turns them off.

Everything stays on the phone: no server, accounts, analytics or push service. Reminders are local
scheduled notifications. The app loads nothing beyond what the planner page itself loads (the site,
and in the public edition MCEC's floor plans from issuu), and it adds `CC26PlannerApp/1` to the WebView's
user agent so the page knows it can hand over the plan.

## How it works

- `App.js` loads https://cc26plan.nb-cs.net in a WebView. The site's service worker keeps it working
  offline, and program updates arrive the same way they do in a browser. (iOS only runs a service worker
  in an app's WebView for its app-bound domains, so `app.config.js` lists the planner's host.)
- When your plan or alert setting changes, the page's `nativeSync()` (in `src/planner.html`) posts
  your Going sessions to the app: id, title, room, start/end as UTC ms, and the walk from the
  session you'll have just left. In a normal browser it does nothing.
- `src/reminders.js` turns that into one reminder per future session; `src/notify.js` replaces the
  scheduled reminders with that list (only when something changed).
- Backup, calendar and CSV exports go through the phone's share sheet. A WebView can't download blobs,
  so the page's `download()` hands the file to the app instead.
- Links away from the planner (official session pages, GitHub feedback) open in the browser.
- Tapping a reminder opens the **Now** tab.
- `src/bridge.js` adds the same hook from outside for any copy of the site deployed before
  `nativeSync()` existed, so the app works against either.

**Exact alarms (Android 12+):** without the "Alarms & reminders" permission, Android may deliver a
reminder several minutes late. Android 14+ turns it off by default, so the app asks once and links to
the switch (`modules/exact-alarm`).

**Force stop clears them:** Android's *Settings › Apps › Force stop* cancels every reminder the app has
scheduled, until you next open it (it reschedules on launch). Swiping it away from recent apps doesn't.

**Your plan is per app:** the app has its own storage, separate from your browser. To bring a plan
across from a laptop, use **My plan › More › Send to another device** there, then in the app use
**My plan › More › Receive from another device** and choose **Scan QR code** (or paste the link).
The app uses the system scanner (Google code scanner on Android, which needs no camera permission;
VisionKit on iOS, which asks for the camera) and only accepts a planner transfer link. Scanning the
QR code with the phone's own camera app opens the browser instead, so its plan would land there.

## Build

Needs Node 22+, Python with Pillow (`pip install -r ../requirements.txt`) (the app icons are drawn from the site's icon by
`scripts/icons.py` and never committed, because `tools/build.py --check` keeps images out of the repo),
and for local Android builds the Android SDK with Android Studio's JDK.

```powershell
cd mobile
npm install
npm test                      # reminder logic (node:test)
npm run prebuild              # icons + android/ (generated, gitignored)
npm run android               # release build installed on a USB-connected phone
```

`EXPO_PUBLIC_PLANNER_URL=https://...` points a build at another copy of the site, and
`EXPO_PUBLIC_WEBVIEW_DEBUG=1` lets `chrome://inspect` attach to the WebView (local test builds only).

Store and TestFlight builds use EAS: `npm run build:android` / `npm run build:ios` draw the icons
locally and start `eas build --profile production` (`eas submit` sends Android builds to the Play
internal track). The repo-root `.easignore` uploads the drawn icons with the build, so the EAS
builder needs no Python; it otherwise mirrors the `.gitignore` files.
