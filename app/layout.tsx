import type { Metadata } from "next";
import { Manrope, Sora } from "next/font/google";
import "./globals.css";

const bodyFont = Manrope({
  variable: "--font-body",
  subsets: ["latin"],
  display: "swap",
});

const displayFont = Sora({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "PI3 Investor",
    template: "%s | PI3 Investor",
  },
  description:
    "Active investor app for strategy-led portfolio guidance on S&P 500 symbols.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${bodyFont.variable} ${displayFont.variable}`}>
        <div className="page-chrome">
          <div className="ambient ambient-a" />
          <div className="ambient ambient-b" />
          <div className="ambient ambient-c" />
          {children}
        </div>
      </body>
    </html>
  );
}
