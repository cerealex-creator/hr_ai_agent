"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ClientZoneDecideForm } from "@/components/ClientZoneDecideForm";
import {
  CZ_STATUS_LABELS,
  type ZoneCandidateDetail,
  type ZoneDetailData,
  zoneFetch,
} from "@/lib/clientZone";

export default function ClientZoneCandidatePage() {
  const params = useParams();
  const token = String(params.token || "");
  const candidateId = String(params.candidateId || "");
  const [data, setData] = useState<ZoneDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);

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
  const links = c
    ? [
        c.resume_url ? { href: c.resume_url, label: "Смотреть резюме" } : null,
        c.video_url ? { href: c.video_url, label: "Смотреть запись" } : null,
        c.portfolio_url ? { href: c.portfolio_url, label: "Портфолио" } : null,
        c.task_url ? { href: c.task_url, label: "Задание" } : null,
        ...(c.extra_materials || []).map((m) => ({ href: m.url, label: m.title })),
      ].filter(Boolean) as { href: string; label: string }[]
    : [];

  return (
    <div className="cz-page cz-page-detail">
      <header className="cz-header">
        <Link href={`/c/${token}`} className="cz-back">
          ← Все кандидаты
        </Link>
        <p className="cz-kicker">{data?.company.name || "Клиентская зона"}</p>
        <h1 className="cz-title">{c?.name || "Загрузка…"}</h1>
        {c ? (
          <p className="muted">
            {c.vacancy_title}
            {c.client_name ? ` · ${c.client_name}` : ""}
            {" · "}
            {CZ_STATUS_LABELS[c.client_status] || c.client_status}
            {c.ai_score != null ? ` · оценка ИИ ${c.ai_score}` : ""}
          </p>
        ) : null}
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}
      {msg ? <p className="ok cz-banner">{msg}</p> : null}

      {c ? (
        <>
          {links.length ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Материалы</h2>
              <div className="cz-link-stack">
                {links.map((item) => (
                  <a
                    key={`${item.label}-${item.href}`}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className="cz-tap cz-tap-primary"
                  >
                    {item.label}
                  </a>
                ))}
              </div>
            </section>
          ) : (
            <p className="muted cz-banner">Резюме и запись появятся здесь, когда HR их добавит.</p>
          )}

          {c.interview_digest ? (
            <section className="cz-section">
              <button
                type="button"
                className="cz-tap"
                onClick={() => setDigestOpen((v) => !v)}
              >
                {digestOpen ? "Скрыть краткий текст собеседования" : "Краткий текст собеседования"}
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
            </section>
          ) : null}

          {c.hr_comment ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Комментарий HR</h2>
              <p className="cz-comment">{c.hr_comment}</p>
            </section>
          ) : null}

          {c.ai_comment ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Комментарий ИИ</h2>
              <p className="cz-comment">{c.ai_comment}</p>
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
                setMsg("Решение сохранено");
                void load();
              }}
            />
          ) : (
            <p className="muted cz-banner">Решение уже зафиксировано.</p>
          )}
        </>
      ) : null}
    </div>
  );
}
