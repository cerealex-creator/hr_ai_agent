"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ChatSelect } from "@/components/ChatSelect";
import { type ClientItem, type VacancyListItem, apiFetch } from "@/lib/api";

type Props = {
  clients: ClientItem[];
  vacancies?: VacancyListItem[];
  defaultClientId?: number | null;
};

type Mode = "scratch" | "from_source";

function sourceLabel(v: VacancyListItem): string {
  const state = v.active ? "в работе" : "архив";
  const client = v.client_name ? ` · ${v.client_name}` : "";
  return `${v.title} (#${v.id}, ${state})${client}`;
}

export function CreateVacancyForm({
  clients,
  vacancies = [],
  defaultClientId = null,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("scratch");
  const [sourceId, setSourceId] = useState("");
  const [title, setTitle] = useState("");
  const [clientId, setClientId] = useState<string>(
    defaultClientId != null ? String(defaultClientId) : "",
  );
  const [chatId, setChatId] = useState("");
  const [isTest, setIsTest] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const sourceOptions = useMemo(() => {
    return [...vacancies].sort((a, b) => {
      if (a.active !== b.active) return a.active ? 1 : -1; // archive first
      return (a.title || "").localeCompare(b.title || "", "ru");
    });
  }, [vacancies]);

  const applySource = (id: string) => {
    setSourceId(id);
    const src = vacancies.find((v) => String(v.id) === id);
    if (!src) return;
    setTitle(src.title || "");
    setClientId(src.client_id != null ? String(src.client_id) : "");
    setChatId((src.chat_id || "").trim());
  };

  const resetForm = () => {
    setMode("scratch");
    setSourceId("");
    setTitle("");
    setClientId(defaultClientId != null ? String(defaultClientId) : "");
    setChatId("");
    setIsTest(false);
    setErr(null);
  };

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = {
        title: title.trim(),
        client_id: clientId ? Number(clientId) : null,
        chat_id: chatId.trim() || null,
        is_test: isTest,
      };
      if (mode === "from_source" && sourceId) {
        body.source_vacancy_id = Number(sourceId);
      }
      const res = await apiFetch(`/api/v1/vacancies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      resetForm();
      setOpen(false);
      router.push(`/vacancies/${data.id}?section=docs`);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка создания");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="chip chip-active" onClick={() => setOpen(true)}>
        + Новая вакансия
      </button>
    );
  }

  return (
    <section className="card-edit" style={{ marginBottom: "1rem" }}>
      <h2>Новая вакансия</h2>
      {err ? <p className="warn">{err}</p> : null}

      <div className="hh-field">
        <span className="hh-label">Способ создания</span>
        <div className="chip-row">
          <button
            type="button"
            className={mode === "scratch" ? "chip chip-active" : "chip"}
            disabled={busy}
            onClick={() => {
              setMode("scratch");
              setSourceId("");
            }}
          >
            С нуля
          </button>
          <button
            type="button"
            className={mode === "from_source" ? "chip chip-active" : "chip"}
            disabled={busy || !sourceOptions.length}
            onClick={() => setMode("from_source")}
          >
            Из существующей
          </button>
        </div>
        {!sourceOptions.length ? (
          <p className="muted hh-micro">Вакансий пока нет — только «С нуля».</p>
        ) : null}
      </div>

      {mode === "from_source" ? (
        <div className="hh-field">
          <label className="hh-label" htmlFor="vac-source">
            Исходная вакансия
          </label>
          <select
            id="vac-source"
            value={sourceId}
            onChange={(e) => applySource(e.target.value)}
            disabled={busy}
          >
            <option value="">— выберите —</option>
            {sourceOptions.map((v) => (
              <option key={v.id} value={v.id}>
                {sourceLabel(v)}
              </option>
            ))}
          </select>
          <p className="muted hh-micro">
            Копируются документы и настройки (чат, портфолио, контрольное слово, Я.Диск). Кандидаты не
            переносятся. Если исходная активна — измените название.
          </p>
        </div>
      ) : null}

      <div className="hh-field">
        <label className="hh-label" htmlFor="vac-title">
          Название
        </label>
        <input
          id="vac-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={busy}
          placeholder="Должность"
        />
      </div>
      <div className="hh-field">
        <label className="hh-label" htmlFor="vac-client">
          Клиент
        </label>
        <select
          id="vac-client"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          disabled={busy}
        >
          <option value="">— без клиента —</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <ChatSelect value={chatId} onChange={setChatId} disabled={busy} id="vac-chat" />
      <label className="hh-check">
        <input
          type="checkbox"
          checked={isTest}
          onChange={(e) => setIsTest(e.target.checked)}
          disabled={busy}
        />
        Тестовая вакансия
      </label>
      <div className="chip-row">
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !title.trim() || (mode === "from_source" && !sourceId)}
          onClick={() => void submit()}
        >
          {busy ? "Создание…" : "Создать"}
        </button>
        <button
          type="button"
          className="chip"
          disabled={busy}
          onClick={() => {
            resetForm();
            setOpen(false);
          }}
        >
          Отмена
        </button>
      </div>
    </section>
  );
}
