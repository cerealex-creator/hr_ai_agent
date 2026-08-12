"use client";

import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { CandidateAvatar } from "@/components/CandidateAvatar";

/**
 * Визуальный макет раздела «Оффер» в карточке кандидата.
 * Не боевой функционал — только UI для согласования.
 */
export default function OfferSectionMockPage() {
  return (
    <RecruitingShell activePath="/candidates" title="Макет: Оффер">
      <p className="muted" style={{ marginTop: 0 }}>
        Макет раздела ·{" "}
        <Link href="/design-preview">к другим превью</Link>
      </p>

      <div className="rec-card cand-workspace-head">
        <div className="cand-workspace-main">
          <CandidateAvatar name="Анна Сергеевна Иванова" gender="female" size={56} />
          <div>
            <h1 className="cand-workspace-name" style={{ margin: 0, fontSize: "1.35rem" }}>
              Анна Сергеевна Иванова
            </h1>
            <p className="muted" style={{ margin: "0.25rem 0 0" }}>
              Графический дизайнер · Компания «Север» · этап Оффер
            </p>
          </div>
        </div>
      </div>

      <nav className="cand-tabs" aria-label="Разделы кандидата (макет)">
        {["Анкета", "Материалы", "Воронка", "Оффер", "Интервью", "Заказчик", "ИИ"].map((label) => (
          <span
            key={label}
            className={`cand-tab${label === "Оффер" ? " is-active" : ""}`}
            role="tab"
            aria-selected={label === "Оффер"}
          >
            {label}
          </span>
        ))}
      </nav>

      <div className="offer-mock-toolbar">
        <div className="offer-mock-toolbar-left">
          <span className="rec-badge rec-badge-teal">Черновик сохранён</span>
          <span className="muted hh-micro">Авто: ФИО, компания, должность · ИИ: обязанности</span>
        </div>
        <div className="offer-mock-toolbar-actions">
          <button type="button" className="chip" disabled>
            Заполнить из данных
          </button>
          <button type="button" className="chip" disabled>
            Дописать ИИ
          </button>
          <button type="button" className="chip chip-active" disabled>
            Скачать Word
          </button>
        </div>
      </div>

      <div className="offer-mock-grid">
        <section className="rec-card offer-mock-card">
          <h2 className="rec-card-title">Данные письма</h2>
          <p className="muted hh-micro" style={{ marginTop: "-0.25rem" }}>
            То, что уйдёт в шаблон Word. Зелёная метка — подставлено автоматически.
          </p>

          <div className="offer-mock-fields">
            <Field
              label="Обращение"
              hint="авто из пола"
              auto
              value="Уважаемая"
            />
            <Field label="Имя и отчество" hint="из ФИО" auto value="Анна Сергеевна" />
            <Field label="ФИО полностью" hint="подпись кандидата" auto value="Иванова Анна Сергеевна" />
            <Field label="Компания" auto value="Север" />
            <Field label="Должность" auto value="Графический дизайнер" />
            <Field
              label="Адрес офиса"
              hint="вручную / из компании"
              value="г. Москва, ул. Примерная, д. 10"
            />
            <Field
              label="Режим рабочего дня"
              hint="ИИ из профиля или вручную"
              multiline
              value="Пятидневная 40-часовая рабочая неделя с выходными в субботу и воскресенье, рабочее время с 09:00 до 18:00, перерыв для отдыха и питания 60 минут в день."
            />
            <div className="offer-mock-row2">
              <Field label="Дата выхода" hint="вручную" value="01.09.2026" />
              <Field label="Испытательный срок, мес." hint="не гарантия агентства" value="3" />
            </div>

            <div className="offer-mock-pay-block">
              <p className="offer-mock-pay-title">Оплата на испытательном сроке</p>
              <Field
                label="Оклад / формулировка"
                hint="база для письма"
                value="100 000 ₽ «на руки» (после вычета налогов)"
              />
              <Field
                label="Премирование на ИС"
                hint="опционально; может быть и на испытательном сроке"
                multiline
                value="Ежемесячная премия по результатам адаптации"
              />
              <Field
                label="Итоговая строка для письма (ИС)"
                hint="уходит в Word; правится вручную"
                multiline
                value="100 000 ₽ «на руки» (после вычета налогов) + ежемесячная премия по результатам адаптации"
              />
            </div>

            <div className="offer-mock-pay-block">
              <p className="offer-mock-pay-title">Оплата после испытательного срока</p>
              <Field
                label="Оклад / формулировка"
                hint="база для письма"
                value="100 000 ₽ «на руки» (после вычета налогов)"
              />
              <Field
                label="Премирование после ИС"
                hint="опционально"
                multiline
                value="Квартальная премия по итогам работы"
              />
              <Field
                label="Итоговая строка для письма (после ИС)"
                hint="уходит в Word; правится вручную"
                multiline
                value="100 000 ₽ «на руки» (после вычета налогов) + квартальная премия по итогам работы"
              />
            </div>

            <p className="muted hh-micro">
              Премия возможна и на ИС, и после. Пустое поле премии → в письме только оклад. Итоговые
              строки можно править целиком, если формулировка особая.
            </p>
            <Field label="ФИО руководителя" hint="подпись внизу" value="Петров И. А." />
          </div>
        </section>

        <div className="offer-mock-side">
          <section className="rec-card offer-mock-card">
            <h2 className="rec-card-title">Логотип компании</h2>
            <p className="muted hh-micro">
              Хранится у компании. В Word — в верхний колонтитул.
            </p>
            <div className="offer-mock-logo-box" aria-hidden>
              <span className="offer-mock-logo-mark">СЕВЕР</span>
            </div>
            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              <button type="button" className="chip" disabled>
                Загрузить лого
              </button>
              <button type="button" className="chip" disabled>
                Убрать
              </button>
            </div>
          </section>

          <section className="rec-card offer-mock-card">
            <h2 className="rec-card-title">Обязанности</h2>
            <p className="muted hh-micro">
              Список пунктов для письма. ИИ может набросать из профиля вакансии — вы правите.
            </p>
            <textarea
              className="offer-mock-textarea"
              rows={10}
              readOnly
              value={DUTIES}
            />
            <p className="muted hh-micro" style={{ marginTop: "0.5rem" }}>
              В шаблоне — один блок {"{{duties}}"}, не зашитый текст про WB.
            </p>
          </section>
        </div>
      </div>

      <section className="rec-card offer-mock-card">
        <h2 className="rec-card-title">Как это выглядит в письме (сжато)</h2>
        <div className="offer-mock-preview">
          <div className="offer-mock-preview-logo">СЕВЕР</div>
          <p>
            <strong>Уважаемая Анна Сергеевна!</strong>
          </p>
          <p>
            От лица <strong>Север</strong> сообщаем об успешном прохождении Вами собеседования на
            должность «<strong>Графический дизайнер</strong>»…
          </p>
          <p>
            Рабочее место: г. Москва, ул. Примерная, д. 10. Режим: пятидневная неделя 09:00–18:00…
          </p>
          <p>
            Выход с <strong>01.09.2026</strong>, испытательный срок — <strong>3</strong> мес.
          </p>
          <p>
            ЗП на ИС —{" "}
            <strong>
              100 000 ₽ «на руки» (после вычета налогов) + ежемесячная премия по результатам
              адаптации
            </strong>
            .
          </p>
          <p>
            После ИС —{" "}
            <strong>
              100 000 ₽ «на руки» (после вычета налогов) + квартальная премия по итогам работы
            </strong>
            .
          </p>
          <p className="muted hh-micro" style={{ marginBottom: 0 }}>
            Дальше — обязанности и блоки подписей из вашего шаблона без изменения структуры.
          </p>
        </div>
      </section>
    </RecruitingShell>
  );
}

const DUTIES = `• Оформление присутствия на маркетплейсах (WB): бренд-зона, рич-контент, баннеры
• Рекламные и промо-креативы: наружка, референсы ТВ, полиграфия
• Визуальный контент: техфото, ретушь, базовый монтаж, ИИ-генерации
• Поддержка брендинга и айдентики
• Кросс-функциональное взаимодействие со смежными отделами`;

function Field({
  label,
  value,
  hint,
  auto,
  multiline,
}: {
  label: string;
  value: string;
  hint?: string;
  auto?: boolean;
  multiline?: boolean;
}) {
  return (
    <label className="hh-field offer-mock-field">
      <span className="hh-label">
        {label}
        {auto ? <span className="offer-mock-auto">авто</span> : null}
        {hint ? <span className="muted hh-micro"> · {hint}</span> : null}
      </span>
      {multiline ? (
        <textarea className="offer-mock-textarea" rows={3} readOnly value={value} />
      ) : (
        <input type="text" readOnly value={value} />
      )}
    </label>
  );
}
