"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CompaniesSettings } from "@/components/CompaniesSettings";

export default function CompaniesSettingsPage() {
  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Клиенты и компании</h1>
      <p className="muted">
        Создайте компанию или откройте существующую — чаты и подразделения настраиваются там.
      </p>
      <CompaniesSettings />
    </AppShell>
  );
}
