"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  fetchMgmtChangesSummary,
  fetchMgmtImpact,
  markMgmtImpactStale,
  materializeMgmtRoleDocuments,
  type MgmtChangesSummary,
} from "@/lib/management";

export function ManagementChangesPanel() {
  const [data, setData] = useState<MgmtChangesSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [entityType, setEntityType] = useState("role");
  const [entityId, setEntityId] = useState("");
  const [impact, setImpact] = useState<Array<Record<string, unknown>> | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    try {
      setData(await fetchMgmtChangesSummary());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onRematerialize() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await materializeMgmtRoleDocuments();
      setMsg(`Пересборка: ролей ${r.roles}, документов ${r.documents}, строк ${r.lines_created}`);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onImpact() {
    if (!entityId.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetchMgmtImpact(entityType, entityId.trim());
      setImpact(r.items);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка impact");
      setImpact(null);
    } finally {
      setBusy(false);
    }
  }

  async function onMarkStale() {
    if (!entityId.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await markMgmtImpactStale(entityType, entityId.trim());
      setMsg(`Помечено stale: ${r.stale_marked}`);
      setImpact(r.items);
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
        Stale-документы и назначения после правок предков. Impact показывает затронутые узлы графа.
        После правок процессов/ролей пересоберите L3 и снова утвердите.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {data ? (
        <div className="mgmt-gap-summary">
          <span>Документов: {data.documents_total}</span>
          <span>Stale docs: {data.stale_documents_count}</span>
          <span>Stale assignments: {data.stale_assignments_count}</span>
          {Object.entries(data.by_status || {}).map(([k, v]) => (
            <span key={k}>
              {k}: {v}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted">Загрузка…</p>
      )}

      <div className="mgmt-form-row">
        <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void reload()}>
          Обновить
        </button>
        <button type="button" disabled={busy} onClick={() => void onRematerialize()}>
          Пересобрать L3 из процессов
        </button>
        <Link href="/management-system/documents" className="mgmt-btn-link">
          К документам →
        </Link>
      </div>

      <section>
        <h3>Stale-документы</h3>
        {data?.stale_documents?.length ? (
          <ul className="mgmt-list">
            {data.stale_documents.map((d) => (
              <li key={d.id}>
                <strong>{d.role_title}</strong> · {d.doc_kind} · {d.status}
                <span className="muted"> — {d.title}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Нет stale-документов</p>
        )}
      </section>

      <section>
        <h3>Stale-назначения</h3>
        {data?.stale_assignments?.length ? (
          <ul className="mgmt-list">
            {data.stale_assignments.map((a) => (
              <li key={a.id}>
                {a.role_title} ← {a.position_title} · {a.coverage}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Нет stale-назначений</p>
        )}
      </section>

      <section>
        <h3>Impact</h3>
        <div className="mgmt-form-row">
          <label>
            Тип
            <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
              <option value="role">role</option>
              <option value="process_step">process_step</option>
              <option value="goal">goal</option>
              <option value="task">task</option>
              <option value="current_position">current_position</option>
            </select>
          </label>
          <label>
            ID
            <input
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="uuid сущности"
            />
          </label>
          <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void onImpact()}>
            Показать impact
          </button>
          <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => void onMarkStale()}>
            Пометить потомков stale
          </button>
        </div>
        {impact ? (
          <ul className="mgmt-list">
            {impact.length === 0 ? <li className="muted">Пусто</li> : null}
            {impact.map((item, i) => (
              <li key={i}>
                {String(item.source_type)} → {String(item.target_type)} · {String(item.link_kind)} · depth{" "}
                {String(item.depth)}
                <span className="muted"> · {String(item.target_id).slice(0, 8)}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
