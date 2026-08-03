import type { Metadata } from "next";
import { UiPrefsProvider } from "@/components/UiPrefsProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HR AI Agent",
  description: "Подбор сотрудников и работа с вакансиями",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" data-theme="light" suppressHydrationWarning>
      <body>
        <UiPrefsProvider>{children}</UiPrefsProvider>
      </body>
    </html>
  );
}
