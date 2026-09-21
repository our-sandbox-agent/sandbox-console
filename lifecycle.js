// Browser demo clock: closed-page time is excluded; delayed ticks are split at transitions.
export function normalizePolicy(policy = {}) {
  const positive = (n, fallback) => Number.isFinite(n) && n > 0 ? n : fallback;
  return { idleAfter: positive(policy?.idleAfter, 120), suspendAfter: positive(policy?.suspendAfter, 300) };
}

export function restoreClock(box, now) {
  const savedAt = Number.isFinite(box.accountedAt) ? Math.min(box.accountedAt, now) : now;
  const shift = now - savedAt;
  const anchor = value => Number.isFinite(value) ? Math.min(value, savedAt) + shift : now;
  box.lastActivity = anchor(box.lastActivity);
  box.stateSince = anchor(box.stateSince);
  box.accountedAt = now;
  for (const state of ['Active', 'Idle', 'Suspend']) {
    const seconds = box.seconds[state];
    box.seconds[state] = Number.isFinite(seconds) && seconds >= 0 ? seconds : 0;
  }
  return box;
}

export function deadline(box, policy) {
  if (box.status === 'Active') return box.lastActivity + policy.idleAfter * 1000;
  if (box.status === 'Idle') return Math.max(box.stateSince, box.lastActivity) + policy.suspendAfter * 1000;
  return Infinity;
}

export function advance(box, now, policy) {
  let cursor = box.accountedAt;
  const end = Math.max(cursor, now);
  let changed = false;
  while (cursor <= end) {
    const boundary = Math.max(cursor, deadline(box, policy));
    const until = Math.min(end, boundary);
    box.seconds[box.status] += (until - cursor) / 1000;
    cursor = until;
    if (boundary > end) break;
    box.status = box.status === 'Active' ? 'Idle' : 'Suspend';
    box.stateSince = cursor;
    box.logs.push('State changed to ' + box.status + ' (auto, demo)');
    changed = true;
  }
  box.accountedAt = end;
  return changed;
}

export function setState(box, state, now, policy) {
  advance(box, now, policy);
  box.status = state;
  box.stateSince = box.accountedAt;
  box.lastActivity = box.accountedAt;
}

export function recordActivity(box, now, policy) {
  advance(box, now, policy);
  box.lastActivity = box.accountedAt;
}
