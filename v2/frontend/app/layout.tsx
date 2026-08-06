import type { Metadata } from "next";
import { AuthGate } from "@/components/AuthGate";
import { JobsLiveProvider } from "@/components/JobsLive";
import { UI_PREFS_BOOT_SCRIPT, UiPrefsProvider } from "@/components/UiPrefsProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HR AI Agent",
  description: "Подбор сотрудников и работа с вакансиями",
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
