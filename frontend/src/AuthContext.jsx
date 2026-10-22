import { createContext, useContext, useEffect, useState } from "react";
import { supabase } from "./supabaseClient.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  // True from the moment someone arrives through a password reset link until they have chosen a
  // new password. The reset link signs them in with a short lived session, so without this they
  // would land on the normal page, signed in, never having been asked for the new password.
  const [recovering, setRecovering] = useState(
    typeof window !== "undefined" && /type=recovery/.test(window.location.hash)
  );

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession);
      if (event === "PASSWORD_RECOVERY") setRecovering(true);
    });

    return () => subscription.subscription.unsubscribe();
  }, []);

  const value = {
    session,
    user: session?.user ?? null,
    loading,
    signUp: (email, password) => supabase.auth.signUp({ email, password }),
    signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signInWithGoogle: () =>
      supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: window.location.origin },
      }),
    signOut: () => supabase.auth.signOut(),
    recovering,
    finishRecovery: () => setRecovering(false),
    // emails a reset link that returns to the sign in page, where the new password is chosen
    requestPasswordReset: (email) =>
      supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/auth` }),
    updatePassword: (password) => supabase.auth.updateUser({ password }),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
