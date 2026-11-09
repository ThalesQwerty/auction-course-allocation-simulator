/** O histórico de execuções no **IndexedDB**.
 *
 * Saiu do `localStorage` em 09/11/2026, quando a comparação passou a trazer as
 * séries de todos os recortes (uns 450 kB cada): o `localStorage` tem uns
 * 5 MB por origem, e o histórico ia sendo podado pelas mais antigas muito
 * antes do teto de execuções. O IndexedDB tem cota proporcional ao disco e
 * guarda o objeto como está, sem `JSON.stringify`.
 *
 * A lista inteira é **um registro só**, gravado de uma vez. A ordem dela é a
 * da tela — um arquivo carregado entra no topo com a data dele, então a data
 * não serve de ordem —, e as gravações são raras (rodar, carregar, apagar).
 *
 * As gravações saem **em fila**: duas mudanças seguidas no histórico não
 * podem terminar fora de ordem e deixar gravada a mais antiga.
 */

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
    // Falhou uma vez, tenta de novo na próxima chamada em vez de guardar o erro.
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

/** A lista gravada sob `key`, ou `undefined` se nunca se gravou nada — o que
 * distingue "histórico vazio" de "ainda não migrou do `localStorage`". A
 * chave leva a versão do formato, como a do `localStorage` levava. */
export const readEntries = <T>(key: string): Promise<T[] | undefined> =>
  run<T[] | undefined>("readonly", (store) => store.get(key));

let queue: Promise<unknown> = Promise.resolve();

/** Grava a lista inteira, depois de qualquer gravação anterior terminar. */
export function writeEntries<T>(key: string, entries: T[]): Promise<void> {
  const next = queue.then(() =>
    run<IDBValidKey>("readwrite", (store) => store.put(entries, key))
  );
  queue = next.catch(() => undefined);
  return next.then(() => undefined);
}

/** Pede ao navegador que não despeje o banco sob pouco espaço em disco. É um
 * pedido: o navegador pode negar, e aí vale a regra comum de despejo. */
export function requestPersistence(): void {
  try {
    void navigator.storage?.persist?.().catch(() => undefined);
  } catch {
    // Sem a API, não há o que pedir.
  }
}
