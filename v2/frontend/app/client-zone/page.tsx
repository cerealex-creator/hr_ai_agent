"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ClientZoneLink } from "@/components/ClientZoneLink";
import { InfoTip } from "@/components/InfoTip";
import { RecruitingShell } from "@/components/RecruitingShell";
import { apiFetch } from "@/lib/api";
import { type CompanyNode } from "@/lib/companies";

export default function ClientZoneHubPage() {
  const [items, setItems] = useState<CompanyNode[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/v1/companies`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    setItems(Array.isArray(data.items) ? data.items : []);
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false));
  }, [load]);

  return (
    <RecruitingShell activePath="/client-zone" title="Клиентская зона">
      <p className="muted rec-page-lead">
        Отдельная страница для заказчика: он видит кандидатов на оценке и может выбрать «Встреча»,
        «Подумать» или «Отказ» — без входа в HR-помогатор.
      </p>

      <div className="rec-card">
        <h2 className="rec-card-title">
          Как это работает{" "}
          <InfoTip text="У компании и у каждого подразделения своя ссылка. Кандидат появляется в зоне того подразделения (или компании), к которому привязана вакансия." />
        </h2>
        <ol className="cz-hub-steps">
          <li>
            В{" "}
            <Link href="/settings/companies">настройках компании</Link> создайте ссылку клиентской
            зоны для компании или нужного подразделения (или ссылка появится при первой отправке
            кандидата).
          </li>
          <li>Отправьте ссылку заказчику — полный адрес с доменом, не только <code>/c/…</code>.</li>
          <li>
            В карточке кандидата на вкладке «Заказчик» нажмите «Отправить заказчику» — кандидат
            попадёт в список по ссылке.
          </li>
          <li>
            Ссылка вида <code>/i/…</code> — это выжимка собеседования для заказчика, это другой
            раздел.
          </li>
        </ol>
      </div>

      {err ? <p className="warn">{err}</p> : null}
      {loading ? <p className="muted">Загрузка компаний…</p> : null}

      {!loading && items.length === 0 ? (
        <div className="rec-card">
          <p className="muted" style={{ margin: 0 }}>
            Компаний пока нет.{" "}
            <Link href="/settings/companies">Создайте компанию</Link>, затем вернитесь сюда за
            ссылкой.
          </p>
        </div>
      ) : null}

      {items.map((co) => {
        const companyPath = co.client_zone_token ? `/c/${co.client_zone_token}` : null;
        return (
          <div key={co.id} className="rec-card">
            <h2 className="rec-card-title">{co.name}</h2>
            <ClientZoneLink
              path={companyPath}
              label={
                co.departments.length
                  ? "Ссылка компании (вакансии без подразделения)"
                  : "Ссылка для заказчика"
              }
              compact={Boolean(companyPath)}
            />
            {co.departments.map((d) => {
              const deptPath = d.client_zone_token ? `/c/${d.client_zone_token}` : null;
              return (
                <div key={d.id} className="cz-dept-zone">
                  <ClientZoneLink
                    path={deptPath}
                    label={`Подразделение «${d.name}»`}
                    compact={Boolean(deptPath)}
                  />
                </div>
              );
            })}
            <p style={{ marginTop: "0.75rem", marginBottom: 0 }}>
              <Link href={`/settings/companies/${co.id}`}>Настройки компании →</Link>
            </p>
          </div>
        );
      })}
    </RecruitingShell>
  );
}
