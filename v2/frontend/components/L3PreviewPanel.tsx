"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchMgmtL3Preview, type MgmtL3Preview } from "@/lib/management";

type Props = {
  compact?: boolean;
};

export function L3PreviewPanel({ compact = false }: Props) {
  const [data, setData] = useState<MgmtL3Preview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setErr(null);
    try {
      setData(await fetchMgmtL3Preview());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка preview L3");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (err) return <p className="warn">{err}</p>;
  if (!data) return <p className="muted">Загрузка preview документов ролей…</p>;

  return (
    <section className={`mgmt-l3-preview${compact ? " is-compact" : ""}`}>
      <div className="mgmt-form-row" style={{ justifyContent: "space-between" }}>
        <h3>Preview документов ролей (L3)</h3>
        <button type="button" className="mgmt-btn-secondary" onClick={() => void reload()}>
          Обновить
        </button>
      </div>
      <p className="muted">{data.note}</p>
      <div className="mgmt-gap-summary">
        <span>Ролей: {data.summary.roles ?? 0}</span>
        <span>Обязанностей: {data.summary.duties_total ?? 0}</span>
        <span>Без роли: {data.summary.unassigned_steps ?? 0}</span>
      </div>
      {!data.documents.length ? (
        <p className="muted">Нет ролей — примените отраслевой пакет.</p>
      ) : (
        <ul className="mgmt-l3-doc-list">
          {data.documents.map((doc) => (
            <li key={doc.role_id} className="mgmt-l3-doc">
              <strong>{doc.role_title}</strong>
              <span className={`mgmt-status mgmt-status-${doc.role_status}`}> · {doc.role_status}</span>
              <span className="muted"> · preview, без утверждения</span>
              {doc.duties.length ? (
                <>
                  <p className="mgmt-l3-sub">Обязанности (из шагов процессов)</p>
                  <ul>
                    {doc.duties.map((d, i) => (
                      <li key={`${doc.role_id}-d-${i}`}>
                        {d.title}
                        {d.process_map ? <span className="muted"> · {d.process_map}</span> : null}
                        {d.frequency ? <span className="muted"> · {d.frequency}</span> : null}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="muted">Нет шагов с этой ролью</p>
              )}
              {!compact && doc.checklist.length ? (
                <>
                  <p className="mgmt-l3-sub">Черновик чек-листа</p>
                  <ul>
                    {doc.checklist.slice(0, 8).map((c, i) => (
                      <li key={`${doc.role_id}-c-${i}`}>{c.title}</li>
                    ))}
                    {doc.checklist.length > 8 ? (
                      <li className="muted">… ещё {doc.checklist.length - 8}</li>
                    ) : null}
                  </ul>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {data.unassigned_steps.length ? (
        <p className="warn">
          Шагов без роли: {data.unassigned_steps.map((s) => s.title).join(", ")}
        </p>
      ) : null}
    </section>
  );
}
