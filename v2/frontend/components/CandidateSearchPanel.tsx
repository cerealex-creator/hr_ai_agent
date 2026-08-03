"use client";

import Link from "next/link";
import { useState } from "react";
import { getApiBase, type CandidateListItem } from "@/lib/api";
import { clientStatusLabel, hrStageLabel } from "@/lib/labels";

type Hit = CandidateListItem & { match_in?: string; score?: number };

export function CandidateSearchPanel() {
  const [q, setQ] = useState("");
  const [includeTest, setIncludeTest] = useState(false);
  const [rows, setRows] = useState<Hit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const search = async () => {
    if (q.trim().length < 2) {
      setErr("Введите минимум 2 символа");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const qs = new URLSearchParams({ q: q.trim(), limit: "40" });
      if (includeTest) qs.set("include_test", "true");
      const res = await fetch(`${getApiBase()}/api/v1/candidates/search?${qs}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRows((await res.json()) as Hit[]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка поиска");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-edit" style={{ marginBottom: "1.25rem" }}>
      <h2>Поиск</h2>
      <div className="hh-inline-pair">
        <div className="hh-field" style={{ flex: 1 }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            disabled={busy}
            placeholder="ФИО, телефон, текст резюме…"
            onKeyDown={(e) => {
              if (e.key === "Enter") void search();
            }}
          />
        </div>
        <button type="button" className="chip chip-active" disabled={busy} onClick={search}>
          Найти
        </button>
      </div>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={includeTest}
          onChange={(e) => setIncludeTest(e.target.checked)}
          disabled={busy}
        />
        Включать тестовые вакансии
      </label>
      {err ? <p className="warn">{err}</p> : null}
      {rows ? (
        <table style={{ marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th>Имя</th>
              <th>Вакансия</th>
              <th>Этап</th>
              <th>Где нашли</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link href={`/candidates/${c.id}`}>{c.name || "—"}</Link>
                </td>
                <td>{c.vacancy_title || `#${c.vacancy_id}`}</td>
                <td>
                  {hrStageLabel(c.hr_stage)} · {clientStatusLabel(c.client_status)}
                </td>
                <td>{c.match_in || "—"}</td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={4}>Ничего не найдено</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
