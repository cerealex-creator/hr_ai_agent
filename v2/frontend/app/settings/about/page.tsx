import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";

const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "Вакансии и кандидаты",
    items: [
      "Вакансии в работе и в архиве, привязка к компании или подразделению.",
      "Карточка кандидата: этапы HR, статусы заказчика, комментарии, материалы, оценка резюме.",
      "Способы добавления: вручную и из файла всегда; по ссылке, синхронизация папки вакансии и роутинг из inbox Яндекс Диска — включаются в настройках.",
      "Холодный поиск резюме на HH с ИИ-оценкой, shortlist и перенос в воронку (включается в «Функции»).",
      "Документы вакансии: профиль, вопросы, оффер и др. — генерация и правка.",
    ],
  },
  {
    title: "Взаимодействие с заказчиком",
    items: [
      "Компании и подразделения, режимы чатов, тестовый чат.",
      "Каналы связи: Bitrix24 и Telegram (WhatsApp и Max — позже).",
      "Отправка кандидата заказчику и статусы с комментариями в клиентской зоне / Bitrix.",
    ],
  },
  {
    title: "Уведомления и встречи",
    items: [
      "Личный Google Calendar: включаете сами и подключаете через OAuth (пошаговая инструкция в настройках).",
      "Zoom для созвонов настраивает администратор на компанию.",
      "Личные Telegram-уведомления (опционально) после привязки Chat ID.",
    ],
  },
  {
    title: "Сервис",
    items: [
      "Статистика по воронке и эффективности HH.",
      "Фоновые задачи: поиск HH, расшифровка, синхронизация Диска, роутинг inbox.",
      "Темы оформления (включая коричнево-зелёную, оранжево-белую, бело-синюю) и размер шрифта.",
    ],
  },
];

export default function AboutSettingsPage() {
  return (
    <RecruitingShell activePath="/settings" title="Настройки">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Описание функционала</h1>
      <p className="muted">
        Актуальные возможности HR-помогатора. Список дополняется по мере развития модулей.
      </p>

      {SECTIONS.map((section) => (
        <section key={section.title} className="card-edit about-block">
          <h2>{section.title}</h2>
          <ul className="about-list">
            {section.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ))}
    </RecruitingShell>
  );
}
