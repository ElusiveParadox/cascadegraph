import { createContext, useContext, type ReactNode } from "react";

export type AuthState = {
  /** False when no Clerk publishable key is configured (local/CI). */
  available: boolean;
  /** True once Clerk has resolved the current identity (always true when unavailable). */
  ready: boolean;
  signedIn: boolean;
  displayName: string | null;
  email: string | null;
  /** Clears the anonymous browser cookie, then ends the Clerk session. Throws on failure. */
  signOut: () => Promise<void>;
};

const unavailable: AuthState = {
  available: false,
  ready: true,
  signedIn: false,
  displayName: null,
  email: null,
  signOut: async () => {},
};

const AuthContext = createContext<AuthState>(unavailable);

export function AuthStateProvider({ value, children }: { value: AuthState; children: ReactNode }) {
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthState(): AuthState {
  return useContext(AuthContext);
}

export const AUTH_UNAVAILABLE = unavailable;

/** Ask the API to expire the anonymous ownership cookie. 204 expected; no body. */
export async function clearBrowserCookie(): Promise<void> {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  const res = await fetch(`${base}/api/v1/auth/sign-out`, { method: "POST", credentials: "same-origin" });
  if (!res.ok) throw new Error(`Sign out failed (HTTP ${res.status}). Your session is unchanged.`);
}
