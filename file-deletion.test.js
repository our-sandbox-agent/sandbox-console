import { test } from 'node:test';
import assert from 'node:assert/strict';
import { IDBFactory } from 'fake-indexeddb';
import { createFileDeleter, deleteStoredFile } from './file-deletion.js';

const target = { box: 'a', path: 'src/file.txt', key: 'a:src/file.txt' };
async function database() {
  const factory = new IDBFactory();
  const db = await new Promise(resolve => {
    const request = factory.open('test', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('files', { keyPath: 'key' });
    request.onsuccess = () => resolve(request.result);
  });
  await new Promise(resolve => {
    const tx = db.transaction('files', 'readwrite');
    for (const key of [target.key, 'b:src/file.txt', 'a:other/file.txt']) tx.objectStore('files').put({ key, bytes: [0, 255, 12] });
    tx.oncomplete = resolve;
  });
  return db;
}
const rows = db => new Promise(resolve => {
  const req = db.transaction('files').objectStore('files').getAll();
  req.onsuccess = () => resolve(req.result);
});

test('committed deletion removes only the exact sandbox and relative path', async () => {
  const db = await database();
  await deleteStoredFile(db, target.key);
  assert.deepEqual(await rows(db), [
    { key: 'a:other/file.txt', bytes: [0, 255, 12] },
    { key: 'b:src/file.txt', bytes: [0, 255, 12] }
  ]);
  db.close();
});

test('aborted deletion keeps bytes and allows a successful retry without recording failed activity', async () => {
  const db = await database();
  const before = await rows(db);
  let failed = true, activities = 0;
  const remove = key => deleteStoredFile(failed ? {
    transaction(...args) {
      const tx = db.transaction(...args);
      queueMicrotask(() => tx.abort());
      return tx;
    }
  } : db, key);
  const del = createFileDeleter({ getBox: () => ({ status: 'Idle' }), settle() {}, remove, activity() { activities++; } });
  await assert.rejects(del(target));
  assert.deepEqual(await rows(db), before);
  assert.equal(activities, 0);
  failed = false;
  await del(target);
  assert.equal(activities, 1);
  assert.equal((await rows(db)).length, 2);
  db.close();
});

test('confirmation settles time before checking whether the sandbox became suspended', async () => {
  const box = { status: 'Active' };
  const del = createFileDeleter({ getBox: () => box, settle() { box.status = 'Suspend'; }, remove() { assert.fail('must not delete'); }, activity() { assert.fail('must not touch'); } });
  await assert.rejects(del(target), /Resume/);
});

test('duplicate requests cannot submit two transactions', async () => {
  let finish, calls = 0;
  const del = createFileDeleter({ getBox: () => ({ status: 'Active' }), settle() {}, remove() { calls++; return new Promise(resolve => { finish = resolve; }); }, activity() {} });
  const first = del(target);
  await assert.rejects(del(target), /正在刪除/);
  finish();
  await first;
  assert.equal(calls, 1);
});

test('a mismatched key cannot delete another sandbox file', async () => {
  const del = createFileDeleter({ getBox: () => ({ status: 'Active' }), settle() {}, remove() { assert.fail('must not delete'); }, activity() {} });
  await assert.rejects(del({ ...target, key: 'b:src/file.txt' }), /不一致/);
});
