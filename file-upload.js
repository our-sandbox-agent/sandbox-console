export const UPLOAD_LIMIT_BYTES = 10 * 1024 * 1024;

export function planUpload(boxId, items) {
  if (!items || !items.length) throw new Error('沒有可上傳的檔案。');
  const seen = new Set();
  return items.map(file => {
    const path = file.webkitRelativePath || file.name;
    const key = boxId + ':' + path;
    if (file.size > UPLOAD_LIMIT_BYTES) throw new Error('單一檔案不能超過 10 MB：' + path);
    if (seen.has(key)) throw new Error('選取內容有重複的目標路徑：' + path);
    seen.add(key);
    return { box: boxId, path, key, file };
  });
}

export function findConflicts(entries, existingKeys) {
  const present = new Set(existingKeys);
  return entries.filter(e => present.has(e.key));
}

export function writeFiles(db, entries) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('files', 'readwrite');
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(tx.error || new Error('上傳未完成，請重試。'));
    tx.onerror = () => reject(tx.error || new Error('檔案儲存空間發生錯誤。'));
    const store = tx.objectStore('files');
    for (const e of entries) store.put({ key: e.key, box: e.box, path: e.path, blob: e.file });
  });
}

// The caller supplies fresh keys so a file that appeared after confirmation cannot be overwritten unseen.
export function createUploadWriter({ getBox, settle, currentKeys, write, activity }) {
  const pending = new Set();
  return async function uploadFiles({ boxId, entries, mode, confirmedKeys }) {
    if (pending.has(boxId)) throw new Error('此沙盒正在上傳中。');
    pending.add(boxId);
    try {
      settle();
      const box = getBox(boxId);
      if (!box) throw new Error('找不到這個工作空間。');
      if (box.status === 'Suspend') throw new Error('沙盒已掛起，請先 Resume 再上傳。');
      for (const e of entries) if (e.box !== boxId || e.key !== e.box + ':' + e.path) throw new Error('檔案路徑不一致，請重新載入。');
      const present = new Set(await currentKeys());
      const conflicts = entries.filter(e => present.has(e.key));
      let writeEntries = entries, skipped = 0;
      if (mode === 'skip') {
        writeEntries = entries.filter(e => !present.has(e.key));
        skipped = entries.length - writeEntries.length;
      } else if (conflicts.some(e => !confirmedKeys || !confirmedKeys.has(e.key))) {
        return { status: 'reconfirm', conflicts };
      }
      let overwritten = 0;
      if (writeEntries.length) {
        overwritten = writeEntries.filter(e => present.has(e.key)).length;
        await write(writeEntries);
        activity(box, { written: writeEntries.length, overwritten });
      }
      return { status: 'done', written: writeEntries.length, skipped, overwritten };
    } finally {
      pending.delete(boxId);
    }
  };
}
