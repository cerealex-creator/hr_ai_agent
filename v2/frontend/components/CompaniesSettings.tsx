"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { CommunicationChannelsPanel } from "@/components/CommunicationChannelsPanel";
import { InfoTip } from "@/components/InfoTip";
import { TestChatSettings } from "@/components/TestChatSettings";
import { apiFetch } from "@/lib/api";
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
    const res = await apiFetch(`/api/v1/companies`, { cache: "no-store" });
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
        <h2>
          Создать компанию{" "}
          <InfoTip text="Сначала создайте компанию (заказчика). Потом при необходимости — подразделения, куда ищете сотрудников. Если подразделения нет, все вакансии привязываются к самой компании. Можно создать несколько компаний." />
        </h2>
        <p className="muted hh-micro">
          Шаг 1: название компании. Подразделения добавляются уже на странице компании. Режим чатов
          можно сменить позже.
        </p>
        {err ? <p className="warn">{err}</p> : null}
        {msg ? <p className="ok">{msg}</p> : null}
        <div className="hh-inline-pair" style={{ marginTop: "0.75rem" }}>
          <div className="hh-field">
            <label className="hh-label">
              Название{" "}
              <InfoTip text="Как будет отображаться заказчик в списках вакансий и сайдбаре. Пример: ООО «Компания»." />
            </label>
            <input
              value={newCompanyName}
              onChange={(e) => setNewCompanyName(e.target.value)}
              disabled={busy}
              placeholder="ООО «Компания», ИП Иванов…"
            />
          </div>
          <div className="hh-field">
            <label className="hh-label">
              Как устроены чаты?{" "}
              <InfoTip text="Один чат — все вакансии компании в одной Telegram-группе. По подразделениям — у каждого отдела свой чат (удобно, когда в компании несколько направлений)." />
            </label>
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
              const res = await apiFetch(`/api/v1/companies`, {
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
              setMsg("Компания создана — откройте её, чтобы добавить подразделения и чат");
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
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.5rem" }}>
          Существующие компании{" "}
          <InfoTip text="Откройте компанию, чтобы задать чат, клиентскую зону и подразделения (если нужны)." />
        </h2>
        <p className="muted hh-micro" style={{ marginTop: 0 }}>
          Можно несколько компаний. Внутри каждой — сколько угодно подразделений.
        </p>
        {!items.length ? <p className="muted">Пока нет компаний — создайте первую выше.</p> : null}
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

      <CommunicationChannelsPanel />

      <section id="test-chat" className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>
          Настройка тестового чата{" "}
          <InfoTip text="Отдельный чат, чтобы проверить бота и сценарии без риска написать реальному заказчику. Не показывается в обычном списке компаний слева." />
        </h2>
        <TestChatSettings embedded />
      </section>
    </>
  );
}
