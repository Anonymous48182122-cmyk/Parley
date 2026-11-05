import { COUNTRY_NAMES } from "../countryNames.js";

// A country's flag as a small image (emoji flags show as two letters on Windows, so they are not used).
// With no known country it shows a plain globe, never a guess.
export default function Flag({ code, size = 16, className = "" }) {
  const iso = (code || "").toUpperCase();
  const name = COUNTRY_NAMES[iso] || (iso ? iso : "Country not known");
  if (!iso || !COUNTRY_NAMES[iso]) {
    return (
      <span className={`flag flag--unknown ${className}`} style={{ width: size * 1.33, height: size }} title={name} role="img" aria-label={name}>
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18" />
        </svg>
      </span>
    );
  }
  return (
    <img
      className={`flag ${className}`}
      src={`/flags/${iso.toLowerCase()}.svg`}
      alt={name}
      title={name}
      width={Math.round(size * 1.33)}
      height={size}
      loading="lazy"
      decoding="async"
    />
  );
}
