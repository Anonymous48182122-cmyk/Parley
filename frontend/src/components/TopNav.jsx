import { useEffect } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { useOpenResearch } from "../committee.js";
import TickerSearchBox from "./TickerSearchBox.jsx";

// The top bar: the name, a search that works from any page (the home page has its own, larger one), history,
// light or dark, and signing in.
export default function TopNav() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const open = useOpenResearch();
  const home = pathname === "/";

  // Ctrl K (or Command K) puts the cursor in the search box, wherever the reader is
  useEffect(() => {
    function key(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        document.querySelector(".search input")?.focus();
      }
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  return (
    <header className="nav">
      <div className="nav-in">
        <Link to="/" className="brand" aria-label="Parley home">
          <span className="brand-name">Parley</span>
        </Link>

        <div className="nav-search">{!home && <TickerSearchBox variant="nav" onSelect={(t, m) => open(t, m)} />}</div>

        <nav className="nav-actions">
          {user && (
            <NavLink to="/history" className="nav-link">
              History
            </NavLink>
          )}
          {user ? (
            <button
              type="button"
              className="nav-user"
              title={`${user.email}. Sign out`}
              onClick={async () => {
                await signOut();
                navigate("/");
              }}
            >
              <span className="topnav-user-badge">{user.email?.[0]?.toUpperCase() ?? "?"}</span>
              <span className="nav-signout">Sign out</span>
            </button>
          ) : (
            <Link to="/auth" className="button-secondary nav-signin">
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
