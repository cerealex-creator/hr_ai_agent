"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import { DemoBanner } from "@/components/DemoBanner";
import {
  CZ_STATUS_LABELS,
  type ZoneListData,
  zoneFetch,
  zonePlaceLabel,
} from "@/lib/clientZone";

export default function ClientZoneTokenPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const token = String(params.token || "");
  const [data, setData] = useState<ZoneListData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(
    searchParams.get("saved") === "1" ? "Решение сохранено" : null,
  );

  const load = useCallback(async () => {
    const res = await zoneFetch(`/api/v1/client-zone/${encodeURIComponent(token)}`);
    if (!res.ok) {
      setError(res.status === 404 ? "Ссылка недействительна или устарела" : `Ошибка ${res.status}`);
      setData(null);
      return;
    }
    const json = (await res.json()) as ZoneListData;
    setData(json);
    setError(null);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [token, load]);

  return (
    <div className="cz-page">
      {data?.demo ? <DemoBanner /> : null}
      <header className="cz-header">
        <p className="cz-kicker">Зона заказчика вакансии</p>
        <h1 className="cz-title">{data?.company.name || "Загрузка…"}</h1>
        {data?.company.department_name ? (
          <p className="cz-place">{data.company.department_name}</p>
        ) : null}
        <p className="muted">Откройте карточку кандидата, чтобы посмотреть материалы и оставить решение.</p>
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}
      {msg ? <p className="ok cz-banner">{msg}</p> : null}

      {!data && !error ? <p className="muted">Загрузка кандидатов…</p> : null}

      {data && data.candidates.length === 0 ? (
        <div className="cz-empty">
          <p className="muted">Сейчас нет кандидатов на рассмотрении.</p>
          <p className="muted hh-micro">
            Кандидаты появятся здесь, когда HR отправит их вам. Откройте ссылку целиком (с адресом
            сайта, не только <code>/c/…</code>).
          </p>
        </div>
      ) : null}

      <div className="cz-list">
        {(data?.candidates || []).map((c) => {
          const place = zonePlaceLabel(c);
          return (
            <Link
              key={c.id}
              href={`/c/${token}/${c.id}`}
              className={`cz-card cz-card-link${c.actionable ? "" : " cz-card-done"}`}
            >
              <div className="cz-card-top">
                <div className="cz-card-identity">
                  <CandidateAvatar
                    name={c.name}
                    photoUrl={c.photo_url}
                    gender={c.gender}
                    size={44}
                    className="cz-avatar"
                  />
                  <h2>{c.name}</h2>
                </div>
                <span className="cz-pill cz-pill-status">
                  {CZ_STATUS_LABELS[c.client_status] || c.client_status}
                </span>
              </div>
              <p className="cz-vacancy">{c.vacancy_title}</p>
              {place ? <p className="cz-place">{place}</p> : null}
              <p className="cz-card-meta muted hh-micro">
                {[
                  c.has_resume ? "резюме" : null,
                  c.has_video ? "запись" : null,
                  c.has_digest ? "конспект" : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "материалы появятся здесь"}
              </p>
              <span className="cz-tap cz-tap-ghost">Смотреть кандидата</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
