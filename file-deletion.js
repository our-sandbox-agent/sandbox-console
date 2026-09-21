export function deleteStoredFile(db, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('files', 'readwrite');
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(tx.error || new Error('刪除未完成，請重試。'));
    tx.onerror = () => reject(tx.error || new Error('檔案儲存空間發生錯誤。'));
    tx.objectStore('files').delete(key);
  });
}

// The caller supplies a transaction that resolves only after IndexedDB commits.
export function createFileDeleter({ getBox, settle, remove, activity }) {
  const pending = new Set();
  return async function deleteFile(target) {
    if (pending.has(target.key)) throw new Error('此檔案正在刪除中。');
    pending.add(target.key);
    try {
      settle();
      const box = getBox(target.box);
      if (!box) throw new Error('找不到這個工作空間。');
      if (box.status === 'Suspend') throw new Error('沙盒已掛起，請先 Resume 再刪除。');
      if (target.key !== target.box + ':' + target.path) throw new Error('檔案路徑不一致，請重新載入。');
      await remove(target.key);
      activity(box);
    } finally {
      pending.delete(target.key);
    }
  };
}
