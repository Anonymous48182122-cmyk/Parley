import { useEffect, useState } from "react";

// The company's own logo, on a light tile so dark logos stay readable on Parley's dark screens.
//
// Where it comes from, in order, falling to the next when one is missing or fails to load:
//   1. the logo file Wikidata records for the company (served by Wikimedia Commons),
//   2. the icon of the company's own website,
//   3. its initials, so there is never an empty box or a broken picture.
// A small spot (the button) wants the square icon, so it tries the website's icon first. A big spot (the sheet's
// header) has room for the full wordmark, so it tries the logo first and lets the tile grow wider for it.
// The server finds the web address and logo file (backend business_facts.brand); this only draws it.

function commonsUrl(file) {
  return `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(String(file).replace(/ /g, "_"))}?width=256`;
}

function initials(name) {
  const words = String(name || "").replace(/\b(inc|corp|corporation|ltd|limited|plc|co|company|group|holdings?)\b\.?/gi, "").trim().split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] || "?").slice(0, 2)).toUpperCase();
}

export default function CompanyLogo({ brand, name, size = 40, wide = false }) {
  const sources = [];
  if (brand?.logo) sources.push({ kind: "logo", url: commonsUrl(brand.logo) });
  if (brand?.site_logo) sources.push({ kind: "logo", url: brand.site_logo });
  if (brand?.site_icon) sources.push({ kind: "icon", url: brand.site_icon });
  if (brand?.domain) sources.push({ kind: "icon", url: `https://www.google.com/s2/favicons?domain=${encodeURIComponent(brand.domain)}&sz=128` });

  // stable sort: icons before logos in a small spot, each group keeping its own order
  if (!wide) sources.sort((a, b) => (a.kind === "icon" ? 0 : 1) - (b.kind === "icon" ? 0 : 1));
  const key = sources.map((s) => s.url).join("|");
  const [index, setIndex] = useState(0);
  useEffect(() => setIndex(0), [key]);

  const current = sources[index];
  const stretch = wide && current?.kind === "logo";
  const box = { width: stretch ? "auto" : size, minWidth: size, maxWidth: stretch ? size * 3.2 : size, height: size, borderRadius: Math.round(size * 0.26) };

  if (!current) {
    return (
      <span className="co-logo co-logo--initials" style={{ ...box, fontSize: size * 0.38 }} role="img" aria-label={name}>
        {initials(name)}
      </span>
    );
  }
  return (
    <span className="co-logo" style={box}>
      <img
        src={current.url}
        alt={`${name} logo`}
        referrerPolicy="no-referrer"
        onError={() => setIndex((i) => i + 1)}
        onLoad={(e) => {
          // a website with no icon of its own gets a tiny grey globe back, which is worse than initials
          if (current.kind === "icon" && e.currentTarget.naturalWidth < 24) setIndex((i) => i + 1);
          // a long wordmark squeezed into a small square cannot be read, so a small spot takes initials instead
          const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
          if (!wide && current.kind === "logo" && h > 0 && w / h > 1.6) setIndex((i) => i + 1);
        }}
        style={{ padding: Math.round(size * (stretch ? 0.16 : 0.12)), ...(stretch ? { width: "auto", maxWidth: "100%" } : {}) }}
      />
    </span>
  );
}
