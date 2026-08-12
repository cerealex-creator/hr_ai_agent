"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

type Digest = {
  summary?: string;
  qa?: { q: string; a: string }[];
  created_at?: string | null;
};

type PageData = {
  candidate_name: string;
  vacancy_title: string | null;
  digest: Digest;
};

export default function InterviewDigestPublicPage() {
  const params = useParams();
  const token = String(params.token || "");
  const [data, setData] = useState<PageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch(
      `${getApiBase()}/api/v1/interview-digest/${encodeURIComponent(token)}`,
      { cache: "no-store" },
    );
    if (!res.ok) {
      setError(
        res.status === 404
          ? "Ссылка недействительна или выжимка ещё не готова"
          : `Ошибка ${res.status}`,
      );
      setData(null);
      return;
    }
    setData((await res.json()) as PageData);
    setError(null);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [token, load]);

  const qa = data?.digest?.qa || [];

  return (
    <div className="cz-page">
      <header className="cz-header">
        <p className="cz-kicker">Выжимка собеседования</p>
        <h1 className="cz-title">{data?.candidate_name || "Загрузка…"}</h1>
        {data?.vacancy_title ? (
          <p className="muted">{data.vacancy_title}</p>
        ) : null}
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}
      {!data && !error ? <p className="muted">Загрузка…</p> : null}

      {data ? (
        <article className="cz-card">
          {data.digest.summary ? (
            <>
              <h2 className="hh-subhead">Кратко</h2>
              <p>{data.digest.summary}</p>
            </>
          ) : null}

          {qa.length ? (
            <>
              <h2 className="hh-subhead">Вопрос → ответ</h2>
              <div className="q-digest-list">
                {qa.map((row, i) => (
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
            </>
          ) : (
            <p className="muted">Пар вопрос–ответ пока нет.</p>
          )}
        </article>
      ) : null}
    </div>
  );
}
