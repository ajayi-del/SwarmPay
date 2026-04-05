import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "SwarmPay — Multi-Agent Autonomous Economy",
  description: "OWS-powered coordinator-agent payment network. Open Wallet Standard Category 04.",
  keywords: ["multi-agent", "Solana", "x402", "OWS", "autonomous economy", "SwarmPay"],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0a0f",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
