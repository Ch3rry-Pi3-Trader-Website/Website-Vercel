import Link from "next/link";

export default function SiteNav() {
  return (
    <header className="site-nav">
      <div className="site-nav-inner">
        <Link href="/" className="brand">
          <span className="brand-dot" />
          PI3 Investor
        </Link>
        <nav className="nav-links">
          <Link href="/">Home</Link>
          <Link href="/results">Results</Link>
        </nav>
      </div>
    </header>
  );
}
