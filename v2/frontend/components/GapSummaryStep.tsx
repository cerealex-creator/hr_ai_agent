"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { L3PreviewPanel } from "@/components/L3PreviewPanel";
import { TransitionPlanPanel } from "@/components/TransitionPlanPanel";
import {
  completeMgmtWizardStep5,
  fetchMgmtGapReport,
  type MgmtGapReport,
  type MgmtGoal,
} from "@/lib/management";

type Props = {
  inheritedGoals?: MgmtGoal[];
  onComplete?: () => Promise<void>;
};

export function GapSummaryStep({ inheritedGoals = [], onComplete }: Props) {
  const [report, setReport] = useState<MgmtGapReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const data = await fetchMgmtGapReport();
      setReport(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onFinish() {
    setBusy(true);
    setErr(null);
    try {
      await completeMgmtWizardStep5();
      setMsg("Мастер завершён — доработка в экспертном режиме");
      await onComplete?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mgmt-form-col">
      <p className="muted">
        Шаг 5: сводка разрыва и утверждение плана перехода. Документы ролей (L3) — preview ниже;
        полное утверждение L3 — в разделе «Документы».
      </p>
      {inheritedGoals.length ? (
        <section className="mgmt-holding-goals">
          <h3>Цели холдинга (read-only)</h3>
          <ul className="mgmt-list">
            {inheritedGoals.map((g) => (
              <li key={g.id}>
                <strong>{g.title}</strong>
                <span className="muted"> · холдинг · {g.status}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {report ? (
        <>
          <div className="mgmt-gap-summary">
            <span>Целей: {report.summary.goals}</span>
            <span>Задач: {report.summary.tasks}</span>
            <span>Ролей: {report.summary.roles}</span>
            <span>Шагов процессов: {report.summary.process_steps}</span>
          </div>
          <ul className="mgmt-gap-list">
            {report.items.map((item, i) => (
              <li key={`${item.code}-${i}`} className={`mgmt-gap-item severity-${item.severity}`}>
                <strong>{item.title}</strong>
                <span className="muted"> · {item.code}</span>
                <p>{item.message}</p>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <TransitionPlanPanel compact showVacancyBridge={false} />

      <L3PreviewPanel compact />

      <p className="muted">
        Карта структуры:{" "}
        <Link href="/management-system">открыть режим «Карта»</Link> (перетаскивание узлов сохраняет
        раскладку).
      </p>

      <div className="mgmt-form-row">
        <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void reload()}>
          Обновить отчёт
        </button>
        <button type="button" disabled={busy} onClick={() => void onFinish()}>
          Завершить мастер
        </button>
        <Link href="/management-system/documents" className="mgmt-btn-link">
          Документы ролей (L3) →
        </Link>
        <Link href="/management-system/implementation" className="mgmt-btn-link">
          Режим «Внедрение» →
        </Link>
        <Link href="/management-system/expert" className="mgmt-btn-link">
          Экспертный режим →
        </Link>
      </div>
    </div>
  );
}
