import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sector Rotation Regime Discovery | Indian Equity Market",
  description:
    "Production ML-driven market regime discovery and systematic sector rotation platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}

