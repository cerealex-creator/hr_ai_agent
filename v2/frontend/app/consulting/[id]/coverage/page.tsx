"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import { getConsultingCoverage, type ConsultingCoverage } from "@/lib/consulting";

export default function ConsultingCoveragePage() {
  const params = useParams();
  const id = String(params.id || "");
  const [data, setData] = useState<ConsultingCoverage | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getConsultingCoverage(id).then(setData).catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="coverage" title="Белые пятна">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">
        Каркас лежит в скилле, не в документах компании. Клетка закрыта только годным следом: рабочий документ с цитатой
        или разобранным текстом, встреча с расшифровкой в этой папке, подтверждённая строка реестра. Слово в поиске клетку
        не закрывает.
      </p>
      {!data ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <p>
            Нет данных: {data.open} из {data.total}.
          </p>
          <ul className="consult-list">
            {data.items.map((cell) => (
              <li key={cell.code}>
                <span>{cell.title}</span>
                <em>{cell.closed ? "есть след" : "нет данных"}</em>
              </li>
            ))}
          </ul>
        </>
      )}
    </ConsultingShell>
  );
}
