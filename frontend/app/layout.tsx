import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RenalAI — CKD Screening Assistant",
  description: "AI-assisted chronic kidney disease screening and clinical decision support (prototype).",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
