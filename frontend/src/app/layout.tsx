import type { Metadata } from "next";
import { Heebo } from "next/font/google";

import "./globals.css";

const heebo = Heebo({
  subsets: ["hebrew", "latin"],
  variable: "--font-heebo",
  display: "swap",
});

export const metadata: Metadata = {
  title: "עורך וידאו AI",
  description: "עורך וידאו מבוסס סוכני Claude לעריכה מקצה לקצה לפי תיאור חופשי",
};

/**
 * Root layout for the entire app.
 *
 * The page is rendered in Hebrew with `dir="rtl"`. All component-level
 * styling assumes RTL by default; LTR exceptions (e.g. embedded English
 * code blocks) must opt in explicitly via `dir="ltr"`.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="he" dir="rtl" className={heebo.variable}>
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  );
}
