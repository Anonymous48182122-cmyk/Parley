import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

// The auth service speaks in system messages ("Invalid login credentials"). Say what it means
// and what to do next.
function friendlyAuthError(message) {
  const m = message || "";
  if (/invalid login credentials/i.test(m)) return "That email and password do not match. Check them and try again.";
  if (/email not confirmed/i.test(m)) return "Please confirm your email first. We sent you a link when you signed up.";
  if (/already (been )?registered|already exists/i.test(m)) return "That email already has an account. Try signing in instead.";
  if (/password should be at least|weak password/i.test(m)) return "Use at least 6 characters for your password.";
  if (/rate limit|too many/i.test(m)) return "Too many tries. Please wait a minute and try again.";
  if (/failed to fetch|network|load failed/i.test(m)) return "We could not reach the server. Check your connection and try again.";
  if (/unable to validate email|invalid email/i.test(m)) return "That does not look like a valid email address.";
  return m || "Something went wrong. Please try again.";
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.2 5.5-4.7 7.2l7.6 5.9c4.4-4.1 6.9-10.1 6.9-17.6z" />
      <path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 0 1 0-9.4l-7.9-6.1a24 24 0 0 0 0 21.6l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

export default function AuthPage() {
  const { signUp, signIn, signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  const signup = mode === "signup";

  function switchMode(next) {
    setMode(next);
    setError(null);
    setInfo(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (signup) {
        const { error: err } = await signUp(email, password);
        if (err) throw err;
        setInfo("Check your email to confirm your account, then sign in.");
      } else {
        const { error: err } = await signIn(email, password);
        if (err) throw err;
        navigate("/");
      }
    } catch (err) {
      setError(friendlyAuthError(err.message));
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
      setError(friendlyAuthError(err.message));
    }
  }

  return (
    <div className="container auth">
      <div className="auth-head">
        <img src="/icon-192.png" alt="Parley" className="auth-logo" />
        <h1>{signup ? "Create your account" : "Welcome back"}</h1>
        <p>Keep every committee call, and see how it aged.</p>
      </div>

      <div className="card auth-card fade-in">
        <div className="auth-tabs" role="tablist" aria-label="Sign in or create an account">
          <button
            type="button"
            role="tab"
            aria-selected={!signup}
            className={`auth-tab${!signup ? " auth-tab--active" : ""}`}
            onClick={() => switchMode("signin")}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={signup}
            className={`auth-tab${signup ? " auth-tab--active" : ""}`}
            onClick={() => switchMode("signup")}
          >
            Create account
          </button>
        </div>

        <button type="button" className="auth-google" onClick={handleGoogle}>
          <GoogleMark /> Continue with Google
        </button>

        <div className="auth-or">
          <span />
          <em>or use your email</em>
          <span />
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate={false}>
          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </label>

          <label className="auth-field">
            <span>Password</span>
            <div className="auth-password">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                autoComplete={signup ? "new-password" : "current-password"}
                placeholder={signup ? "At least 6 characters" : "Your password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
              <button
                type="button"
                className="auth-show"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          {error && (
            <div className="auth-message auth-message--error" role="alert">
              {error}
            </div>
          )}
          {info && (
            <div className="auth-message auth-message--info" role="status">
              {info}
            </div>
          )}

          <button type="submit" className="button-primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Please wait…" : signup ? "Create account" : "Sign in"}
          </button>
        </form>
      </div>

      <ul className="auth-perks">
        <li>Save any debate and reopen it later</li>
        <li>See your Buy, Hold and Sell calls at a glance</li>
        <li>Compare a stock now with what the committee said before</li>
      </ul>
    </div>
  );
}
