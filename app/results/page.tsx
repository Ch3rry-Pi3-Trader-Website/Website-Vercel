import SiteNav from "@/components/SiteNav";
import ResultsClient from "@/components/ResultsClient";

export const dynamic = "force-dynamic";

export default function ResultsPage() {
  return (
    <div>
      <SiteNav />
      <main className="section">
        <div className="results-head reveal" style={{ ["--delay" as string]: "0ms" }}>
          <p className="eyebrow">Portfolio Output</p>
          <h1>Strategy-backed recommendations from your latest backend run.</h1>
          <p className="lede">
            Update budget and holdings to generate a practical allocation plan and
            see top-ranked symbols.
          </p>
        </div>
        <ResultsClient />
      </main>
    </div>
  );
}
