"use client";

import { useState } from "react";

type HhStats = {
  viewed: number;
  ai_score_gt2: number;
  ai_low: number;
  recruiter_reject: number;
  shortlist: number;
  in_funnel: number;
  jobs_completed: number;
};

export function CollapsibleHhBlock({ hh }: { hh: HhStats }) {
  const [open, setOpen] = useState(false);
  return (
    <section className={`card-edit card-collapse${open ? " is-open" : ""}`} style={{ marginTop: "1.25rem" }}>
      <button
        type="button"
        className="card-collapse-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="card-collapse-title">Эффективность поиска HH (ИИ)</span>
        <span className="card-collapse-hint">
          {hh.viewed} просмотров · {hh.in_funnel} в воронку
        </span>
        <span className="card-collapse-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open ? (
        <div className="card-collapse-body">
          <p className="muted">
            Холодный поиск: просмотренные резюме, оценки ИИ, shortlist и перевод в воронку.
          </p>
          <div className="stats">
            <div className="stat">
              <strong>{hh.viewed}</strong>
              <span>просмотрено резюме</span>
            </div>
            <div className="stat">
              <strong>{hh.ai_score_gt2}</strong>
              <span>оценка ИИ &gt; 2</span>
            </div>
            <div className="stat">
              <strong>{hh.shortlist}</strong>
              <span>в shortlist</span>
            </div>
            <div className="stat">
              <strong>{hh.in_funnel}</strong>
              <span>одобрено → воронка</span>
            </div>
            <div className="stat">
              <strong>{hh.ai_low}</strong>
              <span>автоотсев ИИ (≤1)</span>
            </div>
            <div className="stat">
              <strong>{hh.recruiter_reject}</strong>
              <span>отклонил рекрутер</span>
            </div>
            <div className="stat">
              <strong>{hh.jobs_completed}</strong>
              <span>завершённых поисков</span>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
