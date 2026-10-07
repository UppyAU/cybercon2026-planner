// Turns the planner's "cc26-plan" message into the reminders to schedule. Pure (no React Native),
// so the node tests can run it. The message comes from nativeSync() in src/planner.html:
//   {type: "cc26-plan", v: 1, remind: minutes before (0 = off),
//    sessions: [{id, title, loc, start, end (UTC ms), from: room you'll have just left | null, walk: minutes | null}]}

const AEDT = 11 * 60 * 60 * 1000; // the whole conference is in Melbourne summer time

// "11:10 am", in Melbourne whatever zone the phone is set to (Hermes' Intl timeZone support varies).
export function melTime(ms) {
  const d = new Date(ms + AEDT);
  const h = d.getUTCHours(), m = d.getUTCMinutes();
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'am' : 'pm'}`;
}

export function parsePlan(raw) {
  let msg;
  try { msg = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch { return null; }
  if (!msg || msg.type !== 'cc26-plan' || msg.v !== 1 || !Array.isArray(msg.sessions)) return null;
  const remind = Number.isFinite(msg.remind) && msg.remind >= 0 && msg.remind <= 120 ? msg.remind : 10;
  const sessions = msg.sessions.filter(s => s && typeof s.id === 'string' && typeof s.title === 'string' && Number.isFinite(s.start));
  return { remind, sessions };
}

// One reminder per future Going session, `remind` minutes before it starts. A session whose
// reminder time has already passed gets none: you're either in the app or already there.
// (notify.js won't newly schedule one due in the next couple of seconds, but keeps it if already set.)
export function buildReminders(plan, now = Date.now()) {
  if (!plan || !plan.remind) return [];
  return plan.sessions
    .map(s => ({ s, at: s.start - plan.remind * 60000 }))
    .filter(({ at }) => at > now)
    .map(({ s, at }) => {
      const where = s.loc ? ` · ${s.loc}` : '';
      const walk = s.walk && s.from ? ` · ${s.walk} min walk from ${s.from}` : '';
      return {
        id: `cc26-${s.id}`,
        at,
        title: `In ${plan.remind} min: ${s.title}`,
        body: `${melTime(s.start)}${where}${walk}`,
        data: { session: s.id },
      };
    });
}

// Cheap identity for a schedule, so an unchanged plan isn't cancelled and re-scheduled on every page load.
export const scheduleKey = list => list.map(r => `${r.id}@${r.at}|${r.title}|${r.body}`).join('\n');
