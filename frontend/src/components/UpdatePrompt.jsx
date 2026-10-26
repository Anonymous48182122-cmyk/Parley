import { useRegisterSW } from "virtual:pwa-register/react";

const CHECK_INTERVAL_MS = 60 * 1000;

export default function UpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      if (!registration) return;
      // The browser itself only re-checks the service worker file
      // occasionally (roughly once a day) — poll more often ourselves so a
      // deployed update shows up within a minute instead of a day.
      setInterval(() => registration.update(), CHECK_INTERVAL_MS);
    },
  });

  // The normal route asks the waiting version to take over and reloads. When that does not happen
  // (an old tab still holding the previous version, a worker stuck waiting) the button used to do
  // nothing at all, so after a moment it clears the saved copies and reloads, which always works.
  function applyUpdate() {
    updateServiceWorker(true);
    setTimeout(async () => {
      try {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map((r) => r.unregister()));
        for (const key of await caches.keys()) await caches.delete(key);
      } catch {
        // reloading is still the best that can be done
      }
      window.location.reload();
    }, 2000);
  }

  if (!needRefresh) return null;

  return (
    <div
      className="card fade-in"
      style={{
        position: "fixed",
        bottom: 20,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "14px 18px",
        maxWidth: "calc(100vw - 40px)",
      }}
    >
      <span style={{ fontSize: "0.9rem" }}>A new version of Parley is available.</span>
      <button
        className="button-primary"
        style={{ whiteSpace: "nowrap", padding: "8px 16px" }}
        onClick={applyUpdate}
      >
        Update
      </button>
      <button
        className="button-secondary"
        style={{ padding: "8px 12px" }}
        onClick={() => setNeedRefresh(false)}
      >
        Later
      </button>
    </div>
  );
}
