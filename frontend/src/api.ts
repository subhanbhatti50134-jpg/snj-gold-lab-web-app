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

// A unique key for one logical checkout/payment. Reuse the SAME key when
// retrying a failed request so the server records it only once; generate
// a new key for a genuinely new operation.
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers: 122 bits of randomness, UUID-shaped.
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
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

export type ApiOptions = RequestInit & {
  // Sent as the Idempotency-Key header so a retried POST is recorded
  // only once on the server.
  idempotencyKey?: string;
};

export async function api<T>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const { idempotencyKey, ...init } = options;
  const headers = new Headers(init.headers);

  headers.set("Accept", "application/json");

  if (init.body) {
    headers.set("Content-Type", "application/json");
  }

  if (idempotencyKey) {
    headers.set("Idempotency-Key", idempotencyKey);
  }

  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
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
