"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type Tmpl = {
  id: string;
  title: string;
  legacy_key: string;
  client_id: number | null;
  has_profile: boolean;
  has_questions: boolean;
};

export default function TemplatesPage() {
  const [items, setItems] = useState<Tmpl[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${getApiBase()}/api/v1/vacancy-templates`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setItems(d.items || []))
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, []);

  const createFrom = async (id: string, title: string) => {
    setBusyId(id);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/vacancy-templates/${id}/create-vacancy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error(await res.text());
      const vac = await res.json();
      setMsg(`Создана вакансия #${vac.id}`);
      window.location.href = `/vacancies/${vac.id}?view=docs`;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка создания");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell activePath="/templates">
      <h1 className="page-title">Шаблоны вакансий</h1>
      <p className="muted">Импортированные шаблоны → новая вакансия с документами.</p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Профиль</th>
            <th>Опросник</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.id}>
              <td>{t.title}</td>
              <td>{t.has_profile ? "да" : "—"}</td>
              <td>{t.has_questions ? "да" : "—"}</td>
              <td>
                <button
                  type="button"
                  className="chip chip-active"
                  disabled={busyId === t.id}
                  onClick={() => void createFrom(t.id, t.title)}
                >
                  {busyId === t.id ? "…" : "Создать вакансию"}
                </button>
              </td>
            </tr>
          ))}
          {!items.length && !err ? (
            <tr>
              <td colSpan={4}>Шаблонов нет — импортируйте legacy vacancy_templates.json</td>
            </tr>
          ) : null}
        </tbody>
      </table>
      <p style={{ marginTop: "1rem" }}>
        <Link className="back" href="/vacancies">
          ← К вакансиям
        </Link>
      </p>
    </AppShell>
  );
}
