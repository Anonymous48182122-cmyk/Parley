// The verdict as one picture, for sending to a friend: the ticker, the call, the headline in plain words, the
// three lights and how the committee voted. Drawn on a canvas so there is nothing to install and nothing leaves
// the device. 1080 by 1350 is the shape chat apps and feeds show best.

const W = 1080;
const H = 1350;
const COLORS = {
  bg: "#f7f6f2", surface: "#ffffff", text: "#14171c", dim: "#485059", faint: "#767d86", gold: "#9a6208",
  success: "#0a7a4a", danger: "#bf342a",
};
const VERDICT = { BUY: COLORS.success, HOLD: COLORS.gold, SELL: COLORS.danger };
const LIGHT = { good: COLORS.success, ok: COLORS.gold, bad: COLORS.danger, unknown: COLORS.faint };
const ANSWER = { good: "Yes", ok: "Maybe", bad: "No", unknown: "Unclear" };

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function wrap(ctx, text, maxWidth) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

export function drawShareCard(canvas, { ticker, name, verdict, conviction, headline, lights, counts }) {
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  const color = VERDICT[verdict] || COLORS.dim;
  const font = (size, weight = 500) => `${weight} ${size}px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif`;

  // background with a soft glow in the verdict's colour
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(0, 0, 40, 0, 0, 900);
  glow.addColorStop(0, `${color}00`);
  glow.addColorStop(1, "transparent");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);

  // header
  ctx.fillStyle = COLORS.text;
  ctx.font = '700 46px "Source Serif 4", Georgia, serif';
  ctx.fillText("Parley", 72, 112);
  ctx.fillStyle = COLORS.faint;
  ctx.font = font(26);
  ctx.textAlign = "right";
  ctx.fillText("AI investment committee", W - 72, 110);
  ctx.textAlign = "left";

  // ticker and name
  ctx.fillStyle = COLORS.text;
  ctx.font = '600 96px "IBM Plex Mono", ui-monospace, monospace';
  ctx.fillText(String(ticker).toUpperCase(), 72, 250);
  if (name) {
    ctx.fillStyle = COLORS.dim;
    ctx.font = font(32);
    ctx.fillText(String(name).slice(0, 44), 72, 300);
  }

  // the call
  ctx.fillStyle = color;
  ctx.font = font(150, 700);
  ctx.fillText(verdict || "NO CALL", 72, 450);
  ctx.fillStyle = COLORS.dim;
  ctx.font = font(32);
  ctx.fillText(conviction != null ? `Sure about it: ${conviction} out of 10` : "No score given", 76, 504);

  // headline
  ctx.fillStyle = COLORS.text;
  ctx.font = font(46, 500);
  const lines = wrap(ctx, headline, W - 144).slice(0, 4);
  lines.forEach((l, i) => ctx.fillText(l, 72, 592 + i * 58));

  // lights
  let y = 592 + lines.length * 58 + 12;
  for (const l of lights || []) {
    roundRect(ctx, 72, y, W - 144, 96, 22);
    ctx.fillStyle = COLORS.surface;
    ctx.fill();
    ctx.fillStyle = LIGHT[l.tone] || COLORS.faint;
    ctx.beginPath();
    ctx.arc(124, y + 48, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = COLORS.dim;
    ctx.font = font(30, 600);
    ctx.fillText(l.question, 164, y + 42);
    ctx.fillStyle = COLORS.faint;
    ctx.font = font(26);
    ctx.fillText(String(l.line).slice(0, 38), 164, y + 76);
    ctx.fillStyle = LIGHT[l.tone] || COLORS.faint;
    ctx.font = font(36, 700);
    ctx.textAlign = "right";
    ctx.fillText(ANSWER[l.tone], W - 108, y + 60);
    ctx.textAlign = "left";
    y += 112;
  }

  // the vote
  const total = (counts?.buy || 0) + (counts?.pass || 0) + (counts?.sell || 0) + (counts?.unclear || 0);
  if (total > 0) {
    y += 6;
    const barW = W - 144;
    let x = 72;
    [["buy", COLORS.success], ["pass", COLORS.gold], ["sell", COLORS.danger], ["unclear", COLORS.faint]].forEach(([k, c]) => {
      const n = counts[k] || 0;
      if (!n) return;
      const w = Math.max(n / total * barW - 6, 24);
      roundRect(ctx, x, y, w, 40, 12);
      ctx.fillStyle = c;
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.font = font(26, 700);
      ctx.textAlign = "center";
      ctx.fillText(String(n), x + w / 2, y + 28);
      ctx.textAlign = "left";
      x += w + 6;
    });
    ctx.fillStyle = COLORS.dim;
    ctx.font = font(26);
    const words = [[counts.buy, "for"], [counts.pass, "not sure"], [counts.sell, "against"], [counts.unclear, "undecided"]]
      .filter(([n]) => n > 0).map(([n, w]) => `${n} ${w}`).join(", ");
    ctx.fillText(words, 72, y + 78);
  }

  // footer
  ctx.fillStyle = COLORS.faint;
  ctx.font = font(24);
  ctx.fillText("The committee's view, not advice. Parley", 72, H - 40);
  return canvas;
}

export async function shareCardBlob(info) {
  const canvas = drawShareCard(document.createElement("canvas"), info);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

// Shares the picture with the phone's own share sheet when it can, else downloads it.
export async function shareVerdict(info) {
  const blob = await shareCardBlob(info);
  if (!blob) return "failed";
  const file = new File([blob], `parley-${String(info.ticker).toLowerCase()}.png`, { type: "image/png" });
  try {
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: `${info.ticker} on Parley`, text: info.headline });
      return "shared";
    }
  } catch (err) {
    if (err && err.name === "AbortError") return "cancelled";
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  return "downloaded";
}
