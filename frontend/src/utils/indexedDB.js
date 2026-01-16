export async function openDB(name, version) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(name, version);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveToIndexedDB(db, store, data) {
  const tx = db.transaction(store, 'readwrite');
  tx.objectStore(store).put(data);
  return tx.complete;
}

export async function loadFromIndexedDB(db, store, key) {
  const tx = db.transaction(store, 'readonly');
  return tx.objectStore(store).get(key);
}
