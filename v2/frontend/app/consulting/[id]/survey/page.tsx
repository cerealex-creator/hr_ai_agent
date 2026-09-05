"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  createConsultingSurvey,
  getConsultingProject,
  getConsultingSurvey,
  getConsultingSurveyResponses,
  getConsultingSurveys,
  patchConsultingSurveyQuestion,
  publishConsultingSurvey,
  statusLabel,
  submitInterviewerResponse,
  type ConsultingPerson,
  type ConsultingSurvey,
} from "@/lib/consulting";

export default function ConsultingSurveyPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [list, setList] = useState<ConsultingSurvey[]>([]);
  const [survey, setSurvey] = useState<ConsultingSurvey | null>(null);
  const [people, setPeople] = useState<ConsultingPerson[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [fillSpots, setFillSpots] = useState(false);
  const [personId, setPersonId] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"edit" | "interview">("edit");

  function reloadList() {
    return getConsultingSurveys(id).then((d) => setList(d.items));
  }

  function openSurvey(surveyId: string) {
    return getConsultingSurvey(id, surveyId).then(setSurvey);
  }

  useEffect(() => {
    if (!id) return;
    Promise.all([reloadList(), getConsultingProject(id)])
      .then(([, p]) => setPeople(p.people || []))
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  const linkQuestions = useMemo(
    () => (survey?.questions || []).filter((q) => q.channel === "link"),
    [survey],
  );

  const sections = useMemo(() => {
    const map = new Map<string, typeof linkQuestions>();
    for (const q of survey?.questions || []) {
      const arr = map.get(q.section) || [];
      arr.push(q);
      map.set(q.section, arr);
    }
    return [...map.entries()];
  }, [survey]);

  return (
    <ConsultingShell projectId={id} active="survey" title="Опрос">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">
        По умолчанию полный опрос в ссылку. Галка «добить белые пятна» режет только открытые клетки покрытия (формы
        результата ещё нет). Преамбулу нужно утвердить до публикации.
      </p>

      <div className="consult-actions">
        <label className="consult-check">
          <input type="checkbox" checked={fillSpots} onChange={(e) => setFillSpots(e.target.checked)} />
          Добить белые пятна
        </label>
        <button
          type="button"
          className="mgmt-btn"
          onClick={() =>
            createConsultingSurvey(id, { fill_white_spots: fillSpots })
              .then((s) => {
                setSurvey(s);
                return reloadList();
              })
              .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))
          }
        >
          Собрать опрос
        </button>
      </div>

      <ul className="consult-list">
        {list.map((s) => (
          <li key={s.id}>
            <button type="button" className="mgmt-btn-link" onClick={() => openSurvey(s.id).catch((e) => setErr(String(e)))}>
              {s.title} · {statusLabel(s.status)} · ответов {s.responses_count}
            </button>
          </li>
        ))}
      </ul>

      {survey ? (
        <>
          <h2 className="consult-h2">{survey.title}</h2>
          <p className="muted">
            В ссылку: {survey.link_questions ?? linkQuestions.length}. На встречу:{" "}
            {(survey.questions || []).filter((q) => q.channel === "meeting").length}.
          </p>
          <div className="consult-actions">
            <button type="button" className="consult-btn-secondary" onClick={() => setMode("edit")}>
              Править
            </button>
            <button type="button" className="consult-btn-secondary" onClick={() => setMode("interview")}>
              Режим интервьюера
            </button>
            <button
              type="button"
              className="mgmt-btn"
              onClick={() =>
                publishConsultingSurvey(id, survey.id)
                  .then((s) => {
                    setSurvey(s);
                    return reloadList();
                  })
                  .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))
              }
            >
              Опубликовать
            </button>
          </div>
          {survey.public_url ? (
            <p className="muted">
              Ссылка: <a href={survey.public_url}>{survey.public_url}</a>
            </p>
          ) : null}

          {mode === "edit" ? (
            <div className="consult-hub">
              {sections.map(([section, qs]) => (
                <section key={section} className="consult-band">
                  <h3 className="consult-h3">{section}</h3>
                  {qs[0]?.preamble ? (
                    <div className="consult-label">
                      Преамбула ({statusLabel(qs[0].preamble_status)})
                      <textarea
                        defaultValue={qs[0].preamble}
                        rows={2}
                        onBlur={(e) => {
                          const v = e.target.value;
                          patchConsultingSurveyQuestion(id, survey.id, qs[0].id, {
                            preamble: v,
                            preamble_status: v.trim() ? "draft" : "none",
                          })
                            .then(() => openSurvey(survey.id))
                            .catch((er) => setErr(String(er)));
                        }}
                      />
                      {qs[0].preamble_status !== "approved" && qs[0].preamble.trim() ? (
                        <button
                          type="button"
                          className="consult-btn-secondary"
                          onClick={() =>
                            patchConsultingSurveyQuestion(id, survey.id, qs[0].id, {
                              preamble_status: "approved",
                            })
                              .then(() => openSurvey(survey.id))
                              .catch((er) => setErr(String(er)))
                          }
                        >
                          Утвердить преамбулу
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  {qs.map((q) => (
                    <div key={q.id} className="consult-label">
                      <span>
                        {q.text} · {statusLabel(q.channel)}
                      </span>
                      <select
                        value={q.channel}
                        onChange={(e) =>
                          patchConsultingSurveyQuestion(id, survey.id, q.id, { channel: e.target.value })
                            .then(() => openSurvey(survey.id))
                            .catch((er) => setErr(String(er)))
                        }
                      >
                        <option value="link">В ссылку</option>
                        <option value="meeting">На встречу</option>
                      </select>
                    </div>
                  ))}
                </section>
              ))}
            </div>
          ) : (
            <form
              className="consult-form"
              onSubmit={(e) => {
                e.preventDefault();
                const person = people.find((p) => p.id === personId);
                submitInterviewerResponse(id, survey.id, {
                  person_id: personId || null,
                  full_name: person?.full_name || "",
                  title: person?.title || "",
                  answers,
                  mode: "interviewer",
                })
                  .then(() => {
                    setAnswers({});
                    return getConsultingSurveyResponses(id, survey.id);
                  })
                  .then(() => openSurvey(survey.id))
                  .catch((er) => setErr(er instanceof Error ? er.message : "Ошибка"));
              }}
            >
              <label className="consult-label">
                Кто отвечает
                <select value={personId} onChange={(e) => setPersonId(e.target.value)} required>
                  <option value="">Выберите из паспорта</option>
                  {people.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.full_name}
                      {p.title ? ` — ${p.title}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              {linkQuestions.map((q) => (
                <label key={q.id} className="consult-label">
                  {q.text}
                  {q.kind === "single" ? (
                    <select
                      value={answers[q.code] || ""}
                      onChange={(e) => setAnswers((a) => ({ ...a, [q.code]: e.target.value }))}
                    >
                      <option value="">—</option>
                      {q.options.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <textarea
                      rows={q.kind === "long" ? 3 : 2}
                      value={answers[q.code] || ""}
                      onChange={(e) => setAnswers((a) => ({ ...a, [q.code]: e.target.value }))}
                    />
                  )}
                </label>
              ))}
              <button type="submit" className="mgmt-btn">
                Сохранить ответы
              </button>
            </form>
          )}
        </>
      ) : null}
    </ConsultingShell>
  );
}
