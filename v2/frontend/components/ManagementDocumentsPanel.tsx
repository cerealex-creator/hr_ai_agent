"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  addMgmtRoleDocumentLine,
  approveMgmtRoleDocument,
  criticMgmtRoleDocuments,
  fetchMgmtRoleDocuments,
  materializeMgmtRoleDocuments,
  polishMgmtRoleDocuments,
  publishMgmtRoleDocuments,
  type MgmtCriticResult,
  type MgmtRoleDocument,
} from "@/lib/management";

const KIND_LABEL: Record<string, string> = {
  instruction: "Инструкция",
  kpi: "KPI",
  checklist: "Чек-лист",
};

export function ManagementDocumentsPanel() {
  const [docs, setDocs] = useState<MgmtRoleDocument[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState<string>("");
  const [manualTitle, setManualTitle] = useState("");
  const [manualTarget, setManualTarget] = useState("");
  const [manualDocId, setManualDocId] = useState("");
  const [critic, setCritic] = useState<MgmtCriticResult | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const list = await fetchMgmtRoleDocuments();
      setDocs(list);
      setSelectedRoleId((prev) => prev || list[0]?.role_id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const roles = useMemo(() => {
    const map = new Map<string, string>();
    for (const d of docs) map.set(d.role_id, d.role_title);
    return Array.from(map.entries()).map(([id, title]) => ({ id, title }));
  }, [docs]);

  const roleDocs = docs.filter((d) => d.role_id === selectedRoleId);

  async function onMaterialize(all: boolean) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await materializeMgmtRoleDocuments(all ? undefined : selectedRoleId || undefined);
      setMsg(`Собрано: ролей ${r.roles}, документов ${r.documents}, строк ${r.lines_created}`);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сборки");
    } finally {
      setBusy(false);
    }
  }

  async function onApprove(docId: string) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await approveMgmtRoleDocument(docId);
      setMsg("Документ утверждён (L3)");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка утверждения");
    } finally {
      setBusy(false);
    }
  }

  async function onPolish(useAi: boolean) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await polishMgmtRoleDocuments({ use_ai: useAi });
      setMsg(
        `Полировка: ${r.updated_lines} строк в ${r.documents} док.${
          r.warnings?.length ? ` (${r.warnings[0]})` : ""
        }`
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка полировки");
    } finally {
      setBusy(false);
    }
  }

  async function onCritic(useLlm: boolean) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await criticMgmtRoleDocuments(useLlm);
      setCritic(r);
      setMsg(r.ok ? "Критик: блокирующих нет" : `Критик: блокирующих ${r.blocking.length}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка критика");
    } finally {
      setBusy(false);
    }
  }

  async function onPublish() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await publishMgmtRoleDocuments();
      setCritic(r.critic);
      if (!r.ok) {
        setErr(
          r.critic?.blocking?.[0]?.message ||
            "Publish заблокирован критиком — исправьте blocking"
        );
        return;
      }
      setMsg(`Опубликовано документов: ${r.published_count}`);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка publish");
    } finally {
      setBusy(false);
    }
  }

  async function onAddManual(e: FormEvent) {
    e.preventDefault();
    if (!manualDocId || !manualTitle.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const target = manualTarget.trim() ? Number(manualTarget.replace(",", ".")) : null;
      await addMgmtRoleDocumentLine(manualDocId, {
        title: manualTitle.trim(),
        target_value: target != null && !Number.isNaN(target) ? target : null,
      });
      setManualTitle("");
      setManualTarget("");
      setMsg("Ручная строка добавлена (is_manual)");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mgmt-form-col">
      <p className="muted">
        Режим «Документ»: сборка L3 из процессов (INSERT from SELECT), утверждение по одному документу.
        Ручные строки не затираются при повторной сборке. KPI без таргета / связи measures → 422.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <div className="mgmt-form-row">
        <button type="button" disabled={busy} onClick={() => void onMaterialize(true)}>
          Собрать документы для всех ролей
        </button>
        <button
          type="button"
          className="mgmt-btn-secondary"
          disabled={busy || !selectedRoleId}
          onClick={() => void onMaterialize(false)}
        >
          Собрать для выбранной роли
        </button>
        <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void onPolish(false)}>
          Полировка (локальная)
        </button>
        <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void onPolish(true)}>
          Полировка (ИИ)
        </button>
        <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void onCritic(false)}>
          Критик
        </button>
        <button type="button" disabled={busy} onClick={() => void onPublish()}>
          Publish L3
        </button>
        <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void reload()}>
          Обновить
        </button>
      </div>

      {critic ? (
        <section className="mgmt-critic-box">
          <h3>Критик {critic.ok ? "✓" : "✗"}</h3>
          {critic.blocking.length ? (
            <ul className="mgmt-list">
              {critic.blocking.map((b, i) => (
                <li key={`b-${i}`} className="warn">
                  <strong>{b.code}</strong>: {b.message}
                </li>
              ))}
            </ul>
          ) : (
            <p className="ok">Блокирующих замечаний нет</p>
          )}
          {critic.warnings.length ? (
            <ul className="mgmt-list">
              {critic.warnings.map((w, i) => (
                <li key={`w-${i}`} className="muted">
                  <strong>{w.code}</strong>: {w.message}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {roles.length ? (
        <label>
          Роль
          <select value={selectedRoleId} onChange={(e) => setSelectedRoleId(e.target.value)}>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="muted">Документов пока нет — примените пакет и нажмите «Собрать».</p>
      )}

      <div className="mgmt-docs-grid">
        {roleDocs.map((doc) => (
          <article key={doc.id} className={`mgmt-doc-card${doc.stale ? " is-stale" : ""}`}>
            <header>
              <strong>{KIND_LABEL[doc.doc_kind] || doc.doc_kind}</strong>
              <span className={`mgmt-status mgmt-status-${doc.status}`}> · {doc.status}</span>
              {doc.stale ? <span className="warn"> · stale</span> : null}
            </header>
            <p className="muted" style={{ margin: "0.25rem 0" }}>
              {doc.title}
            </p>
            <ul className="mgmt-doc-lines">
              {doc.lines.map((ln) => (
                <li key={ln.id}>
                  {ln.title}
                  {ln.target_value != null ? (
                    <span className="muted">
                      {" "}
                      · {ln.target_value}
                      {ln.metric_unit ? ` ${ln.metric_unit}` : ""}
                    </span>
                  ) : null}
                  {ln.is_manual ? <span className="muted"> · ручная</span> : null}
                </li>
              ))}
              {!doc.lines.length ? <li className="muted">Пусто</li> : null}
            </ul>
            {doc.status !== "approved" ? (
              <button
                type="button"
                className="mgmt-btn-secondary"
                disabled={busy}
                onClick={() => void onApprove(doc.id)}
              >
                Утвердить L3
              </button>
            ) : null}
          </article>
        ))}
      </div>

      {roleDocs.length ? (
        <form className="mgmt-form-row" onSubmit={(e) => void onAddManual(e)}>
          <label>
            Документ
            <select value={manualDocId} onChange={(e) => setManualDocId(e.target.value)}>
              <option value="">—</option>
              {roleDocs.map((d) => (
                <option key={d.id} value={d.id}>
                  {KIND_LABEL[d.doc_kind] || d.doc_kind}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ручная строка
            <input value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} placeholder="Текст" />
          </label>
          <label>
            Таргет (для KPI)
            <input value={manualTarget} onChange={(e) => setManualTarget(e.target.value)} inputMode="decimal" />
          </label>
          <button type="submit" disabled={busy || !manualDocId || !manualTitle.trim()}>
            Добавить строку
          </button>
        </form>
      ) : null}
    </div>
  );
}
