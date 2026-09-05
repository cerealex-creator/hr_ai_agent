"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import { getConsultingHub, publishConsultingShowcase, type ConsultingHub } from "@/lib/consulting";

export default function ConsultingHubPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [hub, setHub] = useState<ConsultingHub | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getConsultingHub(id).then(setHub).catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="hub" title={hub?.project.title || "Консалтинг"}>
      {err ? <p className="consult-err">{err}</p> : null}
      {!hub ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <HubBody
          hub={hub}
          id={id}
          link={link}
          onPublish={() =>
            publishConsultingShowcase(id)
              .then((s) => {
                setLink(s.url);
                return getConsultingHub(id).then(setHub);
              })
              .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))
          }
        />
      )}
    </ConsultingShell>
  );
}

function HubBody({
  hub,
  id,
  link,
  onPublish,
}: {
  hub: ConsultingHub;
  id: string;
  link: string | null;
  onPublish: () => void;
}) {
  const { collect, attention, output, project } = hub;
  const shown = link || (project.showcase_token ? `/consulting/p/${project.showcase_token}` : null);
  return (
    <div className="consult-hub">
      <p className="muted">
        {project.customer_name}. Срок до {project.due_on || "—"}. План:{" "}
        {project.plan_status === "approved" ? "утверждён" : "черновик"}.
      </p>

      <section className="consult-band">
        <h2>Сбор</h2>
        <div className="consult-metrics">
          <Metric n={collect.sources} label="материалов" />
          <Metric n={collect.pending_review} label="на разборе" />
          <Metric n={collect.people} label="в паспорте" />
        </div>
        <div className="consult-actions">
          <Link href={`/consulting/${id}/folders`} className="mgmt-btn">
            Загрузить материалы
          </Link>
          <Link href={`/consulting/${id}/passport`} className="consult-btn-secondary">
            Люди и структура
          </Link>
          <Link href={`/consulting/${id}/meetings`} className="consult-btn-secondary">
            Встречи
          </Link>
          <Link href={`/consulting/${id}/survey`} className="consult-btn-secondary">
            Опрос{collect.surveys_pending ? ` (${collect.surveys_pending})` : ""}
          </Link>
          <Link href={`/consulting/${id}/megamaid`} className="consult-btn-secondary">
            Мегамейд
          </Link>
          <Link href={`/consulting/${id}/etalon`} className="consult-btn-secondary">
            Эталон
          </Link>
        </div>
      </section>

      <section className="consult-band">
        <h2>Внимание</h2>
        <ul className="consult-attention">
          <li>Пустых папок (уровень 2+): {attention.empty_folders}</li>
          <li>Рекомендаций ждут клика: {attention.recommended}</li>
          <li>Оспорено заказчиком: {attention.disputed}</li>
          <li>
            <Link href={`/consulting/${id}/contradictions`}>Открытых противоречий: {attention.contradictions}</Link>
          </li>
          <li>
            <Link href={`/consulting/${id}/coverage`}>Белых пятен (нет годного следа): {attention.white_spots}</Link>
          </li>
        </ul>
      </section>

      <section className="consult-band">
        <h2>Результат</h2>
        <p>
          Чек-лист плана: {output.plan_done} из {output.plan_total}. Формы результата ещё не загружены — клетки итога не
          заполняем.
        </p>
        <div className="consult-actions">
          <Link href={`/consulting/${id}/plan`} className="consult-btn-secondary">
            Открыть план
          </Link>
          <Link href={`/consulting/${id}/registry`} className="consult-btn-secondary">
            Реестр
          </Link>
          <button type="button" className="mgmt-btn" onClick={onPublish}>
            {output.showcase_ready ? "Обновить витрину" : "Опубликовать витрину"}
          </button>
        </div>
        {shown ? (
          <p className="muted">
            Ссылка для заказчика: <a href={shown}>{shown}</a>
          </p>
        ) : null}
        <ul className="consult-results">
          {(project.result_labels || []).map((r) => (
            <li key={r.code}>
              <span>{r.title}</span>
              <em>ждёт форму</em>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Metric({ n, label }: { n: number; label: string }) {
  return (
    <div className="consult-metric">
      <strong>{n}</strong>
      <span>{label}</span>
    </div>
  );
}
