// Capa de servicios: comunicación con el backend FastAPI
// Cada módulo encapsula las llamadas HTTP a un recurso específico.
//
// Ejemplo:
//   export * from "./stockService";
//   export * from "./partsService";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Cliente HTTP base reutilizable */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}
