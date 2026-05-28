import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Multi-Agent Delivery Dashboard",
  description: "Enterprise workflow monitoring for autonomous software delivery agents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>): JSX.Element {
  const debugOverlayEnabled =
    process.env.FRONTEND_DEBUG_OVERLAY === "true" ||
    process.env.NEXT_PUBLIC_FRONTEND_DEBUG_OVERLAY === "true";

  return (
    <html
      lang="en"
      className="dark"
      data-debug-overlay={debugOverlayEnabled ? "true" : "false"}
    >
      <body>{children}</body>
    </html>
  );
}
