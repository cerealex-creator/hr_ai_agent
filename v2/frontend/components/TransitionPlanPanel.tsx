"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approveMgmtTransitionStep,
  draftMgmtTransitionPlan,
  fetchMgmtCoverage,
  fetchMgmtRoleVacancyPreview,
  fetchMgmtTransitionSteps,
  rejectMgmtTransitionStep,
  type MgmtCoverageTracker,
  type MgmtTransitionStep,
} from "@/lib/management";

const HORIZON_LABEL: Record<string, string> = {
  short: "короткий",
  medium: "средний",
  long: "длинный",
};

type Props = {
  compact?: boolean;
  showVacancyBridge?: boolean;
};

export function TransitionPlanPanel({ compact = false, showVacancyBridge = true }: Props) {
  const [steps, setSteps] = useState<MgmtTransitionStep[]>([]);
  const [coverage, setCoverage] = useState<MgmtCoverageTracker | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [previewRoleId, setPreviewRoleId] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const [s, c] = await Promise.all([fetchMgmtTransitionSteps(), fetchMgmtCoverage()]);
      setSteps(s);
      setCoverage(c);
      setPreviewRoleId((prev) => prev || c.roles[0]?.role_id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки плана");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onDraft() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await draftMgmtTransitionPlan();
      setMsg(
        `План из gap: пунктов ${r.gap_items}, новых шагов ${r.steps_created}, всего ${r.steps_total}`
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сборки плана");
    } finally {
      setBusy(false);
    }
  }

  async function onApprove(id: string) {
    setBusy(true);
    setErr(null);
    try {
      await approveMgmtTransitionStep(id);
      setMsg("Шаг утверждён");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onReject(id: string) {
    setBusy(true);
    setErr(null);
    try {
      await rejectMgmtTransitionStep(id);
      setMsg("Шаг отклонён");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onPreview() {
    if (!previewRoleId) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetchMgmtRoleVacancyPreview(previewRoleId);
      setPreview(r.profile);
      if (r.warnings?.length) setMsg(r.warnings.join("; "));
      else setMsg("Preview профиля вакансии собран");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка preview");
    } finally {
      setBusy(false);
    }
  }

  const pending = steps.filter((s) => s.status === "draft").length;
  const approved = steps.filter((s) => s.status === "approved").length;

  return (
    <section className={`mgmt-transition${compact ? " is-compact" : ""}`}>
      <div className="mgmt-form-row" style={{ justifyContent: "space-between" }}>
        <h3>План перехода</h3>
        <button type="button" disabled={busy} onClick={() => void onDraft()}>
          Сгенерировать из gap
        </button>
      </div>
      <p className="muted">
        Шаги собираются детерминированно из gap-пунктов (INSERT from SELECT). Каждый шаг утверждается
        отдельно.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <div className="mgmt-gap-summary">
        <span>Шагов: {steps.length}</span>
        <span>Ждут: {pending}</span>
        <span>Утверждено: {approved}</span>
      </div>
      <ul className="mgmt-transition-list">
        {steps.map((s) => (
          <li key={s.id} className={`mgmt-transition-item status-${s.status}`}>
            <div>
              <strong>{s.title}</strong>
              <span className="muted">
                {" "}
                · {s.action_code} · горизонт {HORIZON_LABEL[s.horizon] || s.horizon} · {s.status}
              </span>
              {s.description ? <p className="muted">{s.description}</p> : null}
            </div>
            {s.status === "draft" ? (
              <div className="mgmt-form-row">
                <button
                  type="button"
                  className="mgmt-btn-secondary"
                  disabled={busy}
                  onClick={() => void onApprove(s.id)}
                >
                  Утвердить
                </button>
                <button
                  type="button"
                  className="mgmt-btn-secondary"
                  disabled={busy}
                  onClick={() => void onReject(s.id)}
                >
                  Отклонить
                </button>
              </div>
            ) : null}
          </li>
        ))}
        {!steps.length ? <li className="muted">Плана ещё нет — нажмите «Сгенерировать из gap»</li> : null}
      </ul>

      {coverage ? (
        <div className="mgmt-coverage">
          <h4>Трекер покрытия</h4>
          <div className="mgmt-gap-summary">
            <span>Инструкции {coverage.summary.pct_instruction}%</span>
            <span>Чек-листы {coverage.summary.pct_checklist}%</span>
            <span>KPI {coverage.summary.pct_kpi}%</span>
            <span>Назначения {coverage.summary.pct_assignment}%</span>
          </div>
          {!compact ? (
            <ul className="mgmt-list">
              {coverage.roles.map((r) => (
                <li key={r.role_id}>
                  <strong>{r.role_title}</strong>
                  <span className="muted">
                    {" "}
                    · И {r.instruction ? "✓" : "—"} · Ч {r.checklist ? "✓" : "—"} · KPI{" "}
                    {r.kpi ? "✓" : "—"} · As-is {r.assignment ? "✓" : "—"}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {showVacancyBridge && coverage?.roles.length ? (
        <div className="mgmt-vacancy-bridge">
          <h4>Мост в вакансию (preview)</h4>
          <div className="mgmt-form-row">
            <label>
              Роль
              <select value={previewRoleId} onChange={(e) => setPreviewRoleId(e.target.value)}>
                {coverage.roles.map((r) => (
                  <option key={r.role_id} value={r.role_id}>
                    {r.role_title}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void onPreview()}>
              Preview профиля
            </button>
          </div>
          {preview ? (
            <pre className="mgmt-json-preview">{JSON.stringify(preview, null, 2)}</pre>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
