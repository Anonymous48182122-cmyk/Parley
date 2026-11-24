import Jargon from "./Jargon.jsx";
import { splitJargon } from "../glossary.js";

// Lightweight heuristic renderer for agent/CIO prose. Models tend to answer
// with real markdown (### Header, **bold**, numbered/bulleted lists) even
// though the prompts ask for plain section headers — so this handles actual
// markdown first and falls back to plainer heuristics, rather than printing
// raw #/* characters when the model's formatting drifts from the ask.
const MARKDOWN_HEADER = /^#{1,6}\s*(.+?)\s*#*$/;
const NUMBERED_HEADER = /^(\d+)\.\s+([A-Za-z][A-Za-z\s/()&'-]{2,60})(?:\s*[—-]\s*(.*))?$/;
const COLON_HEADER = /^\*{0,2}([A-Za-z][A-Za-z\s/()&'-]{2,45})\*{0,2}:\s*(.*)$/;
const BULLET = /^[*-]\s+(.*)$/;

function renderInline(text) {
  const parts = [];
  const regex = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text))) {
    if (match.index > lastIndex) parts.push({ text: text.slice(lastIndex, match.index) });
    if (match[1] !== undefined) parts.push({ text: match[1], bold: true });
    else parts.push({ text: match[2], italic: true });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push({ text: text.slice(lastIndex) });
  return parts;
}

// Finance words in the writing can be tapped for a plain explanation; each word is marked only the first time it
// appears in the piece (`only` lists the words this line may mark, worked out once from the whole text).
function Inline({ text, only }) {
  // headers pass no `only`, and stay plain
  if (!only) return renderInline(text).map((part, i) => (part.bold ? <strong key={i}>{part.text}</strong> : part.italic ? <em key={i}>{part.text}</em> : <span key={i}>{part.text}</span>));
  return renderInline(text).map((part, i) =>
    part.bold ? (
      <strong key={i}>
        <Jargon text={part.text} only={only} />
      </strong>
    ) : part.italic ? (
      <em key={i}>
        <Jargon text={part.text} only={only} />
      </em>
    ) : (
      <span key={i}>
        <Jargon text={part.text} only={only} />
      </span>
    )
  );
}

export default function FormattedText({ text, accentColor = "var(--gold)" }) {
  const lines = text.split(/\n+/).filter((line) => line.trim().length > 0);
  // which finance words each line may mark: a word only where it first appears in the whole piece
  const running = new Set();
  const allowed = lines.map((line) => {
    const mine = new Set();
    for (const part of splitJargon(line)) {
      if (part.term && !running.has(part.term)) {
        running.add(part.term);
        mine.add(part.term);
      }
    }
    return mine;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {lines.map((line, i) => {
        const trimmed = line.trim();

        const markdown = trimmed.match(MARKDOWN_HEADER);
        if (markdown) {
          return (
            <div key={i} style={{ color: accentColor, fontWeight: 600, marginTop: i > 0 ? 4 : 0 }}>
              <Inline text={markdown[1]} />
            </div>
          );
        }

        const numbered = trimmed.match(NUMBERED_HEADER);
        if (numbered) {
          const [, num, header, rest] = numbered;
          return (
            <div key={i}>
              <div style={{ color: accentColor, fontWeight: 600, marginBottom: 4 }}>
                {num}. {header}
              </div>
              {rest && (
                <div style={{ color: "var(--text)" }}>
                  <Inline text={rest} only={allowed[i]} />
                </div>
              )}
            </div>
          );
        }

        const colon = trimmed.match(COLON_HEADER);
        if (colon) {
          const [, header, rest] = colon;
          return (
            <div key={i}>
              <span style={{ color: accentColor, fontWeight: 600 }}>{header}: </span>
              <span>
                <Inline text={rest} only={allowed[i]} />
              </span>
            </div>
          );
        }

        const bullet = trimmed.match(BULLET);
        if (bullet) {
          return (
            <div key={i} style={{ display: "flex", gap: 8, color: "var(--text-dim)" }}>
              <span style={{ color: accentColor }}>·</span>
              <span>
                <Inline text={bullet[1]} only={allowed[i]} />
              </span>
            </div>
          );
        }

        return (
          <div key={i} style={{ color: "var(--text-dim)" }}>
            <Inline text={trimmed} only={allowed[i]} />
          </div>
        );
      })}
    </div>
  );
}
