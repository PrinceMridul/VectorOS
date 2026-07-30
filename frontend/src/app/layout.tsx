import type { Metadata, Viewport } from "next";

import { Providers } from "@/components/providers";

import "./globals.css";
import "@xyflow/react/dist/base.css";

export const metadata: Metadata = {
  // Matches the landing hero and the thesis stated in README/ARCHITECTURE.
  title: "VectorOS — Understanding before Explanation",
  description:
    "An AI-native learning operating system. It plans a path with you, adapts to how you " +
    "learn, and stays with you until you have mastered it. An answer is not an education.",
  applicationName: "VectorOS",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#08080a",
  colorScheme: "dark light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-canvas antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
