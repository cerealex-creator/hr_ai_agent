"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export type StatsAiBrief = {
  title: string;
  summary: string;
  kpis: { label: string; value: string; tone: string }[];
  sections: {
    title: string;
    body?: string | null;
    items: { text: string; tone: string }[];
  }[];
  actions: string[];
};

type Props = {
  clientId: number | null;
  vacancyId: number | null;
  period: string;
  dateFrom: string;
  dateTo: string;
  activeOnly: boolean;
};

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    const d = data?.detail;
    if (typeof d === "string" && d.trim()) return d;
    if (Array.isArray(d) && d[0] && typeof (d[0] as { msg?: string }).msg === "string") {
      return (d[0] as { msg: string }).msg;
    }
  } catch {
    /* ignore */
  }
  return `Ошибка ИИ (${res.status})`;
}

function kpiToneClass(tone: string): string {
  if (tone === "blue" || tone === "attention" || tone === "orange" || tone === "teal") {
    return `rec-dash-kpi-${tone}`;
  }
  return "rec-dash-kpi-blue";
}

function itemToneClass(tone: string): string {
  if (tone === "attention") return "rec-badge rec-badge-attention";
  if (tone === "ok") return "rec-badge rec-badge-teal";
  return "rec-badge rec-badge-gray";
}

const EXAMPLES = [
  "Что сейчас тормозит найм и куда смотреть в первую очередь?",
  "Краткий отчёт для руководителя: результат за период и риски",
  "По каким вакансиям мало прогресса и что сделать на этой неделе?",
];

export function StatsAiBriefPanel({
  clientId,
  vacancyId,
  period,
  dateFrom,
  dateTo,
  activeOnly,
}: Props) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [brief, setBrief] = useState<StatsAiBrief | null>(null);

  async function generate(text?: string) {
    const q = (text ?? prompt).trim();
    if (q.length < 3) {
      setError("Опишите запрос подробнее");
      return;
    }
    setPrompt(q);
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        prompt: q,
        period,
        active_vacancies_only: activeOnly,
      };
      if (clientId != null) body.client_id = clientId;
      if (vacancyId != null) body.vacancy_id = vacancyId;
      if (dateFrom) body.from = dateFrom;
      if (dateTo) body.to = dateTo;

      const res = await apiFetch("/api/v1/stats/ai-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        setError(await readError(res));
        setBrief(null);
        return;
      }
      setBrief((await res.json()) as StatsAiBrief);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось получить расклад");
      setBrief(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stats-ai">
      <section className="rec-dash-section">
        <div className="rec-card stats-ai-ask">
          <h2 className="stats-ai-ask-title">Что разобрать?</h2>
          <p className="muted stats-ai-ask-hint">
            ИИ соберёт расклад по выбранным фильтрам и периоду: KPI, списки и следующие шаги —
            не просто текст.
          </p>
          <textarea
            className="stats-ai-textarea"
            rows={3}
            value={prompt}
            disabled={busy}
            placeholder="Например: где узкие места воронки и кого взять в работу сегодня"
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void generate();
              }
            }}
          />
          <div className="stats-ai-examples">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                className="stats-ai-example"
                disabled={busy}
                onClick={() => void generate(ex)}
              >
                {ex}
              </button>
            ))}
          </div>
          <div className="stats-ai-actions-row">
            <button
              type="button"
              className="btn primary"
              disabled={busy || prompt.trim().length < 3}
              onClick={() => void generate()}
            >
              {busy ? "Собираю расклад…" : "Собрать расклад"}
            </button>
            {busy ? <span className="muted">Обычно 10–30 сек</span> : null}
          </div>
          {error ? <p className="warn">{error}</p> : null}
        </div>
      </section>

      {brief ? (
        <>
          <section className="rec-dash-section">
            <div className="rec-dash-section-head">
              <h2 className="rec-dash-section-title">{brief.title}</h2>
            </div>
            {brief.summary ? (
              <div className="rec-card stats-ai-summary">
                <p>{brief.summary}</p>
              </div>
            ) : null}
          </section>

          {brief.kpis.length ? (
            <div className="rec-dash-kpis">
              {brief.kpis.map((k, i) => (
                <div key={`${k.label}-${i}`} className={`rec-dash-kpi ${kpiToneClass(k.tone)}`}>
                  <span className="rec-dash-kpi-label">{k.label}</span>
                  <span className="rec-dash-kpi-val">{k.value}</span>
                </div>
              ))}
            </div>
          ) : null}

          {brief.sections.map((sec, si) => (
            <section key={`${sec.title}-${si}`} className="rec-dash-section">
              <div className="rec-dash-section-head">
                <h2 className="rec-dash-section-title">{sec.title}</h2>
              </div>
              <div className="rec-card vac-list-card">
                {sec.body ? <p className="stats-ai-section-body">{sec.body}</p> : null}
                {sec.items.length ? (
                  <div className="vac-list">
                    {sec.items.map((it, ii) => (
                      <div key={`${ii}-${it.text.slice(0, 24)}`} className="rec-row rec-row-compact">
                        <div className="rec-row-body">
                          <p className="rec-row-sub stats-ai-item-text">{it.text}</p>
                        </div>
                        <div className="rec-row-aside">
                          <span className={itemToneClass(it.tone)}>
                            {it.tone === "attention" ? "Внимание" : it.tone === "ok" ? "Ок" : "Факт"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : !sec.body ? (
                  <p className="rec-empty">Нет пунктов</p>
                ) : null}
              </div>
            </section>
          ))}

          {brief.actions.length ? (
            <section className="rec-dash-section">
              <div className="rec-dash-section-head">
                <h2 className="rec-dash-section-title">Что сделать дальше</h2>
              </div>
              <div className="rec-card">
                <ol className="stats-ai-next-list">
                  {brief.actions.map((a, i) => (
                    <li key={`${i}-${a.slice(0, 20)}`}>{a}</li>
                  ))}
                </ol>
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default StatsAiBriefPanel;
