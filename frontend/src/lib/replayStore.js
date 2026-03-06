/**
 * IndexedDB-backed audio replay store (brainwave-inspired).
 * Persists audio chunks locally so a failed session can be replayed.
 *
 * Schema:
 *   sessions: { id, createdAt, status, durationMs }
 *   chunks:   { id (auto), sessionId, seq, deltaMs, kind, payload }
 */

const DB_NAME = "interview-copilot-replay";
const DB_VERSION = 1;
const MAX_SESSIONS = 5;
const MAX_BYTES = 100 * 1024 * 1024; // 100 MB

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains("sessions")) {
        db.createObjectStore("sessions", { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains("chunks")) {
        const store = db.createObjectStore("chunks", {
          keyPath: "id",
          autoIncrement: true,
        });
        store.createIndex("bySession", "sessionId", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(db, stores, mode = "readonly") {
  const t = db.transaction(stores, mode);
  return stores.length === 1 ? t.objectStore(stores[0]) : stores.map((s) => t.objectStore(s));
}

function reqP(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function createSession(sessionId) {
  const db = await openDB();
  const store = tx(db, ["sessions"], "readwrite");
  await reqP(
    store.put({
      id: sessionId,
      createdAt: Date.now(),
      status: "recording",
      durationMs: 0,
    })
  );
  // Write start marker
  const chunkStore = tx(db, ["chunks"], "readwrite");
  await reqP(
    chunkStore.add({
      sessionId,
      seq: 0,
      deltaMs: 0,
      kind: "start",
      payload: null,
    })
  );
  db.close();
}

export async function appendChunk(sessionId, seq, deltaMs, audioBuffer) {
  const db = await openDB();
  const store = tx(db, ["chunks"], "readwrite");
  await reqP(
    store.add({
      sessionId,
      seq,
      deltaMs,
      kind: "audio",
      payload: audioBuffer, // ArrayBuffer
    })
  );
  db.close();
}

export async function finishSession(sessionId, durationMs) {
  const db = await openDB();
  const sessions = tx(db, ["sessions"], "readwrite");
  const existing = await reqP(sessions.get(sessionId));
  if (existing) {
    existing.status = "completed";
    existing.durationMs = durationMs;
    await reqP(sessions.put(existing));
  }
  const chunkStore = tx(db, ["chunks"], "readwrite");
  await reqP(
    chunkStore.add({
      sessionId,
      seq: -1,
      deltaMs: durationMs,
      kind: "stop",
      payload: null,
    })
  );
  db.close();
  await enforceQuota();
}

export async function getLatestSession() {
  const db = await openDB();
  const store = tx(db, ["sessions"], "readonly");
  const all = await reqP(store.getAll());
  db.close();
  if (all.length === 0) return null;
  all.sort((a, b) => b.createdAt - a.createdAt);
  return all[0];
}

export async function getSessionChunks(sessionId) {
  const db = await openDB();
  const store = tx(db, ["chunks"], "readonly");
  const idx = store.index("bySession");
  const chunks = await reqP(idx.getAll(sessionId));
  db.close();
  return chunks
    .filter((c) => c.kind === "audio")
    .sort((a, b) => a.seq - b.seq);
}

export async function enforceQuota() {
  const db = await openDB();
  const sessStore = tx(db, ["sessions"], "readonly");
  const sessions = await reqP(sessStore.getAll());
  if (sessions.length <= MAX_SESSIONS) {
    db.close();
    return;
  }
  sessions.sort((a, b) => a.createdAt - b.createdAt);
  const toDelete = sessions.slice(0, sessions.length - MAX_SESSIONS);
  for (const s of toDelete) {
    await deleteSession(s.id);
  }
  db.close();
}

async function deleteSession(sessionId) {
  const db = await openDB();
  const sessStore = tx(db, ["sessions"], "readwrite");
  await reqP(sessStore.delete(sessionId));

  const chunkStore = tx(db, ["chunks"], "readwrite");
  const idx = chunkStore.index("bySession");
  const keys = await reqP(idx.getAllKeys(sessionId));
  for (const k of keys) {
    chunkStore.delete(k);
  }
  db.close();
}

export async function hasReplayData() {
  const latest = await getLatestSession();
  return latest !== null;
}
