export default function SectionLabel({ children }) {
  return (
    <h2
      style={{
        fontSize: "0.8rem",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: "var(--text-faint)",
        marginBottom: 16,
      }}
    >
      {children}
    </h2>
  );
}
