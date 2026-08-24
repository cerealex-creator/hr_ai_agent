"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { BusinessProfileForm } from "@/components/BusinessProfileForm";
import { GapSummaryStep } from "@/components/GapSummaryStep";
import { GoalBlocksWizard } from "@/components/GoalBlocksWizard";
import { IndustryPackStep } from "@/components/IndustryPackStep";
import {
  completeMgmtWizardStep1,
  completeMgmtWizardStep2,
  fetchMgmtWizardState,
  type MgmtWizardState,
} from "@/lib/management";

export function ManagementWizard() {
  const [state, setState] = useState<MgmtWizardState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [importText, setImportText] = useState("");

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const data = await fetchMgmtWizardState();
      setState(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const step = state?.step ?? 1;

  async function onStep1Submit(e: FormEvent, skipped: boolean) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await completeMgmtWizardStep1({
        skipped,
        import_text: skipped ? null : importText.trim() || null,
      });
      setMsg(skipped ? "Шаг 1 пропущен" : "Команда сохранена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onCompleteStep3() {
    await completeMgmtWizardStep2();
    setMsg("Шаг 3 завершён — дальше отраслевой пакет (U3)");
    await reload();
  }

  if (!state && !err) return <p className="muted">Загрузка мастера…</p>;

  return (
    <div className="mgmt-wizard">
      <header className="mgmt-wizard-head">
        <p className="muted">Шаг {step} из 5 · resumable-сессия</p>
        <div className="mgmt-wizard-steps" aria-hidden>
          {[1, 2, 3, 4, 5].map((n) => (
            <span
              key={n}
              className={`mgmt-wizard-dot${n <= step ? " is-done" : ""}${n === step ? " is-active" : ""}`}
            />
          ))}
        </div>
      </header>

      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {(state?.warnings || []).map((w) => (
        <p key={w} className="warn">{w}</p>
      ))}

      {step === 1 ? (
        <section className="card-edit">
          <h2>Шаг 1 — Текущая команда</h2>
          <p className="muted">
            Вставьте список должностей: одна строка = должность, или «название;число» для headcount.
            Можно пропустить, если компания с нуля (greenfield).
          </p>
          <form onSubmit={(e) => onStep1Submit(e, false)} className="mgmt-form-col">
            <textarea
              rows={6}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder={"Директор;1\nМенеджер по продажам;3\nБухгалтер;1"}
            />
            <div className="mgmt-form-row">
              <button type="submit" disabled={busy}>Сохранить и далее</button>
              <button
                type="button"
                disabled={busy}
                onClick={(e) => void onStep1Submit(e as unknown as FormEvent, true)}
              >
                Пропустить (greenfield)
              </button>
            </div>
          </form>
          {(state?.positions || []).length ? (
            <ul className="mgmt-list">
              {state!.positions.map((p) => (
                <li key={p.id}>{p.title} · ×{p.headcount}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {step === 2 ? (
        <section className="card-edit">
          <h2>Шаг 2 — Паспорт бизнеса</h2>
          <BusinessProfileForm onComplete={() => void reload()} />
        </section>
      ) : null}

      {step === 3 ? (
        <section className="card-edit">
          <h2>Шаг 3 — Цели по блокам BSC</h2>
          <p className="muted">
            Четыре измерения: финансы, клиенты, процессы, команда. Мини-опрос → предложения ИИ → утверждение.
          </p>
          <GoalBlocksWizard
            blocks={state?.goal_blocks || []}
            skippedBlocks={state?.skipped_blocks || []}
            mode="wizard"
            onReload={reload}
            onCompleteStep={onCompleteStep3}
            showWizardComplete
          />
        </section>
      ) : null}

      {step === 4 ? (
        <section className="card-edit">
          <h2>Шаг 4 — Отраслевой пакет</h2>
          <IndustryPackStep
            packs={state?.industry_packs || []}
            activePackId={state?.industry_pack_id}
            onApplied={reload}
          />
        </section>
      ) : null}

      {step === 5 ? (
        <section className="card-edit">
          <h2>Шаг 5 — Сводка и разрыв</h2>
          <GapSummaryStep
            inheritedGoals={state?.inherited_goals || []}
            onComplete={reload}
          />
        </section>
      ) : null}

      {step > 5 ? (
        <section className="card-edit">
          <h2>Мастер завершён</h2>
          <p className="muted">План перехода (U5) — в следующей фазе.</p>
          <Link href="/management-system/expert" className="mgmt-btn-link">Экспертный режим →</Link>
        </section>
      ) : null}
    </div>
  );
}
