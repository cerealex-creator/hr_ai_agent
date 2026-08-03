"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { getApiBase, type VacancyDetail } from "@/lib/api";
import { ChatSelect } from "@/components/ChatSelect";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { VacancyStageSchemaPanel } from "@/components/VacancyStageSchemaPanel";

type Props = { vacancy: VacancyDetail };

export function VacancySettingsPanel({ vacancy }: Props) {
  const router = useRouter();
  const payload = vacancy.payload || {};
  const [isTest, setIsTest] = useState(Boolean(payload.is_test));
  const [showPortfolio, setShowPortfolio] = useState(Boolean(payload.show_portfolio_field));
  const [cwEnabled, setCwEnabled] = useState(Boolean(payload.control_word_enabled));
  const [controlWord, setControlWord] = useState(String(payload.control_word || ""));
  const [chatId, setChatId] = useState(vacancy.chat_id || "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancy.id}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_test: isTest,
          show_portfolio_field: showPortfolio,
          control_word_enabled: cwEnabled,
          control_word: controlWord,
          chat_id: chatId,
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
      const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancy.id}/digest-to-chat`, {
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
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancy.id}/warranty/create-search`,
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
    <CollapsibleCard
      title="Параметры вакансии"
      hint={hintBits.length ? hintBits.join(" · ") : undefined}
      defaultOpen={false}
    >
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
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
          disabled={busy}
        />
        Тестовая вакансия
      </label>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={showPortfolio}
          onChange={(e) => setShowPortfolio(e.target.checked)}
          disabled={busy}
        />
        Показывать поле портфолио
      </label>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={cwEnabled}
          onChange={(e) => setCwEnabled(e.target.checked)}
          disabled={busy}
        />
        Контрольное слово
      </label>
      {cwEnabled ? (
        <div className="hh-field">
          <input
            value={controlWord}
            onChange={(e) => setControlWord(e.target.value)}
            disabled={busy}
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
    </CollapsibleCard>

    <CollapsibleCard title="Этапы и статусы вакансии" defaultOpen={false}>
      <VacancyStageSchemaPanel vacancyId={vacancy.id} />
    </CollapsibleCard>
    </>
  );
}
