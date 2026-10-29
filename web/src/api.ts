import type {
  CompareRequest,
  CompareResponse,
  PlaygroundRequest,
  PlaygroundResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";


/** Roda o mesmo cenário em cada braço da comparação, N vezes, com as seeds de
 * 1 a N. São N simulações completas por braço no servidor: num cenário grande
 * a requisição leva dezenas de segundos, e por isso a tela trava o botão em
 * vez de fingir que foi rápido. */
export async function compare(request: CompareRequest): Promise<CompareResponse> {
  return post("/compare", request);
}

export async function playground(request: PlaygroundRequest): Promise<PlaygroundResponse> {
  return post("/playground", request);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail =
        typeof payload.detail === "string"
          ? payload.detail
          : JSON.stringify(payload.detail);
    } catch {
      // corpo não era JSON — mantém o statusText
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
