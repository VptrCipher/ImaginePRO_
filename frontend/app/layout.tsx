import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "ImaginePro", description: "Imagine your next story. Create it with ImaginePro, your local AI video studio.", icons: { icon: "/icon.svg" }, applicationName: "ImaginePro" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
