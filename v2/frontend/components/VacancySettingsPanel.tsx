"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { type VacancyDetail, apiFetch } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";
import { DEMO_WRITE_HINT } from "@/lib/demo";
import { ChatSelect } from "@/components/ChatSelect";
import { VacancyStageSchemaPanel } from "@/components/VacancyStageSchemaPanel";
import {
  VACANCY_AVATAR_KEYS,
  VACANCY_AVATAR_LABELS,
  VacancyAvatar,
  type VacancyAvatarKey,
} from "@/components/VacancyAvatar";

type Props = { vacancy: VacancyDetail };

export function VacancySettingsPanel({ vacancy }: Props) {
  const { isDemo } = useAuth();
  const router = useRouter();
  const payload = vacancy.payload || {};
  const [isTest, setIsTest] = useState(Boolean(payload.is_test));
  const [showPortfolio, setShowPortfolio] = useState(Boolean(payload.show_portfolio_field));
  const [cwEnabled, setCwEnabled] = useState(Boolean(payload.control_word_enabled));
  const [controlWord, setControlWord] = useState(String(payload.control_word || ""));
  const [chatId, setChatId] = useState(vacancy.chat_id || "");
  const [avatarKey, setAvatarKey] = useState(
    String((payload.avatar_key as string) || vacancy.avatar_key || "general"),
  );
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    if (isDemo) {
      setErr(DEMO_WRITE_HINT);
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancy.id}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_test: isTest,
          show_portfolio_field: showPortfolio,
          control_word_enabled: cwEnabled,
          control_word: controlWord,
          chat_id: chatId,
          avatar_key: avatarKey,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setMsg("Сохранено");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const digest = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancy.id}/digest-to-chat`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setMsg(data.message || "Статистика отправлена");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const createWarrantySearch = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancy.id}/warranty/create-search`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setMsg("Гарантийный поиск создан");
      router.push(`/vacancies/${data.id}`);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const searchMode = String(payload.search_mode || "normal");
  const warranty = (payload.warranty || {}) as {
    active?: boolean;
    start_date?: string;
    months?: number;
  };
  const hintBits = [
    searchMode === "warranty" ? "гарантийный" : null,
    isTest ? "тест" : null,
    vacancy.chat_id ? "чат" : null,
  ].filter(Boolean);

  return (
    <>
    <div className="rec-card">
      <h3 className="rec-card-title">
        Параметры вакансии
        {hintBits.length ? (
          <span className="muted hh-micro" style={{ marginLeft: "0.5rem" }}>
            {hintBits.join(" · ")}
          </span>
        ) : null}
      </h3>
      {isDemo ? <p className="warn cz-banner">{DEMO_WRITE_HINT}</p> : null}
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <div className="hh-field" style={{ marginBottom: "0.85rem" }}>
        <span className="hh-label">Аватарка</span>
        <div className="vac-avatar-picker">
          {VACANCY_AVATAR_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className={`vac-avatar-pick${avatarKey === key ? " is-active" : ""}`}
              disabled={busy || isDemo}
              onClick={() => setAvatarKey(key)}
              title={VACANCY_AVATAR_LABELS[key as VacancyAvatarKey]}
            >
              <VacancyAvatar avatarKey={key} size={36} />
            </button>
          ))}
        </div>
        <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
          Подбирается по названию при создании; здесь можно сменить вручную.
        </p>
      </div>
      {searchMode === "warranty" ? <p className="ok">Гарантийный поиск</p> : null}
      {warranty.active ? (
        <p className="muted">
          Гарантия активна с {warranty.start_date || "—"} · {warranty.months || "?"} мес
        </p>
      ) : null}
      <label className="hh-check">
        <input
          type="checkbox"
          checked={isTest}
          onChange={(e) => setIsTest(e.target.checked)}
          disabled={busy || isDemo}
        />
        Тестовая вакансия
      </label>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={showPortfolio}
          onChange={(e) => setShowPortfolio(e.target.checked)}
          disabled={busy || isDemo}
        />
        Показывать поле портфолио
      </label>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={cwEnabled}
          onChange={(e) => setCwEnabled(e.target.checked)}
          disabled={busy || isDemo}
        />
        Контрольное слово
      </label>
      {cwEnabled ? (
        <div className="hh-field">
          <input
            value={controlWord}
            onChange={(e) => setControlWord(e.target.value)}
            disabled={busy || isDemo}
            placeholder="слово"
          />
        </div>
      ) : null}
      <ChatSelect value={chatId} onChange={setChatId} disabled={busy} id="vac-settings-chat" />
      <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
        <button type="button" className="chip chip-active" disabled={busy} onClick={save}>
          Сохранить
        </button>
        <button type="button" className="chip" disabled={busy} onClick={digest}>
          Статистика в чат
        </button>
        <button type="button" className="chip" disabled={busy} onClick={createWarrantySearch}>
          Открыть гарантийный поиск
        </button>
      </div>
    </div>

    <div className="rec-card">
      <h3 className="rec-card-title">Этапы и статусы вакансии</h3>
      <VacancyStageSchemaPanel vacancyId={vacancy.id} />
    </div>
    </>
  );
}
