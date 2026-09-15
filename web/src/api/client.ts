import type { ComparisonOut, ScenarioInput, ScenarioOutput } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // corpo não era JSON — mantém o statusText
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listScenarios: () => request<ScenarioOutput[]>("/scenarios"),
  createScenario: (input: ScenarioInput) =>
    request<ScenarioOutput>("/scenarios", { method: "POST", body: JSON.stringify(input) }),
  getScenario: (id: string) => request<ScenarioOutput>(`/scenarios/${id}`),
  updateScenario: (id: string, input: ScenarioInput) =>
    request<ScenarioOutput>(`/scenarios/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteScenario: (id: string) => request<void>(`/scenarios/${id}`, { method: "DELETE" }),
  runSimulation: (id: string) => request<ComparisonOut>(`/scenarios/${id}/run`, { method: "POST" }),
  getResult: (id: string) => request<ComparisonOut>(`/scenarios/${id}/result`),
};
