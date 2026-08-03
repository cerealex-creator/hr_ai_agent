"use client";

import { useState } from "react";
import { getApiBase } from "@/lib/api";

export type SoftenSuggestion = {
  id: string;
  title: string;
  rationale: string;
  field: string;
  action: string;
  value?: unknown;
  item?: unknown;
};

type ManualItem = {
  hh_resume_id: string;
  title?: string;
  url?: string;
  area?: string | null;
  ai_score?: number | null;
  ai_preview?: string;
  ai_strengths?: string[];
  ai_weaknesses?: string[];
  error?: string | null;
};

type Props = {
  vacancyId: number;
  criteria: Record<string, unknown>;
  onCriteriaApplied?: (criteria: Record<string, unknown>) => void;
  /** Optional auto-search hits to ask AI for soften suggestions */
  searchResults?: Record<string, unknown>[];
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export function HhManualEvalBlock({
  vacancyId,
  criteria,
  onCriteriaApplied,
  searchResults,
}: Props) {
  const [text, setText] = useState("");
  const [items, setItems] = useState<ManualItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [softBusy, setSoftBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [summary, setSummary] = useState("");
  const [suggestions, setSuggestions] = useState<SoftenSuggestion[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  async function runEvaluate() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-manual-evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, criteria }),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      setItems(data.items || []);
      setMsg(`Оценено: ${data.compared || 0}`);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function askSoften(from: "manual" | "search") {
    setSoftBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const body: Record<string, unknown> = { criteria };
      if (from === "manual") {
        body.good_resumes = items.filter((i) => (i.ai_score ?? 0) >= 2 || !i.error);
      } else {
        body.search_results = searchResults || [];
      }
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-soften-suggestions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      setSummary(data.summary || "");
      const sug = (data.suggestions || []) as SoftenSuggestion[];
      setSuggestions(sug);
      const init: Record<string, boolean> = {};
      sug.forEach((s) => {
        init[s.id] = true;
      });
      setSelected(init);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Ошибка");
    } finally {
      setSoftBusy(false);
    }
  }

  async function applySelected() {
    const selected_ids = Object.entries(selected)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (!selected_ids.length) {
      setErr("Отметьте хотя бы одно предложение");
      return;
    }
    setSoftBusy(true);
    setErr(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-soften-apply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            criteria,
            suggestions,
            selected_ids,
            persist: true,
          }),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      onCriteriaApplied?.(data.criteria);
      setMsg("Критерии обновлены по отмеченным пунктам");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Ошибка");
    } finally {
      setSoftBusy(false);
    }
  }

  return (
    <div className="hh-manual">
      <p className="muted">
        Ручной режим: вставьте ссылки HH (или id резюме), оцените пачкой и сравните плюсы/минусы.
        Отдельно можно попросить ИИ предложить смягчение фильтров — вы отметите, что принять.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <label className="hh-field">
        <span className="hh-label">Ссылки / id резюме HH</span>
        <textarea
          rows={5}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          placeholder={"https://hh.ru/resume/…\nhttps://hh.ru/resume/…"}
        />
      </label>
      <div className="hh-footer-actions" style={{ justifyContent: "flex-start" }}>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !text.trim()}
          onClick={runEvaluate}
        >
          {busy ? "Оценка…" : "Оценить вручную"}
        </button>
        <button
          type="button"
          className="chip"
          disabled={softBusy || !items.length}
          onClick={() => askSoften("manual")}
        >
          {softBusy ? "…" : "ИИ: смягчить по этим резюме"}
        </button>
        {searchResults && searchResults.length ? (
          <button
            type="button"
            className="chip"
            disabled={softBusy}
            onClick={() => askSoften("search")}
          >
            ИИ: смягчить по автопоиску
          </button>
        ) : null}
      </div>

      {items.length ? (
        <div style={{ marginTop: "1rem", overflowX: "auto" }}>
          <h3 className="hh-subhead">Сравнение</h3>
          <table>
            <thead>
              <tr>
                <th>Оценка</th>
                <th>Резюме</th>
                <th>Плюсы</th>
                <th>Минусы</th>
                <th>Итог</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.hh_resume_id}>
                  <td>{r.ai_score != null ? <strong>{r.ai_score}/4</strong> : "—"}</td>
                  <td>
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer">
                        {r.title || r.hh_resume_id}
                      </a>
                    ) : (
                      r.title || r.hh_resume_id
                    )}
                    {r.area ? <div className="row-meta">{r.area}</div> : null}
                    {r.error ? <div className="row-meta warn">{r.error}</div> : null}
                  </td>
                  <td className="row-meta">
                    {(r.ai_strengths || []).length
                      ? (r.ai_strengths || []).map((s) => <div key={s}>+ {s}</div>)
                      : "—"}
                  </td>
                  <td className="row-meta">
                    {(r.ai_weaknesses || []).length
                      ? (r.ai_weaknesses || []).map((s) => <div key={s}>− {s}</div>)
                      : "—"}
                  </td>
                  <td className="row-meta">{r.ai_preview || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {suggestions.length || summary ? (
        <section className="card-edit" style={{ marginTop: "1rem" }}>
          <h3 className="hh-subhead">Предложения смягчить</h3>
          {summary ? <p>{summary}</p> : null}
          <ul className="soften-checklist">
            {suggestions.map((s) => (
              <li key={s.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={!!selected[s.id]}
                    onChange={(e) =>
                      setSelected((prev) => ({ ...prev, [s.id]: e.target.checked }))
                    }
                  />
                  <span>
                    <strong>{s.title}</strong>
                    {s.rationale ? <span className="muted"> — {s.rationale}</span> : null}
                    <span className="row-meta">
                      {s.field}:{s.action}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="chip chip-active"
            disabled={softBusy || !suggestions.length}
            onClick={applySelected}
          >
            Применить отмеченные
          </button>
        </section>
      ) : null}
    </div>
  );
}
