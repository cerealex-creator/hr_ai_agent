"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type StageItem = {
  id: string;
  label: string;
  enabled: boolean;
  protected?: boolean;
};

type Schema = {
  hr_stages: StageItem[];
  client_statuses: StageItem[];
  structure_locked?: boolean;
  labels_editable?: boolean;
  reasons?: string[];
};

type Props = { vacancyId: number };

export function VacancyStageSchemaPanel({ vacancyId }: Props) {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancyId}/stage-schema`, {
      cache: "no-store",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    setSchema(data.schema);
  };

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [vacancyId]);

  const save = async () => {
    if (!schema) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancyId}/stage-schema`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hr_stages: schema.hr_stages,
          client_statuses: schema.client_statuses,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setSchema(data.schema);
      setMsg(
        data.schema?.structure_locked
          ? "Подписи сохранены (структура заморожена — есть кандидаты)"
          : "Схема этапов сохранена",
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const patchHr = (id: string, patch: Partial<StageItem>) => {
    setSchema((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        hr_stages: prev.hr_stages.map((s) => (s.id === id ? { ...s, ...patch } : s)),
      };
    });
  };

  if (!schema) {
    return <p className="muted">Загрузка схемы этапов…</p>;
  }

  const locked = Boolean(schema.structure_locked);

  return (
    <div className="stage-schema-panel">
      <p className="muted hh-micro">
        Ключи в базе не меняются — только подписи и видимость в списках/карточках. Клиентские кнопки
        Telegram остаются на системных статусах.
      </p>
      {locked ? (
        <p className="warn">
          {(schema.reasons || [])[0] ||
            "Есть кандидаты — отключать этапы нельзя, можно менять только названия."}
        </p>
      ) : (
        <p className="ok">Вакансия без кандидатов — можно включать/выключать этапы до старта.</p>
      )}
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <h3 className="hh-subhead">HR-этапы</h3>
      <ul className="stage-schema-list">
        {schema.hr_stages.map((s) => (
          <li key={s.id}>
            <label className="hh-check">
              <input
                type="checkbox"
                checked={s.enabled}
                disabled={busy || locked || s.protected}
                onChange={(e) => patchHr(s.id, { enabled: e.target.checked })}
              />
              <span className="muted hh-micro">{s.id}</span>
            </label>
            <input
              value={s.label}
              disabled={busy}
              onChange={(e) => patchHr(s.id, { label: e.target.value })}
            />
          </li>
        ))}
      </ul>

      <div className="hh-footer-actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="chip chip-active" disabled={busy} onClick={save}>
          Сохранить схему
        </button>
      </div>
    </div>
  );
}
