// "Where the committee changes its mind": the prices members named in their verdicts, from the highest down,
// with today's price as a marker among them and how far each is from it. The distance is the point: it shows
// at a glance whether a Buy would need the stock to fall a little or a lot, and who would act first.
function symbolFor(currency) {
  if (currency === "INR") return "₹";
  if (currency === "USD" || !currency) return "$";
  return "";
}

function fmt(n) {
  return n.toLocaleString("en-US", { maximumFractionDigits: n >= 100 ? 0 : 2 });
}

export default function PriceLadder({ levels, price, currency }) {
  if (!levels || levels.length === 0 || !price) return null;
  const sym = symbolFor(currency);
  const above = levels.filter((l) => l.side === "above");
  const below = levels.filter((l) => l.side === "below");
  const widest = Math.max(...levels.map((l) => Math.abs(l.pct)), 10);

  const row = (l) => (
    <div className={`ladder-row ladder-row--${l.side}`} key={l.price}>
      <div className="ladder-price">
        {sym}
        {fmt(l.price)}
      </div>
      <div className="ladder-bar" aria-hidden="true">
        <span style={{ width: `${Math.max(6, (Math.abs(l.pct) / widest) * 100)}%` }} />
      </div>
      <div className="ladder-pct">
        {l.pct > 0 ? "+" : ""}
        {l.pct.toFixed(0)}%
      </div>
      <div className="ladder-who">{l.who.join(", ")}</div>
    </div>
  );

  return (
    <section className="ladder" aria-label="Prices at which committee members change their mind">
      <div className="lab-kicker">Where the committee changes its mind</div>
      <div className="lab-title">The prices members named, and how far each is from today</div>
      {above.length > 0 && (
        <>
          <div className="ladder-note ladder-note--sell">Above today: members who would sell or trim</div>
          {above.map(row)}
        </>
      )}
      <div className="ladder-now">
        <span>Today</span>
        <b>
          {sym}
          {Number(price).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </b>
      </div>
      {below.length > 0 && (
        <>
          <div className="ladder-note ladder-note--buy">Below today: members who would buy</div>
          {below.map(row)}
        </>
      )}
    </section>
  );
}
