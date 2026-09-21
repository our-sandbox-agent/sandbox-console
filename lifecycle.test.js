import { test } from 'node:test';
import assert from 'node:assert/strict';
import { restoreClock, advance, deadline, setState, recordActivity, normalizePolicy } from './lifecycle.js';

const policy = { idleAfter: 120, suspendAfter: 300 };
const fresh = () => restoreClock({ status: 'Active', seconds: { Active: 0, Idle: 0, Suspend: 0 }, logs: [] }, 0);

test('a delayed tick crosses both boundaries and conserves elapsed time', () => {
  const box = fresh();
  advance(box, 600000, policy);
  assert.equal(box.status, 'Suspend');
  assert.deepEqual(box.seconds, { Active: 120, Idle: 300, Suspend: 180 });
  advance(box, 600000, policy);
  assert.equal(box.logs.length, 2);
  assert.equal(box.seconds.Suspend, 180);
});

test('manual Idle starts its own full suspend countdown', () => {
  const box = fresh();
  setState(box, 'Idle', 10000, policy);
  assert.equal(deadline(box, policy), 310000);
  advance(box, 310000, policy);
  assert.equal(box.status, 'Suspend');
  assert.deepEqual(box.seconds, { Active: 10, Idle: 300, Suspend: 0 });
});

for (const state of ['Active', 'Idle', 'Suspend']) {
  test(`reload preserves ${state} usage and remaining countdown without offline charges`, () => {
    const box = fresh();
    setState(box, state, 0, policy);
    advance(box, 30000, policy);
    const remaining = deadline(box, policy) - 30000;
    const restored = restoreClock(JSON.parse(JSON.stringify(box)), 900000);
    assert.equal(deadline(restored, policy) - 900000, remaining);
    advance(restored, 910000, policy);
    assert.equal(restored.seconds[state], 40);
    assert.equal(restored.status, state);
  });
}

test('activity postpones the next transition after settling prior usage', () => {
  const box = fresh();
  recordActivity(box, 100000, policy);
  advance(box, 220000, policy);
  assert.equal(box.status, 'Idle');
  assert.equal(box.seconds.Active, 220);
  recordActivity(box, 230000, policy);
  assert.equal(deadline(box, policy), 530000);
});

test('manual suspend and resume settle time in the previous state', () => {
  const box = fresh();
  setState(box, 'Suspend', 2500, policy);
  setState(box, 'Active', 5500, policy);
  advance(box, 6500, policy);
  assert.deepEqual(box.seconds, { Active: 3.5, Idle: 0, Suspend: 3 });
  assert.equal(deadline(box, policy), 125500);
});

test('backward clock movement never subtracts usage or counts it twice', () => {
  const box = fresh();
  advance(box, 10000, policy);
  advance(box, 5000, policy);
  advance(box, 11000, policy);
  assert.equal(box.seconds.Active, 11);
});

test('old saved records retain usage and initialize missing timing fields', () => {
  const box = restoreClock({ status: 'Idle', seconds: { Active: 10, Idle: -1 }, logs: [] }, 1000);
  assert.deepEqual(box.seconds, { Active: 10, Idle: 0, Suspend: 0 });
  assert.equal(deadline(box, policy), 301000);
});

test('invalid policies cannot create zero-duration transition loops', () => {
  assert.deepEqual(normalizePolicy({ idleAfter: -1, suspendAfter: 'bad' }), policy);
  assert.deepEqual(normalizePolicy(null), policy);
});
