import type { Metadata } from "next";

import { AuthProvider } from "@/components/AuthProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Borek AI Suite",
  description: "Framework and presentation generation pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
