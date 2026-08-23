import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ParcelPilot | AI Agent",
  description: "Powered by Ant Design X",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
