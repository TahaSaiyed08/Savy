import type { Metadata, Viewport } from "next";
import { ForceTheme } from "@/components/ForceTheme";
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

// Runs before paint, so a stored theme override doesn't flash the OS default first. Can't import the
// migration helper from ForceTheme.tsx here (this has to stay a plain inline string), so it duplicates
// just enough of that logic to read either key; ForceTheme.tsx does the actual one-time migration.
const THEME_INIT_SCRIPT = `(function(){try{var k="realdeal.theme",o="realdeal.dev.theme";var v=localStorage.getItem(k);if(v!=="light"&&v!=="dark"){var old=localStorage.getItem(o);if(old==="light"||old==="dark")v=old;}if(v==="light"||v==="dark")document.documentElement.setAttribute("data-force-theme",v);}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <main className="mx-auto max-w-xl pb-[calc(env(safe-area-inset-bottom)+4rem)]">{children}</main>
        <TabBar />
        <RegisterSW />
        <ForceTheme />
      </body>
    </html>
  );
}
