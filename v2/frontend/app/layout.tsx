import type { Metadata } from "next";
import { AuthGate } from "@/components/AuthGate";
import { JobsLiveProvider } from "@/components/JobsLive";
import { UI_PREFS_BOOT_SCRIPT, UiPrefsProvider } from "@/components/UiPrefsProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HR-помогатор",
  description: "Подбор сотрудников и работа с вакансиями",
  icons: {
    icon: [
      { url: "/favicon-16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-48.png", sizes: "48x48", type: "image/png" },
      { url: "/favicon.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: UI_PREFS_BOOT_SCRIPT }} />
      </head>
      <body>
        <UiPrefsProvider>
          <AuthGate>
            <JobsLiveProvider>{children}</JobsLiveProvider>
          </AuthGate>
        </UiPrefsProvider>
      </body>
    </html>
  );
}
