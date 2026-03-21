import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Institutional Edge Brain",
  description: "12-module institutional trading intelligence system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=JetBrains+Mono:wght@300;400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ background: "#000", margin: 0, minHeight: "100vh", fontFamily: "'Rajdhani', sans-serif" }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
