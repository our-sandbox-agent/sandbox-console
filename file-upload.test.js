import { test } from 'node:test';
import assert from 'node:assert/strict';
import { IDBFactory } from 'fake-indexeddb';
import { planUpload, findConflicts, writeFiles, createUploadWriter, UPLOAD_LIMIT_BYTES } from './file-upload.js';

const file = (name, size = 10, rel) => ({ name, size, webkitRelativePath: rel });
async function database(seed = []) {
  const factory = new IDBFactory();
  const db = await new Promise(resolve => {
    const request = factory.open('test', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('files', { keyPath: 'key' });
    request.onsuccess = () => resolve(request.result);
  });
  if (seed.length) await writeFiles(db, seed);
  return db;
}
const rows = db => new Promise(resolve => {
  const req = db.transaction('files').objectStore('files').getAll();
  req.onsuccess = () => resolve(req.result);
});
const entry = (box, path, blob) => ({ box, path, key: box + ':' + path, file: blob });

test('planning keeps folder-relative paths, the 10 MB limit and rejects duplicate targets', () => {
  const entries = planUpload('a', [file('a.txt', 10, 'proj/src/a.txt'), file('b.txt')]);
  assert.equal(entries[0].path, 'proj/src/a.txt');
  assert.equal(entries[0].key, 'a:proj/src/a.txt');
  assert.equal(entries[1].path, 'b.txt');
  assert.throws(() => planUpload('a', [file('big.bin', UPLOAD_LIMIT_BYTES + 1)]), /10 MB/);
  assert.throws(() => planUpload('a', [file('a.txt', 1, 'proj/a.txt'), file('renamed.txt', 1, 'proj/a.txt')]), /重複/);
  assert.throws(() => planUpload('a', []), /沒有/);
});

test('conflicts match the exact sandbox and full relative path only', () => {
  const entries = [entry('a', 'src/file.txt'), entry('a', 'note.txt')];
  const conflicting = findConflicts(entries, ['a:src/file.txt', 'b:src/file.txt', 'a:other/file.txt', 'a:note.txtx']);
  assert.deepEqual(conflicting.map(e => e.key), ['a:src/file.txt']);
});

test('skip mode writes only non-conflicting files and keeps existing bytes', async () => {
  const db = await database([entry('a', 'src/file.txt', { seeded: true })]);
  const calls = [];
  const uploadFiles = createUploadWriter({
    getBox: () => ({ status: 'Active' }), settle() {}, currentKeys: async () => ['a:src/file.txt'],
    write: async e => { calls.push(e); await writeFiles(db, e); }, activity() {}
  });
  const result = await uploadFiles({ boxId: 'a', entries: [entry('a', 'src/file.txt', { fresh: 1 }), entry('a', 'new.txt', { fresh: 2 })], mode: 'skip' });
  assert.deepEqual(result, { status: 'done', written: 1, skipped: 1, overwritten: 0 });
  assert.equal(calls.length, 1);
  const stored = await rows(db);
  assert.deepEqual(stored.find(r => r.key === 'a:src/file.txt').blob, { seeded: true });
  assert.deepEqual(stored.find(r => r.key === 'a:new.txt').blob, { fresh: 2 });
  db.close();
});

test('overwrite mode replaces bytes and reports the overwritten count', async () => {
  const db = await database([entry('a', 'src/file.txt', { seeded: true })]);
  const logs = [];
  const uploadFiles = createUploadWriter({
    getBox: () => ({ status: 'Active' }), settle() {}, currentKeys: async () => ['a:src/file.txt'],
    write: e => writeFiles(db, e), activity(box, c) { logs.push(c); }
  });
  const result = await uploadFiles({ boxId: 'a', entries: [entry('a', 'src/file.txt', { fresh: 1 }), entry('a', 'new.txt', { fresh: 2 })], mode: 'overwrite', confirmedKeys: new Set(['a:src/file.txt']) });
  assert.deepEqual(result, { status: 'done', written: 2, skipped: 0, overwritten: 1 });
  assert.deepEqual(logs, [{ written: 2, overwritten: 1 }]);
  assert.deepEqual((await rows(db)).find(r => r.key === 'a:src/file.txt').blob, { fresh: 1 });
  db.close();
});

test('a file that appeared after confirmation forces reconfirm without writing', async () => {
  const db = await database([entry('a', 'src/file.txt', { seeded: true })]);
  const uploadFiles = createUploadWriter({
    getBox: () => ({ status: 'Active' }), settle() {},
    currentKeys: async () => ['a:src/file.txt', 'a:late.txt'],
    write() { assert.fail('must not write'); }, activity() { assert.fail('must not touch'); }
  });
  const result = await uploadFiles({ boxId: 'a', entries: [entry('a', 'src/file.txt', {}), entry('a', 'late.txt', {})], mode: 'overwrite', confirmedKeys: new Set(['a:src/file.txt']) });
  assert.equal(result.status, 'reconfirm');
  assert.deepEqual(result.conflicts.map(e => e.key), ['a:src/file.txt', 'a:late.txt']);
  assert.deepEqual(await rows(db), [{ key: 'a:src/file.txt', box: 'a', path: 'src/file.txt', blob: { seeded: true } }]);
  db.close();
});

test('an aborted batch rolls back every file and records no activity', async () => {
  const db = await database([entry('a', 'seed.txt', { seeded: true })]);
  let failed = true, activities = 0;
  const uploadFiles = createUploadWriter({
    getBox: () => ({ status: 'Active' }), settle() {}, currentKeys: async () => [],
    write: async e => writeFiles(failed ? {
      transaction(...args) {
        const tx = db.transaction(...args);
        queueMicrotask(() => tx.abort());
        return tx;
      }
    } : db, e), activity() { activities++; }
  });
  await assert.rejects(uploadFiles({ boxId: 'a', entries: [entry('a', 'x.txt', {}), entry('a', 'y.txt', {})], mode: 'skip' }));
  assert.deepEqual(await rows(db), [{ key: 'a:seed.txt', box: 'a', path: 'seed.txt', blob: { seeded: true } }]);
  assert.equal(activities, 0);
  failed = false;
  const result = await uploadFiles({ boxId: 'a', entries: [entry('a', 'x.txt', {})], mode: 'skip' });
  assert.equal(result.written, 1);
  assert.equal(activities, 1);
  db.close();
});

test('confirmation settles time before checking whether the sandbox became suspended', async () => {
  const box = { status: 'Active' };
  const uploadFiles = createUploadWriter({ getBox: () => box, settle() { box.status = 'Suspend'; }, currentKeys: async () => [], write() { assert.fail('must not write'); }, activity() { assert.fail('must not touch'); } });
  await assert.rejects(uploadFiles({ boxId: 'a', entries: [entry('a', 'x.txt', {})], mode: 'skip' }), /Resume/);
});

test('duplicate submissions cannot start two batches', async () => {
  let finish;
  const uploadFiles = createUploadWriter({ getBox: () => ({ status: 'Active' }), settle() {}, currentKeys: async () => [], write() { return new Promise(resolve => { finish = resolve; }); }, activity() {} });
  const first = uploadFiles({ boxId: 'a', entries: [entry('a', 'x.txt', {})], mode: 'skip' });
  await assert.rejects(uploadFiles({ boxId: 'a', entries: [entry('a', 'y.txt', {})], mode: 'skip' }), /正在上傳/);
  finish();
  assert.equal((await first).written, 1);
});

test('a mismatched key cannot write into another sandbox', async () => {
  const uploadFiles = createUploadWriter({ getBox: () => ({ status: 'Active' }), settle() {}, currentKeys: async () => [], write() { assert.fail('must not write'); }, activity() { assert.fail('must not touch'); } });
  await assert.rejects(uploadFiles({ boxId: 'a', entries: [entry('b', 'x.txt', {})], mode: 'skip' }), /不一致/);
});
