import Link from "next/link";
import { DashboardQueue } from "@/components/DashboardQueue";
import { RecruitingShell } from "@/components/RecruitingShell";
import { apiGet } from "@/lib/api";

type Dashboard = {
  kpis: { key: string; label: string; value: number }[];
  attention: {
    id: string;
    name: string;
    vacancy_id: number;
    vacancy_title?: string | null;
    reason?: string | null;
    photo_url?: string | null;
    gender?: string | null;
  }[];
};

function kpiValue(dash: Dashboard, key: string): number {
  return dash.kpis.find((k) => k.key === key)?.value ?? 0;
}

const KPI_CARDS: {
  key: string;
  label: string;
  tone: string;
  href?: string;
}[] = [
  { key: "attention", label: "Требуют внимания", tone: "attention", href: "/candidates?preset=attention" },
  { key: "meetings_today", label: "Встречи сегодня", tone: "blue" },
  { key: "waiting_client", label: "Ждут заказчика", tone: "orange", href: "/candidates?hr_stage=client_review" },
];

export default async function DashboardPage() {
  let dash: Dashboard | null = null;
  let error: string | null = null;

  try {
    dash = await apiGet<Dashboard>(
      "/api/v1/stats/dashboard?mode=operational&period=week&active_vacancies_only=true",
    );
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  return (
    <RecruitingShell activePath="/dashboard" title="Рабочий стол">
      {error ? <p className="warn">{error}</p> : null}

      {dash ? (
        <>
          <div className="rec-dash-kpis">
            {KPI_CARDS.map(({ key, label, tone, href }) => {
              const val = kpiValue(dash!, key);
              const inner = (
                <>
                  <span className="rec-dash-kpi-label">{label}</span>
                  <span className={`rec-dash-kpi-val rec-dash-kpi-${tone}`}>{val}</span>
                </>
              );
              return href ? (
                <Link key={key} href={href} className={`rec-dash-kpi rec-dash-kpi-link rec-dash-kpi-${tone}`}>
                  {inner}
                </Link>
              ) : (
                <div key={key} className={`rec-dash-kpi rec-dash-kpi-${tone}`}>
                  {inner}
                </div>
              );
            })}
          </div>

          <section className="rec-dash-section">
            <div className="rec-dash-section-head">
              <h2 className="rec-dash-section-title">Очередь «Сегодня»</h2>
              <Link href="/candidates?preset=attention" className="rec-dash-section-link">
                Все внимание →
              </Link>
            </div>
            <DashboardQueue items={dash.attention} />
          </section>
        </>
      ) : null}
    </RecruitingShell>
  );
}
