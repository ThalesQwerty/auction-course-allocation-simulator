/** O histórico de execuções no **IndexedDB** */

const DB_NAME = "leilao";
const DB_VERSION = 1;
const STORE = "historico";

let opening: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!opening) {
    opening = new Promise((resolve, reject) => {
      if (typeof indexedDB === "undefined") {
        reject(new Error("IndexedDB indisponível"));
        return;
      }
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE)) {
          request.result.createObjectStore(STORE);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error("IndexedDB bloqueado"));
    });
    opening.catch(() => (opening = null));
  }
  return opening;
}

function run<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest
): Promise<T> {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const request = action(tx.objectStore(STORE));
        tx.oncomplete = () => resolve(request.result as T);
        tx.onerror = () => reject(tx.error ?? request.error);
        tx.onabort = () => reject(tx.error ?? request.error);
      })
  );
}

/** A lista gravada sob `key`, ou `undefined` se nunca se gravou nada — o que distingue "histórico vazio" de "ainda não migrou do `localStorage`" */
export const readEntries = <T>(key: string): Promise<T[] | undefined> =>
  run<T[] | undefined>("readonly", (store) => store.get(key));

let queue: Promise<unknown> = Promise.resolve();

export function writeEntries<T>(key: string, entries: T[]): Promise<void> {
  const next = queue.then(() =>
    run<IDBValidKey>("readwrite", (store) => store.put(entries, key))
  );
  queue = next.catch(() => undefined);
  return next.then(() => undefined);
}

/** Pede ao navegador que não despeje o banco sob pouco espaço em disco */
export function requestPersistence(): void {
  try {
    void navigator.storage?.persist?.().catch(() => undefined);
  } catch {
  }
}
