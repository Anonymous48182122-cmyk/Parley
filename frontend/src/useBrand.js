import { useEffect, useState } from "react";
import { getBrand } from "./api.js";

// How to draw the company's logo. A run carries it when it was found at the time; older runs and saved debates
// have none, so the server is asked by name. Shared by the page header and the case file.
export function useBrand(model) {
  const saved = model.marketData?.business_facts?.brand;
  const hasSaved = !!(saved && (saved.site_icon || saved.site_logo || saved.logo));
  const [fetched, setFetched] = useState(null);
  const name = model.marketData ? model.name : null;

  useEffect(() => {
    if (!name || hasSaved) return undefined;
    let cancelled = false;
    getBrand(name, model.ticker, model.market)
      .then((b) => !cancelled && setFetched(b))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [name, hasSaved]); // eslint-disable-line react-hooks/exhaustive-deps

  return hasSaved ? saved : fetched;
}
