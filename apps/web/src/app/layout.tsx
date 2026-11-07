import type { Metadata, Viewport } from "next";
import { RegisterSW } from "@/components/RegisterSW";
import { TabBar } from "@/components/TabBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Real Deal",
  description: "This week's grocery deals on the things you actually buy.",
  appleWebApp: { capable: true, title: "Real Deal", statusBarStyle: "default" },
  icons: { apple: "/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f2f7" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <main className="mx-auto max-w-xl pb-[calc(env(safe-area-inset-bottom)+4rem)]">{children}</main>
        <TabBar />
        <RegisterSW />
      </body>
    </html>
  );
}
