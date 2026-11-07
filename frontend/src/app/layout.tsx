import type { Metadata } from "next";
import "./globals.css";
import AppChrome from "@/components/app-chrome";

export const metadata: Metadata = {
  title: "AutoBizPro",
  description: "Automate, grow, and manage your business from one workspace.",
};

const themeInit = `(()=>{try{const saved=localStorage.getItem('bizpilotpro-theme')||localStorage.getItem('autobizpro-theme');document.documentElement.dataset.theme=saved==='dark'?'dark':'light'}catch{document.documentElement.dataset.theme='light'}})()`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeInit }} /></head>
      <body><AppChrome>{children}</AppChrome></body>
    </html>
  );
}
