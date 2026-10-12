const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export function getApiKey(): string {
  return sessionStorage.getItem("hisabpro_api_key") || "";
}

export function setApiKey(key: string): void {
  if (key.trim()) {
    sessionStorage.setItem("hisabpro_api_key", key.trim());
  } else {
    sessionStorage.removeItem("hisabpro_api_key");
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  const key = getApiKey();

  if (key) {
    headers.set("X-API-Key", key);
  }

  let response: Response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers
    });
  } catch {
    throw new Error(
      `Backend connect nahi hua. Check karein: ${API_BASE}`
    );
  }

  const text = await response.text();
  let data: any = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail =
      typeof data === "object" && data
        ? data.detail || data.message
        : data;

    throw new Error(
      typeof detail === "string"
        ? detail
        : `API error: ${response.status}`
    );
  }

  return data as T;
}

export function money(value: unknown): string {
  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency: "PKR",
    maximumFractionDigits: 2
  }).format(Number(value || 0));
}

export function qty(value: unknown): string {
  return new Intl.NumberFormat("en-PK", {
    maximumFractionDigits: 3
  }).format(Number(value || 0));
}
