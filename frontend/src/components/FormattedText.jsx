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

function Inline({ text }) {
  return renderInline(text).map((part, i) =>
    part.bold ? (
      <strong key={i}>{part.text}</strong>
    ) : part.italic ? (
      <em key={i}>{part.text}</em>
    ) : (
      <span key={i}>{part.text}</span>
    )
  );
}

export default function FormattedText({ text, accentColor = "var(--gold)" }) {
  const lines = text.split(/\n+/).filter((line) => line.trim().length > 0);

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
                  <Inline text={rest} />
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
                <Inline text={rest} />
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
                <Inline text={bullet[1]} />
              </span>
            </div>
          );
        }

        return (
          <div key={i} style={{ color: "var(--text-dim)" }}>
            <Inline text={trimmed} />
          </div>
        );
      })}
    </div>
  );
}
