export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const TOKEN_KEY = "hisabpro_token";

// Fired when the backend rejects the saved token (expired or invalid).
export const UNAUTHORIZED_EVENT = "hisabpro:unauthorized";

export type Role = "admin" | "manager" | "operator" | "viewer";

export type CurrentUser = {
  id: number;
  username: string;
  role: Role;
  active: boolean;
};

const ROLE_RANK: Record<Role, number> = {
  viewer: 0,
  operator: 1,
  manager: 2,
  admin: 3
};

// True when the user's role is at least `minimum`.
export function atLeast(user: CurrentUser | null, minimum: Role): boolean {
  if (!user) return false;
  return ROLE_RANK[user.role] >= ROLE_RANK[minimum];
}

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export async function login(
  username: string,
  password: string
): Promise<void> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ username, password })
    });
  } catch {
    throw new Error(`Backend connect nahi hua. Check karein: ${API_BASE}`);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : "";
    throw new Error(detail || `Login failed: ${response.status}`);
  }

  sessionStorage.setItem(TOKEN_KEY, data.access_token);
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

  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Backend connect nahi hua. Check karein: ${API_BASE}`);
  }

  const text = await response.text();
  let data: unknown = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  const tokenRejected =
    response.status === 401 &&
    !!token &&
    typeof data === "object" &&
    data !== null &&
    (data as { detail?: string }).detail === "Invalid or expired access token";

  if (tokenRejected) {
    clearToken();
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new Error("Session expire ho gaya. Dobara login karein.");
  }

  if (!response.ok) {
    const detail =
      typeof data === "object" && data
        ? (data as { detail?: string; message?: string }).detail ||
          (data as { message?: string }).message
        : data;

    throw new Error(
      typeof detail === "string" ? detail : `API error: ${response.status}`
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

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}
