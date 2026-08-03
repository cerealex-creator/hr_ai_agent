"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { getApiBase } from "@/lib/api";
import {
  companyModeLabel,
  detailMessage,
  type CompanyNode,
} from "@/lib/companies";

export function CompaniesSettings() {
  const router = useRouter();
  const [items, setItems] = useState<CompanyNode[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [newCompanyName, setNewCompanyName] = useState("");
  const [newCompanyMode, setNewCompanyMode] = useState<"company" | "departments">("company");

  const load = useCallback(async () => {
    const res = await fetch(`${getApiBase()}/api/v1/companies`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    setItems(data.items || []);
  }, []);

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, [load]);

  return (
    <>
      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Создать клиента / компанию</h2>
        <p className="muted hh-micro">
          Новый заказчик. Режим чатов можно сменить позже на странице компании.
        </p>
        {err ? <p className="warn">{err}</p> : null}
        {msg ? <p className="ok">{msg}</p> : null}
        <div className="hh-inline-pair" style={{ marginTop: "0.75rem" }}>
          <div className="hh-field">
            <label className="hh-label">Название</label>
            <input
              value={newCompanyName}
              onChange={(e) => setNewCompanyName(e.target.value)}
              disabled={busy}
              placeholder="YourBox, Пульс Групп…"
            />
          </div>
          <div className="hh-field">
            <label className="hh-label">Как устроены чаты?</label>
            <select
              value={newCompanyMode}
              onChange={(e) => setNewCompanyMode(e.target.value as "company" | "departments")}
              disabled={busy}
            >
              <option value="company">Один чат на всю компанию</option>
              <option value="departments">Отдельные чаты по подразделениям</option>
            </select>
          </div>
        </div>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !newCompanyName.trim()}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            setMsg(null);
            try {
              const res = await fetch(`${getApiBase()}/api/v1/companies`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  name: newCompanyName.trim(),
                  chat_mode: newCompanyMode,
                }),
              });
              const data = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
              setNewCompanyName("");
              setMsg("Компания создана");
              await load();
              if (data?.id != null) {
                router.push(`/settings/companies/${data.id}`);
              }
            } catch (e) {
              setErr(e instanceof Error ? e.message : "Ошибка");
            } finally {
              setBusy(false);
            }
          }}
        >
          Создать и открыть
        </button>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>Существующие компании</h2>
        <p className="muted hh-micro" style={{ marginTop: 0 }}>
          Свёрнуто. Полные настройки — на странице компании.
        </p>
        {!items.length ? <p className="muted">Пока нет компаний.</p> : null}
        {items.map((co) => {
          const deptCount = co.departments?.length || 0;
          const chatsBound =
            co.chat_mode === "departments"
              ? co.departments.filter((d) => d.channel).length
              : co.channel
                ? 1
                : 0;
          const hint =
            co.chat_mode === "departments"
              ? `${companyModeLabel(co.chat_mode)} · ${deptCount} подр. · чатов ${chatsBound}`
              : `${companyModeLabel(co.chat_mode)}${co.channel ? ` · ${co.channel.name || co.channel.external_id}` : " · чат не задан"}`;
          return (
            <CollapsibleCard key={co.id} title={co.name} hint={hint} defaultOpen={false}>
              <p className="muted hh-micro">
                #{co.id}
                {co.chat_mode === "departments" && deptCount
                  ? ` · ${co.departments.map((d) => d.name).join(", ")}`
                  : null}
              </p>
              <Link className="chip chip-active" href={`/settings/companies/${co.id}`}>
                Открыть настройки компании
              </Link>
            </CollapsibleCard>
          );
        })}
      </section>
    </>
  );
}
