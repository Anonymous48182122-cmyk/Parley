import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

function Divider() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "2px 0" }}>
      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
      <span style={{ color: "var(--text-faint)", fontSize: "0.75rem" }}>or</span>
      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
    </div>
  );
}

export default function AuthPage() {
  const { signUp, signIn, signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (mode === "signup") {
        const { error: err } = await signUp(email, password);
        if (err) throw err;
        setInfo("Check your email to confirm your account, then sign in.");
      } else {
        const { error: err } = await signIn(email, password);
        if (err) throw err;
        navigate("/");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleGoogle() {
    setError(null);
    try {
      const { error: err } = await signInWithGoogle();
      if (err) throw err;
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container" style={{ maxWidth: 400 }}>
      <div style={{ marginTop: 40, marginBottom: 36, textAlign: "center" }}>
        <img
          src="/icon-192.png"
          alt="Parley"
          style={{ width: 52, height: 52, borderRadius: "14px", margin: "0 auto 20px", display: "block" }}
        />
        <h1 style={{ fontSize: "1.9rem", marginBottom: 10 }}>
          {mode === "signup" ? "Create your account" : "Welcome back"}
        </h1>
        <p style={{ color: "var(--text-dim)", fontSize: "0.92rem", lineHeight: 1.5 }}>
          Save every committee session and pick up where you left off.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card fade-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoFocus
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />

        {error && (
          <div style={{ color: "var(--danger)", fontSize: "0.85rem", lineHeight: 1.5 }}>{error}</div>
        )}
        {info && <div style={{ color: "var(--gold)", fontSize: "0.85rem", lineHeight: 1.5 }}>{info}</div>}

        <button type="submit" className="button-primary" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Please wait…" : mode === "signup" ? "Sign Up" : "Sign In"}
        </button>

        <Divider />

        <button type="button" className="button-secondary" style={{ width: "100%" }} onClick={handleGoogle}>
          Continue with Google
        </button>
      </form>

      <div style={{ textAlign: "center", marginTop: 22, fontSize: "0.88rem", color: "var(--text-dim)" }}>
        {mode === "signup" ? (
          <>
            Already have an account?{" "}
            <button
              className="button-secondary"
              style={{ border: "none", background: "none", padding: 0, color: "var(--gold)" }}
              onClick={() => setMode("signin")}
            >
              Sign in
            </button>
          </>
        ) : (
          <>
            New here?{" "}
            <button
              className="button-secondary"
              style={{ border: "none", background: "none", padding: 0, color: "var(--gold)" }}
              onClick={() => setMode("signup")}
            >
              Create an account
            </button>
          </>
        )}
      </div>
    </div>
  );
}
