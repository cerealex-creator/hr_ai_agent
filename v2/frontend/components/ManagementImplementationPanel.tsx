"use client";

import { useCallback, useEffect, useState } from "react";
import { TransitionPlanPanel } from "@/components/TransitionPlanPanel";
import {
  createMgmtRoleAssignment,
  deleteMgmtRoleAssignment,
  fetchMgmtImplementation,
  updateMgmtRoleAssignment,
  type MgmtGapReport,
  type MgmtImplementation,
  type MgmtRoleAssignment,
} from "@/lib/management";

const COVERAGE_OPTIONS = [
  { value: "full", label: "Полное" },
  { value: "partial", label: "Частичное" },
  { value: "none", label: "Нет" },
] as const;

export function ManagementImplementationPanel() {
  const [data, setData] = useState<MgmtImplementation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [roleId, setRoleId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [coverage, setCoverage] = useState("partial");
  const [note, setNote] = useState("");

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const next = await fetchMgmtImplementation();
      setData(next);
      setRoleId((prev) => prev || next.roles[0]?.id || "");
      setPositionId((prev) => prev || next.current_positions[0]?.id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!roleId || !positionId) return;
    setBusy(true);
    setErr(null);
    try {
      await createMgmtRoleAssignment({
        target_role_id: roleId,
        current_position_id: positionId,
        coverage,
        note: note.trim() || undefined,
      });
      setNote("");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  }

  async function onCoverageChange(row: MgmtRoleAssignment, nextCoverage: string) {
    setBusy(true);
    setErr(null);
    try {
      await updateMgmtRoleAssignment(row.id, { coverage: nextCoverage });
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка обновления");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    setBusy(true);
    setErr(null);
    try {
      await deleteMgmtRoleAssignment(id);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка удаления");
    } finally {
      setBusy(false);
    }
  }

  const report: MgmtGapReport | null = data?.gap_report ?? null;

  return (
    <div className="mgmt-form-col">
      {err ? <p className="warn">{err}</p> : null}
      <div className="mgmt-impl-grid">
        <section className="mgmt-impl-card">
          <h3>Как есть</h3>
          <p className="muted">Текущие должности / слоты команды</p>
          {data?.current_positions.length ? (
            <ul className="mgmt-list">
              {data.current_positions.map((p) => (
                <li key={p.id}>
                  <strong>{p.title}</strong>
                  <span className="muted"> · headcount {p.headcount}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Нет as-is слотов — добавьте в мастере или эксперте.</p>
          )}
        </section>
        <section className="mgmt-impl-card">
          <h3>Как надо</h3>
          <p className="muted">Целевые роли из пакета / оргсхемы</p>
          {data?.roles.length ? (
            <ul className="mgmt-list">
              {data.roles.map((r) => (
                <li key={r.id}>
                  <strong>{r.title}</strong>
                  <span className="muted"> · {r.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Нет ролей — примените отраслевой пакет на шаге 4 мастера.</p>
          )}
        </section>
        <section className="mgmt-impl-card">
          <h3>Сопоставление</h3>
          <p className="muted">Связь as-is → to-be для gap-отчёта</p>
          {data?.role_assignments.length ? (
            <ul className="mgmt-assignment-list">
              {data.role_assignments.map((row) => (
                <li key={row.id} className="mgmt-assignment-row">
                  <span>
                    <strong>{row.target_role_title}</strong>
                    <span className="muted"> ← {row.current_position_title}</span>
                  </span>
                  <select
                    value={row.coverage}
                    disabled={busy}
                    onChange={(ev) => void onCoverageChange(row, ev.target.value)}
                    aria-label="Покрытие"
                  >
                    {COVERAGE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="mgmt-btn-secondary"
                    disabled={busy}
                    onClick={() => void onDelete(row.id)}
                  >
                    Удалить
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Сопоставлений пока нет.</p>
          )}
        </section>
      </div>

      <form className="mgmt-form-row mgmt-assignment-form" onSubmit={(e) => void onCreate(e)}>
        <label>
          Роль
          <select value={roleId} disabled={busy} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">—</option>
            {(data?.roles || []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Должность as-is
          <select value={positionId} disabled={busy} onChange={(e) => setPositionId(e.target.value)}>
            <option value="">—</option>
            {(data?.current_positions || []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Покрытие
          <select value={coverage} disabled={busy} onChange={(e) => setCoverage(e.target.value)}>
            {COVERAGE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Заметка
          <input
            type="text"
            value={note}
            disabled={busy}
            placeholder="например: временно до найма"
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <button type="submit" disabled={busy || !roleId || !positionId}>
          Добавить связь
        </button>
      </form>

      <section className="mgmt-gap-section">
        <div className="mgmt-form-row">
          <h3>Разрыв (gap)</h3>
          <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void reload()}>
            Обновить отчёт
          </button>
        </div>
        {report ? (
          <>
            <div className="mgmt-gap-summary">
              <span>Целей: {report.summary.goals}</span>
              <span>Ролей: {report.summary.roles}</span>
              <span>As-is: {report.summary.current_positions}</span>
              <span>Сопоставлений: {report.summary.assignments}</span>
              <span>Gap-пунктов: {report.summary.gap_items}</span>
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
      </section>

      <TransitionPlanPanel showVacancyBridge />
    </div>
  );
}
