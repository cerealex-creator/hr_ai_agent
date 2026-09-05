"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import { createConsultingProject, listConsultingProjects } from "@/lib/consulting";

export default function ConsultingIndexPage() {
  const router = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listConsultingProjects()
      .then((data) => {
        if (cancelled) return;
        if (data.items[0]) router.replace(`/consulting/${data.items[0].id}`);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function create() {
    setBusy(true);
    setErr(null);
    try {
      const project = await createConsultingProject({
        title: "Диагностика системы управления",
        customer_name: "Грохольский Групп",
      });
      router.replace(`/consulting/${project.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось создать");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConsultingShell active="hub" title="Консалтинг">
      <p className="muted">Проекта ещё нет. Создайте каркас диагностики: паспорт, папки 00–09 и чек-лист.</p>
      {err ? <p className="consult-err">{err}</p> : null}
      <button type="button" className="mgmt-btn" disabled={busy} onClick={() => void create()}>
        {busy ? "Создаю…" : "Создать проект"}
      </button>
    </ConsultingShell>
  );
}
