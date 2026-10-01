import type { SimulateRequest, SimulateResponse } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** `withHistories` pede o detalhe por aluno, que num cenário grande é quase
 * toda a resposta (40 MB com 1500 alunos, contra 0,7 MB do resto). Por isso a
 * execução normal não o pede: ele só vem quando alguém abre a tela individual,
 * e a seed garante que reexecutar reconstrói o mesmo detalhe. */
export async function simulate(
  request: SimulateRequest,
  withHistories = false
): Promise<SimulateResponse> {
  const response = await fetch(`${BASE_URL}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, include_histories: withHistories }),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // corpo não era JSON — mantém o statusText
    }
    throw new Error(detail);
  }
  return response.json() as Promise<SimulateResponse>;
}
