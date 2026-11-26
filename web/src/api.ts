import type {
  BoxesPayload,
  ComparisonHead,
  ComparisonState,
  CompareRequest,
  CompareResponse,
  CurvePayload,
  SeriesPayload,
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

/** As comparações, da mais recente para a mais antiga */
export async function listComparisons(): Promise<ComparisonHead[]> {
  return request("/comparacoes");
}

/** Cria a comparação e a fila. **Não roda nada** */
export async function createComparison(
  scenario: CompareRequest,
  label?: string
): Promise<ComparisonState> {
  const query = label ? `?rotulo=${encodeURIComponent(label)}` : "";
  return post(`/comparacoes${query}`, scenario);
}

/** Roda o que falta, em segundo plano. Serve de começo e de retomada */
export async function runComparison(
  name: string,
  workers = 1
): Promise<ComparisonState> {
  return post(`/comparacoes/${encodeURIComponent(name)}/rodar?workers=${workers}`, {});
}

export async function pauseComparison(name: string): Promise<ComparisonState> {
  return post(`/comparacoes/${encodeURIComponent(name)}/pausar`, {});
}

/** O cabeçalho e o estado de cada simulação */
export async function comparisonState(name: string): Promise<ComparisonState> {
  return request(`/comparacoes/${encodeURIComponent(name)}`);
}

/** O cenário e o cabeçalho. As visualizações têm rota própria */
export async function comparisonResult(name: string): Promise<ComparisonHead> {
  return request(`/comparacoes/${encodeURIComponent(name)}/resultado`);
}

/** A série por período, já recortada em faixas e reduzida entre as seeds */
export async function comparisonSeries(
  name: string,
  axis: string,
  cuts: number[]
): Promise<SeriesPayload> {
  const query = new URLSearchParams({ eixo: axis, cortes: cuts.join(",") });
  return request(`/comparacoes/${encodeURIComponent(name)}/series?${query}`);
}

/** A métrica sobre uma grandeza de vida inteira, em faixas de quantil */
export async function comparisonCurve(
  name: string,
  axis: string,
  bins: number
): Promise<CurvePayload> {
  const query = new URLSearchParams({ eixo: axis, pontos: String(bins) });
  return request(`/comparacoes/${encodeURIComponent(name)}/curva?${query}`);
}

/** Uma simulação inteira, aluno a aluno, lida do banco — nada é refeito */
export async function comparisonTrace(
  name: string,
  arm: string,
  seed: number
): Promise<TraceResponse> {
  const query = new URLSearchParams({ braco: arm, seed: String(seed) });
  return request(`/comparacoes/${encodeURIComponent(name)}/traco?${query}`);
}

/** O eixo X colapsado: uma caixa por (braço, métrica) sobre as seeds */
export async function comparisonBoxes(name: string): Promise<BoxesPayload> {
  return request(`/comparacoes/${encodeURIComponent(name)}/caixas`);
}

export async function deleteComparison(name: string): Promise<void> {
  await request(`/comparacoes/${encodeURIComponent(name)}`, { method: "DELETE" });
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
