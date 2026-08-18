"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import { DemoBanner } from "@/components/DemoBanner";
import { getApiBase } from "@/lib/api";

type PreviewCard = {
  id: string;
  name: string;
  photo_url?: string | null;
  gender?: string | null;
  resume_url?: string | null;
  ai_strengths?: string[];
  ai_weaknesses?: string[];
  status: string;
  actionable: boolean;
  ready?: boolean;
};

type PreviewData = {
  vacancy: {
    vacancy_title?: string;
    company_name?: string;
    department_name?: string | null;
    demo?: boolean;
  };
  candidates: PreviewCard[];
  demo?: boolean;
};

const STATUS_LABEL: Record<string, string> = {
  wait: "На рассмотрении",
  consider: "Можно рассмотреть",
  reject: "Отказ",
};

async function previewFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBase()}${path}`, { ...init, cache: "no-store" });
}

export default function ResumePreviewPage() {
  const params = useParams();
  const token = String(params.token || "");
  const [data, setData] = useState<PreviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [localMsg, setLocalMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await previewFetch(`/api/v1/resume-preview/${encodeURIComponent(token)}`);
    if (!res.ok) {
      setError(res.status === 404 ? "Ссылка недействительна или устарела" : `Ошибка ${res.status}`);
      setData(null);
      return;
    }
    setData((await res.json()) as PreviewData);
    setError(null);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [token, load]);

  const decide = async (id: string, action: "consider" | "reject") => {
    setBusyId(id);
    setLocalMsg(null);
    try {
      const res = await previewFetch(
        `/api/v1/resume-preview/${encodeURIComponent(token)}/candidates/${id}/decide`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(typeof body?.detail === "string" ? body.detail : `Ошибка ${res.status}`);
      }
      setLocalMsg(action === "consider" ? "Отметили: можно рассмотреть" : "Отметили отказ");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusyId(null);
    }
  };

  const title = data?.vacancy.vacancy_title || "Макеты резюме";
  const place = [data?.vacancy.company_name, data?.vacancy.department_name].filter(Boolean).join(" · ");

  return (
    <div className="cz-page rp-page">
      {data?.demo ? <DemoBanner /> : null}
      <header className="cz-header">
        <p className="cz-kicker">Макеты резюме</p>
        <h1 className="cz-title">{data ? title : "Загрузка…"}</h1>
        {place ? <p className="cz-place">{place}</p> : null}
        <p className="muted">
          PDF без контактов. Откройте резюме кнопкой, затем отметьте «Можно рассмотреть» или «Отказ».
        </p>
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}
      {localMsg ? <p className="ok cz-banner">{localMsg}</p> : null}
      {!data && !error ? <p className="muted">Загрузка макетов…</p> : null}

      {data && data.candidates.length === 0 ? (
        <div className="cz-empty">
          <p className="muted">Пока нет макетов на согласование.</p>
        </div>
      ) : null}

      <div className="rp-grid">
        {(data?.candidates || []).map((c) => (
          <article key={c.id} className={`rp-card${c.actionable ? "" : " rp-card-done"}`}>
            <div className="rp-card-head">
              <CandidateAvatar
                name={c.name}
                photoUrl={c.photo_url}
                gender={c.gender}
                size={72}
                className="cz-avatar"
              />
              <div>
                <h2 className="rp-card-name">{c.name}</h2>
                <span className="cz-pill cz-pill-status">{STATUS_LABEL[c.status] || c.status}</span>
              </div>
            </div>
            {c.ai_strengths && c.ai_strengths.length ? (
              <ul className="rp-plus">
                {c.ai_strengths.map((line) => (
                  <li key={`plus-${line}`}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="muted hh-micro">Кратких плюсов ИИ пока нет</p>
            )}
            {c.ai_weaknesses && c.ai_weaknesses.length ? (
              <ul className="rp-minus">
                {c.ai_weaknesses.map((line) => (
                  <li key={`minus-${line}`}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="muted hh-micro">Кратких минусов ИИ пока нет</p>
            )}
            {c.resume_url ? (
              <a
                className="cz-tap cz-tap-primary"
                href={c.resume_url}
                target="_blank"
                rel="noreferrer"
              >
                Посмотреть резюме
              </a>
            ) : (
              <p className="muted hh-micro">Ссылка на PDF ещё не готова</p>
            )}
            {c.actionable ? (
              <div className="rp-actions">
                <button
                  type="button"
                  className="cz-tap"
                  disabled={busyId === c.id}
                  onClick={() => void decide(c.id, "consider")}
                >
                  Можно рассмотреть
                </button>
                <button
                  type="button"
                  className="cz-tap rp-reject"
                  disabled={busyId === c.id}
                  onClick={() => void decide(c.id, "reject")}
                >
                  Отказ
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
