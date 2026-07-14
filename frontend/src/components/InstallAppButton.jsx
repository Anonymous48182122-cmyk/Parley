import { useState } from "react";
import { useInstallPrompt } from "../useInstallPrompt.js";

export default function InstallAppButton() {
  const { canInstall, promptInstall, isIOS, isStandalone } = useInstallPrompt();
  const [showIOSHelp, setShowIOSHelp] = useState(false);

  if (isStandalone) return null; // already installed — nothing to offer

  if (!canInstall && !isIOS) return null; // unsupported browser, no graceful install path

  return (
    <div style={{ marginBottom: 28 }}>
      <button
        className="button-secondary"
        onClick={() => (isIOS ? setShowIOSHelp((v) => !v) : promptInstall())}
      >
        ↓ Download the App
      </button>

      {showIOSHelp && (
        <div className="card fade-in" style={{ marginTop: 12, maxWidth: 420 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Install on iPhone/iPad</div>
          <div style={{ color: "var(--text-dim)", fontSize: "0.9rem", lineHeight: 1.5 }}>
            Tap the <strong>Share</strong> button in Safari, then choose{" "}
            <strong>"Add to Home Screen"</strong>. It'll install like a normal app — full
            screen, its own icon, works offline.
          </div>
        </div>
      )}
    </div>
  );
}
