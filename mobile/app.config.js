const { withEntitlementsPlist } = require('expo/config-plugins');

// iOS: the reminders are local notifications, which need no push entitlement. expo-notifications adds
// `aps-environment` anyway, which makes EAS switch on the Push Notifications capability for the bundle id
// (and that call fails). Drop it. Mods run in reverse order of registration, so it goes first in
// the plugin list to run after expo-notifications has set it.
const withoutPushEntitlement = config => withEntitlementsPlist(config, c => {
  delete c.modResults['aps-environment'];
  return c;
});

// iOS: WKWebView only runs a site's service worker (the planner's offline copy) on an app-bound domain,
// so the planner's host goes in WKAppBoundDomains. An EXPO_PUBLIC_PLANNER_URL build loads another host,
// which has to be listed too or the page can't load at all (App.js limits navigation to these domains).
module.exports = ({ config }) => {
  const host = /^https:\/\/([a-z0-9.-]+)(\/[^?#]*)?$/.exec(process.env.EXPO_PUBLIC_PLANNER_URL || '')?.[1];
  const domains = [...new Set(['cc26plan.nb-cs.net', ...(host ? [host] : [])])];
  return {
    ...config,
    ios: { ...config.ios, infoPlist: { ...config.ios.infoPlist, WKAppBoundDomains: domains } },
    plugins: [withoutPushEntitlement, ...(config.plugins || [])],
  };
};
