"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export type SearchPlan = {
  version?: number;
  status?: string;
  human_text?: string;
  machine?: Record<string, unknown>;
  notes?: string[];
  sources?: string[];
  approved_at?: string | null;
  updated_at?: string | null;
};

type Props = {
  vacancyId: number;
  plan: SearchPlan | null;
  maxSearch: number;
  maxEvaluate: number;
  onLimitsChange: (limits: { max_search: number; max_evaluate: number }) => void;
  onPlanChange: (plan: SearchPlan, criteria?: Record<string, unknown>) => void;
  onStartSearch: (opts?: {
    fromApprove?: boolean;
    criteria?: Record<string, unknown>;
  }) => void;
  searchBusy?: boolean;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

const STATUS_RU: Record<string, string> = {
  empty: "нет плана",
  draft: "черновик",
  approved: "утверждён",
  stale: "устарел",
};

export function HhSearchPlanBlock({
  vacancyId,
  plan,
  maxSearch,
  maxEvaluate,
  onLimitsChange,
  onPlanChange,
  onStartSearch,
  searchBusy,
}: Props) {
  const [note, setNote] = useState("");
  const [showMachine, setShowMachine] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const status = plan?.status || "empty";
  const hasText = Boolean((plan?.human_text || "").trim());

  async function call(path: string, body?: Record<string, unknown>) {
    setBusy(true);
    setErr(null);
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 180_000);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/hh-search-plan/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      onPlanChange(data.plan, data.criteria);
      if (path === "revise") setNote("");
      return data;
    } catch (e) {
      // Server may have finished anyway — pull latest plan.
      try {
        const sync = await apiFetch(`/api/v1/vacancies/${vacancyId}/hh-search-plan`, {
          cache: "no-store",
        });
        if (sync.ok) {
          const latest = await sync.json();
          if (latest?.plan) onPlanChange(latest.plan);
        }
      } catch {
        /* ignore */
      }
      if (e instanceof DOMException && e.name === "AbortError") {
        setErr(
          "Генерация плана заняла слишком долго (ИИ). Обновите страницу — план мог уже сохраниться на сервере.",
        );
      } else if (e instanceof TypeError) {
        setErr(
          "Нет ответа от API (Failed to fetch). Часто из‑за долгой генерации ИИ или если API перезапускался. Обновите страницу и повторите.",
        );
      } else {
        setErr(e instanceof Error ? e.message : "Ошибка");
      }
      return null;
    } finally {
      window.clearTimeout(timer);
      setBusy(false);
    }
  }

  async function approveAndSearch() {
    const data = await call("approve");
    if (!data) return;
    // Не ждать React setState — иначе onStart видит старый status и отменяет запуск.
    onStartSearch({
      fromApprove: true,
      criteria: {
        ...(data.criteria || {}),
        max_search: maxSearch,
        max_evaluate: maxEvaluate,
      },
    });
  }

  const clampSearch = (n: number) => Math.max(1, Math.min(50, n || 20));
  const clampEval = (n: number) => Math.max(0, Math.min(50, n || 0));

  return (
    <div className="hh-plan">
      <p className="muted">
        1) Подготовьте план · 2) при необходимости поправьте текстом · 3) задайте лимиты · 4) утвердите
        и запустите поиск.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      <p className="hh-micro">
        Статус: <strong>{STATUS_RU[status] || status}</strong>
        {plan?.version ? ` · v${plan.version}` : ""}
        {plan?.sources?.length ? ` · источники: ${plan.sources.join(", ")}` : ""}
      </p>
      {status === "stale" ? (
        <p className="warn">План устарел после правок профиля — перегенерируйте.</p>
      ) : null}

      <div className="hh-footer-actions" style={{ justifyContent: "flex-start", marginBottom: "0.75rem" }}>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy}
          onClick={() => call("generate")}
        >
          {busy ? "…" : hasText ? "Перегенерировать план" : "Подготовить план поиска"}
        </button>
        {busy ? (
          <span className="muted hh-micro">ИИ готовит план — обычно 30–90 сек, не закрывайте вкладку…</span>
        ) : null}
      </div>

      {hasText ? (
        <section className="card-edit hh-plan-card">
          <div className="hh-plan-text">{plan?.human_text}</div>
          {plan?.notes?.length ? (
            <details className="hh-micro" style={{ marginTop: "0.75rem" }}>
              <summary>История корректировок ({plan.notes.length})</summary>
              <ul>
                {plan.notes.map((n, i) => (
                  <li key={`${i}-${n.slice(0, 24)}`}>{n}</li>
                ))}
              </ul>
            </details>
          ) : null}
          <button
            type="button"
            className="chip"
            style={{ marginTop: "0.65rem" }}
            onClick={() => setShowMachine((v) => !v)}
          >
            {showMachine ? "Скрыть тех. параметры" : "Тех. параметры (под капотом)"}
          </button>
          {showMachine ? (
            <pre className="hh-plan-machine">{JSON.stringify(plan?.machine || {}, null, 2)}</pre>
          ) : null}
          {(plan?.machine as { keywords?: string; keywords_and?: string } | undefined)?.keywords ? (
            <p className="hh-micro muted" style={{ marginTop: "0.5rem" }}>
              HH-логика: ИЛИ —{" "}
              {(String((plan?.machine as { keywords?: string }).keywords || "") || "")
                .split("\n")
                .filter(Boolean)
                .join(" · ") || "—"}
              {(plan?.machine as { keywords_and?: string })?.keywords_and ? (
                <>
                  {" "}
                  · И —{" "}
                  {String((plan?.machine as { keywords_and?: string }).keywords_and)
                    .split("\n")
                    .filter(Boolean)
                    .join(" · ")}
                </>
              ) : null}
            </p>
          ) : null}
        </section>
      ) : null}

      <div className="hh-funnel-grid" style={{ marginTop: "0.85rem", marginBottom: "0.5rem" }}>
        <label className="hh-field">
          <span className="hh-label">Сколько найти (резюме с HH)</span>
          <input
            type="number"
            min={1}
            max={50}
            value={maxSearch}
            disabled={busy || searchBusy}
            onChange={(e) => {
              const max_search = clampSearch(Number(e.target.value));
              onLimitsChange({
                max_search,
                max_evaluate: Math.min(maxEvaluate, max_search),
              });
            }}
          />
        </label>
        <label className="hh-field">
          <span className="hh-label">Сколько оценить ИИ</span>
          <input
            type="number"
            min={0}
            max={50}
            value={maxEvaluate}
            disabled={busy || searchBusy}
            onChange={(e) => {
              const max_evaluate = clampEval(Number(e.target.value));
              onLimitsChange({
                max_search: maxSearch,
                max_evaluate: Math.min(max_evaluate, maxSearch),
              });
            }}
          />
        </label>
      </div>
      <p className="hh-micro muted">
        Итог на вкладке «Результаты»: до {maxEvaluate} оценённых (+ остальные найденные без оценки,
        если нашли больше). Лимит HH ~50 просмотров/сутки.
      </p>

      {hasText ? (
        <>
          <label className="hh-field">
            <span className="hh-label">Корректировки (необязательно)</span>
            <textarea
              rows={3}
              value={note}
              disabled={busy}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Например: джобхоппинг не критичен; расширить географию до ЛО"
            />
          </label>
          <div className="hh-footer-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="chip"
              disabled={busy || !note.trim()}
              onClick={() => call("revise", { note })}
            >
              Обновить план
            </button>
            <button
              type="button"
              className="chip chip-active"
              disabled={busy || searchBusy}
              onClick={approveAndSearch}
            >
              {searchBusy ? "Поиск…" : "Утвердить и начать поиск"}
            </button>
            {status === "approved" ? (
              <button
                type="button"
                className="chip"
                disabled={busy || searchBusy}
                onClick={() => onStartSearch()}
              >
                Искать ещё тем же планом
              </button>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
