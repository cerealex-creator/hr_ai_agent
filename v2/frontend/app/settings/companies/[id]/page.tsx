"use client";

import Link from "next/link";
import { use, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { CompanyEditor } from "@/components/CompanyEditor";

type Props = {
  params: Promise<{ id: string }>;
};

export default function CompanySettingsPage({ params }: Props) {
  const { id } = use(params);
  const companyId = Number(id);
  const [title, setTitle] = useState("Компания");

  if (!Number.isFinite(companyId) || companyId <= 0) {
    return (
      <AppShell variant="settings" activePath="/settings">
        <p className="warn">Некорректный id компании</p>
        <Link className="back" href="/settings">
          ← К настройкам
        </Link>
      </AppShell>
    );
  }

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings/companies">
        ← К списку компаний
      </Link>
      <h1 className="page-title">{title}</h1>
      <p className="muted">Настройки компании: режим чатов, подразделения, Telegram.</p>
      <CompanyEditor companyId={companyId} onRenamed={setTitle} />
    </AppShell>
  );
}
