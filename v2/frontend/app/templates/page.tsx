"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RecruitingShell } from "@/components/RecruitingShell";
import { apiFetch } from "@/lib/api";

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
    apiFetch(`/api/v1/vacancy-templates`, { cache: "no-store" })
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
      const res = await apiFetch(`/api/v1/vacancy-templates/${id}/create-vacancy`, {
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
    <RecruitingShell activePath="/templates" title="Шаблоны вакансий">
      <div className="rec-card">
        <p className="muted" style={{ marginTop: 0 }}>
          Импортированные шаблоны → новая вакансия с готовыми документами (профиль, опросник и т.д.).
        </p>
        {err ? <p className="warn">{err}</p> : null}
        {msg ? <p className="ok">{msg}</p> : null}

        <div className="rec-table-wrap">
          <table className="rec-table">
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
                  <td colSpan={4} className="muted">
                    Шаблонов пока нет. Импортируйте legacy <code>vacancy_templates.json</code> или
                    создайте вакансию вручную в разделе{" "}
                    <Link href="/vacancies">Вакансии</Link>.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </RecruitingShell>
  );
}
