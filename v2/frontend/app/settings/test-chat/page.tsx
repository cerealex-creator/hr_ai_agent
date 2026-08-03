"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { TestChatSettings } from "@/components/TestChatSettings";

export default function TestChatSettingsPage() {
  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Тестировочный чат</h1>
      <TestChatSettings />
    </AppShell>
  );
}
