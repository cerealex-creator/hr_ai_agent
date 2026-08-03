"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { AppearanceSettings } from "@/components/AppearanceSettings";

export default function AppearanceSettingsPage() {
  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Внешний вид</h1>
      <AppearanceSettings />
    </AppShell>
  );
}
