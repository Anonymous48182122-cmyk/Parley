import { useEffect, useRef, useState } from "react";
import { explain, splitJargon } from "../glossary.js";

// Text where any finance word can be tapped for a one line plain explanation. Used wherever the
// quick views talk, so nobody has to leave the page to look a word up.
//
//   <Jargon text="The moat is wide and free cash flow is strong." />
//
// Only the first appearance of each word in a block is marked, so a paragraph is not covered in underlines.

export default function Jargon({ text, only }) {
  const [open, setOpen] = useState(null);
  const box = useRef(null);

  useEffect(() => {
    if (open == null) return undefined;
    function away(e) {
      if (box.current && !box.current.contains(e.target)) setOpen(null);
    }
    function esc(e) {
      if (e.key === "Escape") setOpen(null);
    }
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  // `only`, when given, is the set of words this piece may mark: a longer piece of writing works out once, from the
  // whole text, which line holds each word's first appearance, so a word is underlined once and the result never
  // depends on how many times a component happens to render
  const seen = new Set();
  const parts = splitJargon(text).map((p) => {
    if (!p.term || seen.has(p.term) || (only && !only.has(p.term))) return { text: p.text };
    seen.add(p.term);
    return p;
  });

  return (
    <span ref={box} className="jg-wrap">
      {parts.map((p, i) =>
        p.term ? (
          <span key={i} className="jg-item">
            <button type="button" className="jg" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
              {p.text}
            </button>
            {open === i && (
              <span className="jg-pop" role="note">
                <b>{p.text}</b>
                {explain(p.term)}
              </span>
            )}
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </span>
  );
}
