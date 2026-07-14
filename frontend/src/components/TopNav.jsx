import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

export default function TopNav() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 16,
        padding: "14px 24px",
        fontSize: "0.85rem",
        borderBottom: "1px solid var(--border)",
        background: "rgba(5, 7, 13, 0.7)",
        backdropFilter: "blur(10px)",
      }}
    >
      <Link
        to="/"
        style={{
          fontFamily: "var(--font-serif)",
          fontWeight: 600,
          fontSize: "1.05rem",
          color: "var(--text)",
        }}
      >
        Parley
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        {user ? (
          <>
            <span style={{ color: "var(--text-dim)" }}>{user.email}</span>
            <Link to="/history" style={{ color: "var(--text-dim)" }}>
              History
            </Link>
            <button
              className="button-secondary"
              style={{ padding: "6px 14px" }}
              onClick={async () => {
                await signOut();
                navigate("/");
              }}
            >
              Sign Out
            </button>
          </>
        ) : (
          <Link to="/auth" className="button-secondary" style={{ padding: "6px 14px" }}>
            Sign In
          </Link>
        )}
      </div>
    </div>
  );
}
