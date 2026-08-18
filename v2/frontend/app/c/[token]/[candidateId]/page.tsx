"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import { ClientZoneDecideForm } from "@/components/ClientZoneDecideForm";
import { DemoBanner } from "@/components/DemoBanner";
import {
  CZ_STATUS_LABELS,
  type ZoneCandidateDetail,
  type ZoneDetailData,
  zoneFetch,
  zonePlaceLabel,
} from "@/lib/clientZone";

export default function ClientZoneCandidatePage() {
  const params = useParams();
  const router = useRouter();
  const token = String(params.token || "");
  const candidateId = String(params.candidateId || "");
  const [data, setData] = useState<ZoneDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);

  const load = useCallback(async () => {
    const res = await zoneFetch(
      `/api/v1/client-zone/${encodeURIComponent(token)}/candidates/${candidateId}`,
    );
    if (!res.ok) {
      setError(res.status === 404 ? "Кандидат не найден или ссылка устарела" : `Ошибка ${res.status}`);
      setData(null);
      return;
    }
    setData((await res.json()) as ZoneDetailData);
    setError(null);
  }, [token, candidateId]);

  useEffect(() => {
    if (!token || !candidateId) return;
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [token, candidateId, load]);

  const c: ZoneCandidateDetail | null = data?.candidate || null;
  const place = c ? zonePlaceLabel(c) : "";
  const links = c
    ? [
        c.resume_url ? { href: c.resume_url, label: "Смотреть резюме", primary: true } : null,
        c.video_url ? { href: c.video_url, label: "Смотреть запись", primary: false } : null,
        c.portfolio_url ? { href: c.portfolio_url, label: "Портфолио", primary: false } : null,
        c.task_url ? { href: c.task_url, label: "Задание", primary: false } : null,
        ...(c.extra_materials || []).map((m) => ({ href: m.url, label: m.title, primary: false })),
      ].filter(Boolean) as { href: string; label: string; primary: boolean }[]
    : [];
  const hasMaterials = Boolean(c && (links.length || c.interview_digest || c.ai_comment));

  return (
    <div className="cz-page cz-page-detail">
      {data?.demo ? <DemoBanner /> : null}
      <header className="cz-header">
        <Link href={`/c/${token}`} className="cz-back">
          ← Все кандидаты
        </Link>
        <p className="cz-kicker">{data?.company.name || "Зона заказчика вакансии"}</p>
        {c ? (
          <div className="cz-detail-head">
            <CandidateAvatar
              name={c.name}
              photoUrl={c.photo_url}
              gender={c.gender}
              size={64}
              className="cz-avatar"
            />
            <div className="cz-detail-head-text">
              <h1 className="cz-title">{c.name}</h1>
              <p className="cz-vacancy">{c.vacancy_title}</p>
              {place ? <p className="cz-place">{place}</p> : null}
              <div className="cz-pills">
                <span className="cz-pill cz-pill-status">
                  {CZ_STATUS_LABELS[c.client_status] || c.client_status}
                </span>
                {c.ai_score != null ? <span className="cz-pill">ИИ {c.ai_score}</span> : null}
              </div>
            </div>
          </div>
        ) : (
          <h1 className="cz-title">Загрузка…</h1>
        )}
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}

      {c ? (
        <>
          {hasMaterials ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Материалы</h2>
              <div className="cz-link-stack">
                {links.map((item) => (
                  <a
                    key={`${item.label}-${item.href}`}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className={`cz-tap${item.primary ? " cz-tap-primary" : ""}`}
                  >
                    {item.label}
                  </a>
                ))}
                {c.interview_digest ? (
                  <>
                    <button
                      type="button"
                      className={`cz-tap${digestOpen ? " is-active" : ""}`}
                      onClick={() => setDigestOpen((v) => !v)}
                    >
                      {digestOpen ? "Скрыть конспект собеседования" : "Конспект собеседования"}
                    </button>
                    {digestOpen ? (
                      <div className="q-digest cz-digest">
                        {c.interview_digest.summary ? (
                          <p className="q-digest-summary">{c.interview_digest.summary}</p>
                        ) : null}
                        {c.interview_digest.qa.length ? (
                          <div className="q-digest-list">
                            {c.interview_digest.qa.map((row, i) => (
                              <div key={`${i}-${row.q.slice(0, 24)}`} className="q-digest-item">
                                <p className="q-digest-q">
                                  <strong>В:</strong> {row.q || "—"}
                                </p>
                                <p className="q-digest-a">
                                  <strong>О:</strong> {row.a || "—"}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                ) : null}
                {c.ai_comment ? (
                  <>
                    <button
                      type="button"
                      className={`cz-tap${aiOpen ? " is-active" : ""}`}
                      onClick={() => setAiOpen((v) => !v)}
                    >
                      {aiOpen ? "Скрыть оценку ИИ" : "Оценка ИИ"}
                    </button>
                    {aiOpen ? (
                      <div className="q-digest cz-digest">
                        <p className="cz-comment">{c.ai_comment}</p>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            </section>
          ) : (
            <p className="muted cz-banner">Резюме и запись появятся здесь, когда HR их добавит.</p>
          )}

          {c.hr_comment ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Комментарий HR</h2>
              <p className="cz-comment">{c.hr_comment}</p>
            </section>
          ) : null}

          {c.office_interview_date && c.office_interview_time ? (
            <p className="muted">
              Встреча: {c.office_interview_date} {c.office_interview_time}
            </p>
          ) : null}

          {c.actionable ? (
            <ClientZoneDecideForm
              token={token}
              candidateId={c.id}
              onDone={() => {
                router.replace(`/c/${encodeURIComponent(token)}?saved=1`);
              }}
            />
          ) : (
            <p className="muted cz-banner">
              {data?.demo
                ? "В демо-режиме решение оставить нельзя — только просмотр."
                : "Решение уже зафиксировано."}
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}
