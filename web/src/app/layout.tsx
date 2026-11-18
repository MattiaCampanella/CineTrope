import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

const geist = localFont({
  src: [
    { path: "./fonts/geist-latin.woff2", weight: "100 900" },
    { path: "./fonts/geist-latin-ext.woff2", weight: "100 900" },
  ],
  variable: "--font-geist",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "CineTrope · Raccomandazioni spiegabili", template: "%s · CineTrope" },
  description:
    "Scegli un film: CineTrope ne propone cinque e mostra il percorso semantico che li collega.",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "32x32" },
    ],
    apple: "/apple-touch-icon.png",
  },
};
export const viewport: Viewport = { themeColor: "#000000", colorScheme: "dark" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it" className={geist.variable}>
      <body>
        <a className="skip-link" href="#main">
          Vai al contenuto
        </a>
        <Header />
        <main id="main">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
