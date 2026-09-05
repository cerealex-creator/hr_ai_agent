"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  getConsultingSurveyPublic,
  submitConsultingSurveyPublic,
  type ConsultingSurveyQuestion,
} from "@/lib/consulting";

type Step = "who" | "preamble" | "question" | "done";

export default function ConsultingSurveyPublicPage() {
  const params = useParams();
  const token = String(params.token || "");
  const [title, setTitle] = useState("");
  const [customer, setCustomer] = useState("");
  const [questions, setQuestions] = useState<ConsultingSurveyQuestion[]>([]);
  const [people, setPeople] = useState<{ id: string; full_name: string; title: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [personId, setPersonId] = useState("");
  const [fullName, setFullName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [step, setStep] = useState<Step>("who");
  const [qIndex, setQIndex] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    getConsultingSurveyPublic(token)
      .then((d) => {
        setTitle(d.title);
        setCustomer(d.customer_name);
        setQuestions(d.questions || []);
        setPeople(d.people || []);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Опрос недоступен"));
  }, [token]);

  const sections = useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, ConsultingSurveyQuestion[]>();
    for (const q of questions) {
      if (!map.has(q.section)) {
        order.push(q.section);
        map.set(q.section, []);
      }
      map.get(q.section)!.push(q);
    }
    return order.map((s) => ({ section: s, questions: map.get(s)! }));
  }, [questions]);

  const flat = useMemo(() => {
    const out: { kind: "preamble" | "question"; section: string; q?: ConsultingSurveyQuestion; preamble?: string }[] =
      [];
    for (const block of sections) {
      const pre = block.questions.find((q) => q.preamble)?.preamble || "";
      if (pre.trim()) out.push({ kind: "preamble", section: block.section, preamble: pre });
      for (const q of block.questions) out.push({ kind: "question", section: block.section, q });
    }
    return out;
  }, [sections]);

  const current = flat[qIndex];
  const totalQ = questions.length;

  function start() {
    if (personId) {
      const p = people.find((x) => x.id === personId);
      if (p) {
        setFullName(p.full_name);
        setJobTitle(p.title || jobTitle);
      }
    }
    if (!fullName.trim() && !personId) {
      setErr("Укажите ФИО или выберите из списка");
      return;
    }
    if (!jobTitle.trim() && !personId) {
      setErr("Укажите должность");
      return;
    }
    if (personId) {
      const p = people.find((x) => x.id === personId);
      if (p && !p.title && !jobTitle.trim()) {
        setErr("Укажите должность");
        return;
      }
    }
    setErr(null);
    setStep(flat.length ? (flat[0].kind === "preamble" ? "preamble" : "question") : "done");
    setQIndex(0);
  }

  async function finish() {
    setBusy(true);
    setErr(null);
    try {
      const p = people.find((x) => x.id === personId);
      await submitConsultingSurveyPublic(token, {
        person_id: personId || null,
        full_name: p?.full_name || fullName,
        title: p?.title || jobTitle,
        answers,
        mode: "self",
      });
      setStep("done");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  if (err && !questions.length) {
    return (
      <div className="consult-survey">
        <p className="consult-err">{err}</p>
      </div>
    );
  }

  return (
    <div className="consult-survey">
      <p className="consult-kicker">Опрос</p>
      <h1>{customer || title}</h1>
      {err ? <p className="consult-err">{err}</p> : null}

      {step === "who" ? (
        <div className="consult-survey-card">
          <h2>Кто отвечает</h2>
          <p className="muted">Анонимно пройти нельзя. Можно выбрать из списка или вписать ФИО и должность.</p>
          {people.length ? (
            <label className="consult-label">
              Из паспорта
              <select
                value={personId}
                onChange={(e) => {
                  setPersonId(e.target.value);
                  const p = people.find((x) => x.id === e.target.value);
                  if (p) {
                    setFullName(p.full_name);
                    setJobTitle(p.title || "");
                  }
                }}
              >
                <option value="">Вписать вручную</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name}
                    {p.title ? ` — ${p.title}` : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="consult-label">
            ФИО
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required={!personId} />
          </label>
          <label className="consult-label">
            Должность
            <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} required={!personId} />
          </label>
          <button type="button" className="mgmt-btn" onClick={start}>
            Далее
          </button>
        </div>
      ) : null}

      {(step === "preamble" || step === "question") && current ? (
        <div className="consult-survey-card">
          <p className="muted">
            {current.kind === "question" ? `${Math.min(qIndex + 1, totalQ)} из ${totalQ}` : current.section}
          </p>
          {current.kind === "preamble" ? (
            <>
              <h2>{current.section}</h2>
              <p>{current.preamble}</p>
            </>
          ) : current.q ? (
            <>
              <h2>{current.q.text}</h2>
              {current.q.kind === "single" ? (
                <div className="consult-survey-options">
                  {current.q.options.map((o) => (
                    <button
                      key={o}
                      type="button"
                      className={`consult-survey-opt${answers[current.q!.code] === o ? " is-on" : ""}`}
                      onClick={() => setAnswers((a) => ({ ...a, [current.q!.code]: o }))}
                    >
                      {o}
                    </button>
                  ))}
                </div>
              ) : (
                <textarea
                  rows={current.q.kind === "long" ? 5 : 3}
                  value={answers[current.q.code] || ""}
                  onChange={(e) => setAnswers((a) => ({ ...a, [current.q!.code]: e.target.value }))}
                />
              )}
            </>
          ) : null}
          <div className="consult-actions">
            <button
              type="button"
              className="consult-btn-secondary"
              disabled={qIndex === 0}
              onClick={() => {
                const next = Math.max(0, qIndex - 1);
                setQIndex(next);
                setStep(flat[next]?.kind === "preamble" ? "preamble" : "question");
              }}
            >
              Назад
            </button>
            <button
              type="button"
              className="mgmt-btn"
              disabled={busy}
              onClick={() => {
                if (qIndex >= flat.length - 1) {
                  void finish();
                  return;
                }
                const next = qIndex + 1;
                setQIndex(next);
                setStep(flat[next]?.kind === "preamble" ? "preamble" : "question");
              }}
            >
              {qIndex >= flat.length - 1 ? (busy ? "Отправка…" : "Отправить") : "Далее"}
            </button>
          </div>
        </div>
      ) : null}

      {step === "done" ? (
        <div className="consult-survey-card">
          <h2>Спасибо</h2>
          <p>Ответы сохранены.</p>
        </div>
      ) : null}
    </div>
  );
}
