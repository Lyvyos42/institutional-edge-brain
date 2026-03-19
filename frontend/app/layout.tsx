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
      <body style={{ background: "#06060f", margin: 0, minHeight: "100vh" }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
