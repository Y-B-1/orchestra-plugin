import { expect, test } from 'claude-code/testing';

import { deferred, EXPECTED_DIGEST, rig } from './testkit.js';

const start = { cwd: '/work/proj', surface: null, isInteractive: false } as const;
const end = (reason: string, sessionId: string) => ({ reason, sessionId, resume: {} as never }) as never;
const MARKER = (id: string) => `/state/orchestra/mods/${id}.json`;

test('session.start writes a fresh marker: version, digest and clock heartbeat', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  expect(r.writes.length).toBe(1);
  expect(r.writes[0]!.path).toBe(MARKER('sid-1'));
  expect(r.writes[0]!.json).toEqual({
    session_id: 'sid-1',
    heartbeat_ms: 1000,
    plugin_version: '2.0.0',
    rules_sha256: EXPECTED_DIGEST,
  });
});

test('the marker directory defaults under HOME when XDG_STATE_HOME is unset', async ($, on) => {
  const r = rig(on, { env: { HOME: '/home/x' } });
  await $.session.start(start);
  expect(r.writes.map((w) => w.path)).toEqual(['/home/x/.local/state/orchestra/mods/sid-1.json']);
});

test('one tick refreshes the marker every 5 seconds from the clock', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  await r.clock.advance(5000);
  await r.clock.advance(5000);
  expect(r.of('sid-1').map((w) => w.json.heartbeat_ms)).toEqual([1000, 6000, 11000]);
});

test('no XDG_STATE_HOME and no HOME: no marker is written and the tick never starts', async ($, on) => {
  const r = rig(on, { env: {} });
  await $.session.start(start);
  await r.clock.advance(20000);
  expect(r.started).toEqual([]);
});

test('invalid guard rules: no marker is written', async ($, on) => {
  const r = rig(on, { files: { 'config/guard-rules.json': '{not json' } });
  await $.session.start(start);
  await r.clock.advance(10000);
  expect(r.started).toEqual([]);
});

test('clear retires the old id and the next tick writes the new id', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  await $.session.end(end('clear', 'sid-1'));
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(0);
  r.id = 'sid-2';
  await r.clock.advance(5000);
  expect(r.of('sid-2').map((w) => w.json.heartbeat_ms)).toEqual([6000]);
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(0);
  await r.clock.advance(5000);
  expect(r.of('sid-2').map((w) => w.json.heartbeat_ms)).toEqual([6000, 11000]);
});

test('resume retires the old id and the next tick writes the new id', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  await $.session.end(end('resume', 'sid-1'));
  r.id = 'sid-9';
  await r.clock.advance(5000);
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(0);
  expect(r.of('sid-9').at(-1)!.json.heartbeat_ms).toBe(6000);
});

for (const reason of ['prompt_input_exit', 'logout', 'other']) {
  test(`${reason} cancels the tick and leaves a zero heartbeat`, async ($, on) => {
    const r = rig(on);
    await $.session.start(start);
    await $.session.end(end(reason, 'sid-1'));
    const before = r.writes.length;
    await r.clock.advance(20000);
    expect(r.writes.length).toBe(before);
    expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(0);
  });
}

test('a second session.start leaves exactly one tick', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  await $.session.start(start);
  const before = r.writes.length;
  await r.clock.advance(5000);
  expect(r.writes.length - before).toBe(1);
  await r.clock.advance(5000);
  expect(r.writes.length - before).toBe(2);
});

test('after /clear, returning to the first id gives fresh markers again', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  await $.session.end(end('clear', 'sid-1'));
  r.id = 'sid-2';
  await r.clock.advance(5000);
  r.id = 'sid-1';
  await r.clock.advance(5000);
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(11000);
  await r.clock.advance(5000);
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(16000);
});

test('/clear then session.start under the first id writes fresh markers', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  await $.session.end(end('clear', 'sid-1'));
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(0);
  await $.session.start(start);
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBeGreaterThan(0);
  await r.clock.advance(5000);
  expect(r.of('sid-1').at(-1)!.json.heartbeat_ms).toBe(6000);
});

test('a fresh write held in flight when session.end runs ends with heartbeat_ms 0 as the last write', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  const gate = deferred();
  r.beforeWrite = async (w) => {
    if (w.json.heartbeat_ms > 0) await gate.promise;
  };
  await r.clock.advance(5000);
  expect(r.started.at(-1)!.json.heartbeat_ms).toBe(6000);
  const ending = $.session.end(end('other', 'sid-1'));
  await r.clock.settle();
  gate.resolve();
  await ending;
  await r.clock.settle();
  expect(r.writes.at(-1)!.json.heartbeat_ms).toBe(0);
  expect(r.writes.at(-1)!.json.session_id).toBe('sid-1');
});

test('the same with clock.now held late', async ($, on) => {
  const r = rig(on, { lateClock: true });
  await $.session.start(start);
  const gate = deferred();
  r.nowGate = gate.promise;
  await r.clock.advance(5000);
  const ending = $.session.end(end('other', 'sid-1'));
  await r.clock.settle();
  gate.resolve();
  await ending;
  await r.clock.settle();
  expect(r.writes.at(-1)!.json.heartbeat_ms).toBe(0);
});

test('the same with session.id held late', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  const gate = deferred();
  r.idGate = gate.promise;
  await r.clock.advance(5000);
  const ending = $.session.end(end('other', 'sid-1'));
  await r.clock.settle();
  gate.resolve();
  await ending;
  await r.clock.settle();
  expect(r.writes.at(-1)!.json.heartbeat_ms).toBe(0);
});

test('a rejected write does not skip the next queued write', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  let failures = 1;
  r.beforeWrite = async () => {
    if (failures-- > 0) throw new Error('disk full');
  };
  await r.clock.advance(5000);
  await r.clock.advance(5000);
  expect(r.of('sid-1').map((w) => w.json.heartbeat_ms)).toEqual([1000, 11000]);
  await $.session.end(end('other', 'sid-1'));
  expect(r.writes.at(-1)!.json.heartbeat_ms).toBe(0);
});

test('a throwing tick writes nothing and the next tick still runs', async ($, on) => {
  const r = rig(on);
  await $.session.start(start);
  const before = r.writes.length;
  r.idGate = Promise.reject(new Error('id unavailable'));
  r.idGate.catch(() => undefined);
  await r.clock.advance(5000);
  expect(r.writes.length).toBe(before);
  r.idGate = null;
  await r.clock.advance(5000);
  expect(r.writes.length).toBe(before + 1);
});
