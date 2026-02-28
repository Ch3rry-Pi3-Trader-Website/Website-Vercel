import Link from "next/link";
import SiteNav from "@/components/SiteNav";

const highlights = [
  {
    title: "Signal-driven investing",
    copy: "Evaluate momentum and mean-reversion performance before capital is allocated.",
  },
  {
    title: "Budget-aware suggestions",
    copy: "Translate backtest outputs into practical budget allocations per symbol.",
  },
  {
    title: "Portfolio optimization path",
    copy: "Use your current holdings as context for buy/hold/sell direction in future iterations.",
  },
];

export default function HomePage() {
  return (
    <div>
      <SiteNav />
      <main>
        <section className="hero section">
          <div className="hero-grid">
            <div className="reveal" style={{ ["--delay" as string]: "0ms" }}>
              <p className="eyebrow">Active Investor Assistant</p>
              <h1>
                Build an evidence-led portfolio from S&amp;P 500 signals, not guesswork.
              </h1>
              <p className="lede">
                PI3 Investor ingests market data, backtests configurable strategies, and
                surfaces concise recommendations you can act on.
              </p>
              <div className="cta-row">
                <Link href="/results" className="btn btn-primary">
                  View Current Output
                </Link>
                <a href="#workflow" className="btn btn-ghost">
                  See Workflow
                </a>
              </div>
            </div>
            <div className="hero-panel reveal" style={{ ["--delay" as string]: "120ms" }}>
              <p className="panel-kicker">Current Stack</p>
              <ul>
                <li>Python data + strategy engine</li>
                <li>Next.js frontend on Vercel</li>
                <li>Config-driven risk and selection</li>
                <li>Persisted trailing-month market data</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="workflow" className="section">
          <div className="card-grid">
            {highlights.map((item, idx) => (
              <article
                key={item.title}
                className="feature-card reveal"
                style={{ ["--delay" as string]: `${idx * 90}ms` }}
              >
                <h2>{item.title}</h2>
                <p>{item.copy}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
