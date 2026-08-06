"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Row = {
  vacancy_id: number;
  title: string;
  active: boolean;
  client_name: string | null;
  candidate_id: string | null;
  candidate_name: string | null;
  start_date: string;
  months: number;
  days_remaining: number | null;
  countdown: string;
  is_warranty_search: boolean;
};

export function WarrantyRegistry() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch(`/api/v1/warranty/registry`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setRows)
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, []);

  return (
    <section className="card-edit" style={{ marginTop: "1.5rem" }}>
      <h2>Реестр гарантий</h2>
      {err ? <p className="warn">{err}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Вакансия</th>
            <th>Клиент</th>
            <th>Кандидат</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.vacancy_id}>
              <td>
                <Link href={`/vacancies/${r.vacancy_id}`}>{r.title}</Link>
                {r.is_warranty_search ? (
                  <span className="muted"> · гарантийный поиск</span>
                ) : null}
              </td>
              <td>{r.client_name || "—"}</td>
              <td>
                {r.candidate_id ? (
                  <Link href={`/candidates/${r.candidate_id}`}>
                    {r.candidate_name || r.candidate_id}
                  </Link>
                ) : (
                  "—"
                )}
              </td>
              <td>{r.countdown || "—"}</td>
            </tr>
          ))}
          {!rows.length && !err ? (
            <tr>
              <td colSpan={4}>Нет активных гарантий</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </section>
  );
}
