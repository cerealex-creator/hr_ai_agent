"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CompaniesSettings } from "@/components/CompaniesSettings";
import { InfoTip } from "@/components/InfoTip";

export default function CompaniesSettingsPage() {
  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">
        Настройка взаимодействия{" "}
        <InfoTip text="Здесь вы настраиваете, с кем работаете по вакансиям (компании и подразделения), как пишете заказчику (каналы связи) и тестовый чат для проверки." />
      </h1>
      <p className="muted">
        Настройка взаимодействия по вакансиям с внешним и внутренним заказчиком.
      </p>
      <CompaniesSettings />
    </AppShell>
  );
}
