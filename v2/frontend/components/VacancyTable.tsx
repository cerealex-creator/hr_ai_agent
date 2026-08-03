import Link from "next/link";
import {
  outcomeLabel,
  type VacancyListItem,
} from "@/lib/api";
import { daysBetween, daysLabel, formatDateRu } from "@/lib/dates";

type Props = {
  vacancies: VacancyListItem[];
  mode: "active" | "archive";
};

export function VacancyTable({ vacancies, mode }: Props) {
  const isArchive = mode === "archive";

  return (
    <table>
      <thead>
        <tr>
          <th>Название</th>
          <th>Клиент</th>
          <th>Кандидаты</th>
          {isArchive ? (
            <>
              <th>Период</th>
              <th>Исход</th>
            </>
          ) : (
            <th>В работе</th>
          )}
        </tr>
      </thead>
      <tbody>
        {vacancies.map((v) => {
          const days = daysBetween(v.created_at, isArchive ? v.closed_at : null);
          return (
            <tr key={v.id}>
              <td>
                <Link href={`/vacancies/${v.id}`}>{v.title}</Link>
                <div className="row-meta">#{v.id}</div>
              </td>
              <td>{v.client_name || "—"}</td>
              <td>{v.candidates_count}</td>
              {isArchive ? (
                <>
                  <td>
                    <div>
                      {formatDateRu(v.created_at)} — {formatDateRu(v.closed_at)}
                    </div>
                    <div className="row-meta">{daysLabel(days)}</div>
                  </td>
                  <td>
                    <span className={`outcome outcome-${v.outcome || "none"}`}>
                      {outcomeLabel(v.outcome)}
                    </span>
                  </td>
                </>
              ) : (
                <td>
                  <div>с {formatDateRu(v.created_at)}</div>
                  <div className="row-meta">{daysLabel(days)}</div>
                </td>
              )}
            </tr>
          );
        })}
        {!vacancies.length ? (
          <tr>
            <td colSpan={isArchive ? 5 : 4}>
              {isArchive ? "Архив пуст" : "Нет вакансий в работе"}
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}
