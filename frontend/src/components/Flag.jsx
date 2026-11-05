import { useEffect, useState } from "react";
import { COUNTRY_NAMES } from "../countryNames.js";

// An earlier build kept every flag file in a service worker cache that could hold a bad copy for a year. The
// flags are now fetched normally, so that old cache is simply removed.
if (typeof caches !== "undefined") caches.delete("flags").catch(() => {});

// A country's flag as a small image (emoji flags show as two letters on Windows, so they are not used).
// With no known country it shows a plain globe, never a guess; if the image cannot load it shows the
// country code in a small badge, so there is never an empty box.
export default function Flag({ code, size = 16, className = "" }) {
  const iso = (code || "").toUpperCase();
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [iso]);
  const name = COUNTRY_NAMES[iso] || (iso ? iso : "Country not known");
  const box = { width: Math.round(size * 1.33), height: size };

  if (iso && COUNTRY_NAMES[iso] && failed) {
    return (
      <span className={`flag flag--code ${className}`} style={{ ...box, fontSize: Math.max(8, size * 0.55) }} title={name} role="img" aria-label={name}>
        {iso}
      </span>
    );
  }
  if (!iso || !COUNTRY_NAMES[iso]) {
    return (
      <span className={`flag flag--unknown ${className}`} style={box} title={name} role="img" aria-label={name}>
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
      width={box.width}
      height={box.height}
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}
