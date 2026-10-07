import { test } from 'node:test';
import assert from 'node:assert/strict';
import { melTime, parsePlan, buildReminders, scheduleKey } from '../src/reminders.js';

const at = (d, hh, mm) => Date.UTC(2026, 9, d, hh - 11, mm); // Melbourne AEDT -> UTC ms
const msg = (over = {}) => JSON.stringify({
  type: 'cc26-plan', v: 1, remind: 10,
  sessions: [
    { id: 'a', title: 'Opening keynote', loc: 'Plenary Theatre', start: at(14, 9, 0), end: at(14, 10, 0), from: null, walk: null },
    { id: 'b', title: 'Agentic AI', loc: 'Room 204', start: at(14, 11, 10), end: at(14, 11, 50), from: 'Plenary Theatre', walk: 7 },
  ],
  ...over,
});

test('melTime formats Melbourne time regardless of device zone', () => {
  assert.equal(melTime(at(14, 9, 0)), '9:00 am');
  assert.equal(melTime(at(14, 12, 5)), '12:05 pm');
  assert.equal(melTime(at(15, 0, 30)), '12:30 am');
  assert.equal(melTime(at(16, 17, 45)), '5:45 pm');
});

test('parsePlan rejects other messages and bad input', () => {
  assert.equal(parsePlan('not json'), null);
  assert.equal(parsePlan(JSON.stringify({ type: 'cc26-file' })), null);
  assert.equal(parsePlan(msg({ v: 2 })), null);
  assert.equal(parsePlan(msg({ remind: 'x' })).remind, 10);
  assert.equal(parsePlan(msg({ sessions: [{ id: 'z' }, null] })).sessions.length, 0);
});

test('one reminder per session, remind minutes before, with room and walk', () => {
  const r = buildReminders(parsePlan(msg()), at(13, 12, 0));
  assert.equal(r.length, 2);
  assert.equal(r[0].at, at(14, 8, 50));
  assert.equal(r[0].title, 'In 10 min: Opening keynote');
  assert.equal(r[0].body, '9:00 am · Plenary Theatre');
  assert.equal(r[1].body, '11:10 am · Room 204 · 7 min walk from Plenary Theatre');
  assert.deepEqual(r[1].data, { session: 'b' });
});

test('no reminders when turned off or already due', () => {
  assert.deepEqual(buildReminders(parsePlan(msg({ remind: 0 })), at(13, 12, 0)), []);
  const r = buildReminders(parsePlan(msg()), at(14, 8, 55)); // keynote reminder (8:50) has passed
  assert.deepEqual(r.map(x => x.id), ['cc26-b']);
});

test('scheduleKey changes when the plan or setting changes', () => {
  const now = at(13, 12, 0);
  const k = scheduleKey(buildReminders(parsePlan(msg()), now));
  assert.equal(k, scheduleKey(buildReminders(parsePlan(msg()), now)));
  assert.notEqual(k, scheduleKey(buildReminders(parsePlan(msg({ remind: 5 })), now)));
});
