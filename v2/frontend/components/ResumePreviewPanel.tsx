"use client";

import { useCallback, useEffect, useState } from "react";
import { ActionBanner } from "@/components/ActionBanner";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";

export type PreviewPackItem = {
  id: string;
  name: string;
  included: boolean;
  visible?: boolean;
  ready: boolean;
  has_photo: boolean;
  photo_url?: string | null;
  gender?: string | null;
  strengths_count: number;
  weaknesses_count?: number;
  hr_comment?: string;
  status: string;
  anonymized_resume_link: string;
  resume_url: string | null;
};

export type PreviewPack = {
  token?: string | null;
  path?: string | null;
  public_url?: string | null;
  sent_at?: string | null;
  included_count: number;
  ready_count: number;
  candidates: PreviewPackItem[];
};

const STATUS_LABEL: Record<string, string> = {
  wait: "ждёт решения",
  consider: "можно рассмотреть",
  reject: "отказ",
};

function packHref(pack: PreviewPack | null): string {
  if (!pack) return "";
  if (pack.public_url) return pack.public_url;
  if (pack.path && typeof window !== "undefined") {
    return `${window.location.origin}${pack.path}`;
  }
  return pack.path || "";
}

export function ResumePreviewPanel({ vacancyId, hasChatId }: { vacancyId: number; hasChatId: boolean }) {
  const { isOwner } = useAuth();
  const [pack, setPack] = useState<PreviewPack | null>(null);
  const [linksText, setLinksText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/resume-preview`);
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as PreviewPack;
    setPack(data);
    const drafts: Record<string, string> = {};
    for (const c of data.candidates || []) {
      drafts[c.id] = c.hr_comment || "";
    }
    setCommentDrafts(drafts);
  }, [vacancyId]);

  useEffect(() => {
    if (!isOwner) return;
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [isOwner, load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const addLinks = () =>
    run(async () => {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/candidates/bulk-links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: linksText, evaluate: true, for_resume_preview: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setLinksText("");
      setAddOpen(false);
      const extra = Array.isArray(data.messages) ? data.messages.join("\n") : "";
      setMsg(
        `Добавлено в макеты: ${data.created || 0}. Лёгкая оценка ИИ (без опросника) поставлена в очередь — плюсы появятся на карточках, когда закончится.` +
          (extra ? `\n${extra}` : ""),
      );
      await load();
    });

  const toggleVisible = (id: string, visible: boolean) =>
    run(async () => {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/resume-preview/candidates/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visible }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setPack(data as PreviewPack);
    });

  const toggle = (id: string, included: boolean) =>
    run(async () => {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/resume-preview/candidates/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ included }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setPack(data as PreviewPack);
    });

  const saveComment = (id: string) =>
    run(async () => {
      const next = (commentDrafts[id] ?? "").trim();
      const prev = (pack?.candidates.find((c) => c.id === id)?.hr_comment || "").trim();
      if (next === prev) return;
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/resume-preview/candidates/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hr_comment: next }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setPack(data as PreviewPack);
      const drafts: Record<string, string> = {};
      for (const c of (data as PreviewPack).candidates || []) {
        drafts[c.id] = c.hr_comment || "";
      }
      setCommentDrafts(drafts);
      setMsg("Комментарий для заказчика сохранён");
    });

  const ensureLink = () =>
    run(async () => {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/resume-preview/ensure`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setPack(data as PreviewPack);
      setMsg("Ссылка на зону макетов готова");
    });

  const sendChat = () =>
    run(async () => {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/resume-preview/send`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setMsg(typeof data.message === "string" ? data.message : "Отправлено в Telegram");
      await load();
    });

  const copyLink = async () => {
    const href = packHref(pack);
    if (!href) {
      await ensureLink();
      return;
    }
    try {
      await navigator.clipboard.writeText(href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setErr("Не удалось скопировать");
    }
  };

  const href = packHref(pack);
  const ready = pack?.ready_count || 0;
  const waiting = (pack?.included_count || 0) - ready;

  if (!isOwner) return null;

  return (
    <div className="rec-card" id="resume-preview-pack">
      <h3 className="rec-card-title">Макеты резюме для заказчика</h3>
      <p className="muted hh-micro" style={{ marginTop: 0 }}>
        Отдельная клиентская зона: PDF без контактов с Яндекс.Диска, фото и плюсы ИИ. Телефон и
        почта туда не попадают. Обычная зона <code>/c/…</code> не меняется.
      </p>
      <ActionBanner msg={msg} err={err} />

      <div className="rp-add-wrap">
        <button
          type="button"
          className="chip"
          disabled={busy}
          aria-expanded={addOpen}
          onClick={() => setAddOpen((v) => !v)}
        >
          {addOpen ? "Свернуть" : "Добавить резюме"}
        </button>
        {addOpen ? (
          <div className="rp-add-panel">
            <div className="hh-field">
              <label className="hh-label" htmlFor="preview-links">
                Ссылки на PDF без контактов
              </label>
              <textarea
                id="preview-links"
                rows={4}
                value={linksText}
                onChange={(e) => setLinksText(e.target.value)}
                disabled={busy}
                placeholder={"https://disk.yandex.ru/i/…\nhttps://disk.yandex.ru/d/…"}
              />
            </div>
            <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
              <button
                type="button"
                className="chip chip-active"
                disabled={busy || !linksText.trim()}
                onClick={() => void addLinks()}
              >
                Загрузить в макеты
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap", marginTop: "0.65rem" }}>
        <button type="button" className="chip" disabled={busy} onClick={() => void ensureLink()}>
          Получить ссылку
        </button>
        <button type="button" className="chip" disabled={busy || !href} onClick={() => void copyLink()}>
          {copied ? "Скопировано" : "Копировать ссылку"}
        </button>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !hasChatId || ready < 1}
          onClick={() => void sendChat()}
        >
          Отправить в Telegram
        </button>
      </div>
      {!hasChatId ? (
        <p className="muted hh-micro">Чтобы отправить в чат, укажите Chat ID вакансии в настройках.</p>
      ) : null}

      {href ? (
        <p className="hh-micro" style={{ marginTop: "0.65rem" }}>
          Зона макетов:{" "}
          <a href={href} target="_blank" rel="noreferrer">
            {href}
          </a>
        </p>
      ) : null}

      <p className="muted hh-micro">
        Готово к показу заказчику: <strong>{ready}</strong>
        {waiting > 0 ? ` · без ссылки PDF: ${waiting}` : ""}
        {pack?.sent_at ? " · уже отправляли в чат" : ""}
      </p>

      {pack?.candidates?.length ? (
        <>
          <h4 className="hh-subhead" style={{ marginTop: "1rem" }}>
            Список макетов
          </h4>
          <ul className="rp-hr-list">
          {pack.candidates.map((c) => (
            <li key={c.id} className="rp-hr-row-stack">
              <div className="rp-hr-row">
              <div className="rp-hr-row-main">
                <CandidateAvatar
                  name={c.name}
                  photoUrl={c.photo_url}
                  gender={c.gender}
                  size={40}
                  className="rec-row-avatar"
                />
                <div>
                  <a href={`/candidates/${c.id}`}>{c.name}</a>
                  <span className="muted hh-micro">
                    {" "}
                    {c.ready ? "PDF готов" : "нужна ссылка Диска"}
                    {c.strengths_count ? ` · плюсы ИИ: ${c.strengths_count}` : ""}
                    {c.weaknesses_count ? ` · минусы ИИ: ${c.weaknesses_count}` : ""}
                    {c.status && c.status !== "wait" ? ` · ${STATUS_LABEL[c.status] || c.status}` : ""}
                  </span>
                </div>
              </div>
              <div className="rp-hr-row-actions">
                <label className="hh-check rp-hr-visible">
                  <input
                    type="checkbox"
                    checked={c.visible !== false}
                    disabled={busy || !c.ready}
                    onChange={(e) => void toggleVisible(c.id, e.target.checked)}
                  />
                  В зоне заказчика
                </label>
                <button
                  type="button"
                  className="chip"
                  disabled={busy}
                  onClick={() => void toggle(c.id, false)}
                >
                  Убрать
                </button>
              </div>
              </div>
              <label className="hh-field rp-hr-comment">
                <span className="hh-label">Комментарий для заказчика</span>
                <textarea
                  rows={2}
                  value={commentDrafts[c.id] ?? c.hr_comment ?? ""}
                  disabled={busy}
                  placeholder="Коротко: почему стоит или не стоит смотреть кандидата"
                  onChange={(e) =>
                    setCommentDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                  }
                  onBlur={() => void saveComment(c.id)}
                />
              </label>
            </li>
          ))}
        </ul>
        </>
      ) : (
        <p className="muted hh-micro">Пока нет макетов. Вставьте ссылки на PDF с Диска.</p>
      )}
    </div>
  );
}
