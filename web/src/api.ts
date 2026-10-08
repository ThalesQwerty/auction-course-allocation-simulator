import type {
  CompareRequest,
  CompareResponse,
  SimulateRequest,
  SimulateResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** `withHistories` pede o detalhe por aluno, que num cenário grande é quase
 * toda a resposta (40 MB com 1500 alunos, contra 0,7 MB do resto). Por isso a
 * execução normal não o pede: ele só vem quando alguém abre a tela individual,
 * e a seed garante que reexecutar reconstrói o mesmo detalhe. */
export async function simulate(
  request: SimulateRequest,
  withHistories = false
): Promise<SimulateResponse> {
  return post("/simulate", { ...request, include_histories: withHistories });
}

/** Roda o mesmo cenário nos dois mecanismos, N vezes de cada lado, com as
 * seeds de 1 a N. São 2N simulações completas no servidor: num cenário grande
 * a requisição leva dezenas de segundos, e por isso a tela trava o botão em
 * vez de fingir que foi rápido. */
export async function compare(request: CompareRequest): Promise<CompareResponse> {
  return post("/compare", request);
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
