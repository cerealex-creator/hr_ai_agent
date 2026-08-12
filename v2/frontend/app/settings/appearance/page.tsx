"use client";

import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { AppearanceSettings } from "@/components/AppearanceSettings";
import { InfoTip } from "@/components/InfoTip";

export default function AppearanceSettingsPage() {
  return (
    <RecruitingShell activePath="/settings" title="Настройки">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">
        Настройка внешнего вида{" "}
        <InfoTip text="Тема и размер шрифта только в этом браузере. На работу программы не влияют — только удобство чтения." />
      </h1>
      <p className="muted">Тема оформления и размер шрифта.</p>
      <AppearanceSettings />
    </RecruitingShell>
  );
}
