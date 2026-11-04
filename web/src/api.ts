import type {
  CompareRequest,
  CompareResponse,
  EvolveRequest,
  EvolveResponse,
  PlaygroundRequest,
  PlaygroundResponse,
  TraceRequest,
  TraceResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";


/** Roda o mesmo cenário em cada braço da comparação, N vezes, com as seeds de
 * 1 a N. São N simulações completas por braço no servidor: num cenário grande
 * a requisição leva dezenas de segundos, e por isso a tela trava o botão em
 * vez de fingir que foi rápido. */
export async function compare(request: CompareRequest): Promise<CompareResponse> {
  return post("/compare", request);
}

/** Roda o algoritmo genético sobre o cenário. São `observations × gerações`
 * simulações completas no servidor — é a requisição mais cara da API, e os
 * dois tetos são o que separa um teste de minutos de um de horas. */
export async function evolve(request: EvolveRequest): Promise<EvolveResponse> {
  return post("/evolve", request);
}

/** Refaz **uma** observação da comparação — o par (braço, seed) — e devolve o
 * que cada aluno pediu, período a período. É uma simulação completa no
 * servidor e a maior resposta da API (uns 10 MB no preset Computação, ~1
 * comprimidos), então a tela só a pede quando alguém quer o caso individual. */
export async function trace(request: TraceRequest): Promise<TraceResponse> {
  return post("/trace", request);
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
