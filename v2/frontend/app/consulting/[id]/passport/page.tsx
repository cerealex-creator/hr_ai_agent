"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  addConsultingPerson,
  deleteConsultingPerson,
  getConsultingProject,
  patchConsultingMilestone,
  patchConsultingProject,
  patchConsultingUnit,
  type ConsultingProject,
} from "@/lib/consulting";

export default function ConsultingPassportPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [project, setProject] = useState<ConsultingProject | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");

  function reload() {
    return getConsultingProject(id).then(setProject);
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  if (!project) {
    return (
      <ConsultingShell projectId={id} active="passport" title="Паспорт">
        <p className="muted">{err || "Загрузка…"}</p>
      </ConsultingShell>
    );
  }

  const directorates = project.units.filter((u) => u.kind === "directorate");
  const bes = project.units.filter((u) => u.kind === "be");
  const uk = project.units.find((u) => u.kind === "uk");

  return (
    <ConsultingShell projectId={id} active="passport" title="Паспорт">
      {err ? <p className="consult-err">{err}</p> : null}

      <label className="consult-label">
        Заказчик
        <input
          defaultValue={project.customer_name}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== project.customer_name) {
              patchConsultingProject(id, { customer_name: v }).then(setProject).catch((er) => setErr(String(er)));
            }
          }}
        />
      </label>
      <label className="consult-label">
        Название проекта
        <input
          defaultValue={project.title}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== project.title) {
              patchConsultingProject(id, { title: v }).then(setProject).catch((er) => setErr(String(er)));
            }
          }}
        />
      </label>

      <h2 className="consult-h2">Контрольные точки</h2>
      <p className="muted">Даты можно менять. Шаблон 3 / 10 / 15 / 20 дней — только старт.</p>
      <ul className="consult-list">
        {project.milestones.map((m) => (
          <li key={m.id}>
            <span>{m.title}</span>
            <input
              type="date"
              defaultValue={m.due_on || ""}
              onBlur={(e) => {
                if (e.target.value && e.target.value !== m.due_on) {
                  patchConsultingMilestone(id, m.id, e.target.value).catch((er) => setErr(String(er)));
                }
              }}
            />
          </li>
        ))}
      </ul>

      <h2 className="consult-h2">Управляющая компания</h2>
      {uk ? <p>{uk.name}</p> : null}
      <h3 className="consult-h3">Дирекции</h3>
      {directorates.map((u) => (
        <input
          key={u.id}
          className="consult-inline"
          defaultValue={u.name}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== u.name) patchConsultingUnit(id, u.id, v).then(() => reload()).catch((er) => setErr(String(er)));
          }}
        />
      ))}
      <h3 className="consult-h3">Бизнес-единицы</h3>
      {bes.map((u) => (
        <input
          key={u.id}
          className="consult-inline"
          defaultValue={u.name}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== u.name) patchConsultingUnit(id, u.id, v).then(() => reload()).catch((er) => setErr(String(er)));
          }}
        />
      ))}

      <h2 className="consult-h2">Люди</h2>
      <form
        className="consult-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          addConsultingPerson(id, { full_name: name, title, survey: true })
            .then(() => {
              setName("");
              setTitle("");
              return reload();
            })
            .catch((er) => setErr(er instanceof Error ? er.message : "Ошибка"));
        }}
      >
        <input placeholder="ФИО" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Должность" value={title} onChange={(e) => setTitle(e.target.value)} />
        <button type="submit" className="mgmt-btn">
          Добавить
        </button>
      </form>
      <ul className="consult-list">
        {project.people.map((p) => (
          <li key={p.id}>
            <span>
              {p.full_name}
              {p.title ? ` — ${p.title}` : ""}
            </span>
            <button
              type="button"
              className="mgmt-btn-link"
              onClick={() => deleteConsultingPerson(id, p.id).then(() => reload()).catch((er) => setErr(String(er)))}
            >
              Убрать
            </button>
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
