"use client";

import Link from "next/link";
import { use, useState } from "react";
import { RecruitingShell } from "@/components/RecruitingShell";
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
      <RecruitingShell activePath="/settings" title="Настройки">
        <p className="warn">Некорректный id компании</p>
        <Link className="back" href="/settings">
          ← К настройкам
        </Link>
      </RecruitingShell>
    );
  }

  return (
    <RecruitingShell activePath="/settings" title="Настройки">
      <Link className="back" href="/settings/companies">
        ← К списку компаний
      </Link>
      <h1 className="page-title">{title}</h1>
      <p className="muted">Настройки компании: режим чатов, подразделения, Telegram.</p>
      <CompanyEditor companyId={companyId} onRenamed={setTitle} />
    </RecruitingShell>
  );
}
