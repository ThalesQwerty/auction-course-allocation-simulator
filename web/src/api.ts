import type {
  CompareRequest,
  CompareResponse,
  PlaygroundRequest,
  PlaygroundResponse,
  SavedResult,
  StoredRun,
  TraceRequest,
  TraceResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";


/** Roda o mesmo cenário em cada braço da comparação, N vezes, com as seeds de 1 a N */
export async function compare(request: CompareRequest): Promise<CompareResponse> {
  return post("/compare", request);
}

/** Refaz **uma** simulação da comparação — o par (braço, seed) — e devolve o que cada aluno pediu, período a período */
export async function trace(request: TraceRequest): Promise<TraceResponse> {
  return post("/trace", request);
}

export async function playground(request: PlaygroundRequest): Promise<PlaygroundResponse> {
  return post("/playground", request);
}

/** O que há gravado em `resultados/`, do mais recente para o mais antigo */
export async function listResults(): Promise<SavedResult[]> {
  return request("/results");
}

/** Uma execução gravada, inteira */
export async function readResult(name: string): Promise<StoredRun> {
  return request(`/results/${encodeURIComponent(name)}`);
}

export async function deleteResult(name: string): Promise<void> {
  await request(`/results/${encodeURIComponent(name)}`, { method: "DELETE" });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) throw new Error(await detailOf(response));
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await detailOf(response));
  return response.json() as Promise<T>;
}

async function detailOf(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string"
      ? payload.detail
      : JSON.stringify(payload.detail);
  } catch {
    return response.statusText;
  }
}
