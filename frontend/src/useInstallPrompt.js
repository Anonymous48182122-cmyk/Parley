import { useEffect, useState } from "react";

// Wraps the browser's native PWA install flow. Chrome/Edge/Android fire
// `beforeinstallprompt`, which we capture and defer until the user clicks our
// own "Download the App" button. iOS Safari never fires this event — it has
// no programmatic install API — so we detect it and show manual instructions
// instead (Share -> Add to Home Screen).
export function useInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isStandalone, setIsStandalone] = useState(false);

  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);

  useEffect(() => {
    setIsStandalone(window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true);

    function handleBeforeInstallPrompt(event) {
      event.preventDefault();
      setDeferredPrompt(event);
    }
    function handleAppInstalled() {
      setDeferredPrompt(null);
      setIsStandalone(true);
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  async function promptInstall() {
    if (!deferredPrompt) return null;
    deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    setDeferredPrompt(null);
    return choice.outcome; // "accepted" | "dismissed"
  }

  return {
    canInstall: Boolean(deferredPrompt),
    promptInstall,
    isIOS,
    isStandalone,
  };
}
