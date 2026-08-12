"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

const MONTHS_BACK = [
  { id: "m1", label: "1 месяц" },
  { id: "m2", label: "2 месяца" },
  { id: "m3", label: "3 месяца" },
  { id: "m6", label: "6 месяцев" },
  { id: "m12", label: "12 месяцев" },
] as const;

type Chip = { id: string; label: string };

type Props = {
  chips: Chip[];
  period: string;
  /** Precomputed hrefs for chip + months period ids (serializable). */
  hrefByPeriod: Record<string, string>;
};

export function StatsPeriodControls({ chips, period, hrefByPeriod }: Props) {
  const router = useRouter();
  const monthsSelected = MONTHS_BACK.some((m) => m.id === period);

  return (
    <div className="filter-row stats-period-row">
      <span className="filter-label">Период</span>
      <div className="chip-row">
        {chips.map((p) => (
          <Link
            key={p.id}
            href={hrefByPeriod[p.id] || "/stats"}
            className={!monthsSelected && period === p.id ? "chip chip-active" : "chip"}
          >
            {p.label}
          </Link>
        ))}
      </div>
      <label className="stats-months-select">
        <span className="muted">Ещё</span>
        <select
          value={monthsSelected ? period : ""}
          aria-label="Период в месяцах"
          onChange={(e) => {
            const v = e.target.value;
            if (!v) return;
            router.push(hrefByPeriod[v] || "/stats");
          }}
        >
          <option value="">N месяцев…</option>
          {MONTHS_BACK.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
