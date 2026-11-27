import { useEffect, useState } from "react";

// Light or dark. Follows the device until the reader chooses, then remembers the choice.

function systemDark() {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

function currentTheme() {
  const set = document.documentElement.getAttribute("data-theme");
  return set === "light" || set === "dark" ? set : systemDark() ? "dark" : "light";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme);

  useEffect(() => {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0e1013" : "#f7f6f2");
  }, [theme]);

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const follow = () => !document.documentElement.getAttribute("data-theme") && setTheme(currentTheme());
    mq?.addEventListener?.("change", follow);
    return () => mq?.removeEventListener?.("change", follow);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("parley.theme", next);
    } catch {
      // the choice still holds for this visit
    }
    setTheme(next);
  }

  const label = theme === "dark" ? "Switch to light" : "Switch to dark";
  return (
    <button type="button" className="nav-icon" onClick={toggle} aria-label={label} title={label}>
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
        {theme === "dark" ? (
          <>
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5.3 5.3l1.7 1.7M17 17l1.7 1.7M18.7 5.3 17 7M7 17l-1.7 1.7" />
          </>
        ) : (
          <path d="M20 14.4A8.2 8.2 0 0 1 9.6 4a8.2 8.2 0 1 0 10.4 10.4Z" />
        )}
      </svg>
    </button>
  );
}
