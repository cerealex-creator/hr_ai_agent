import Link from "next/link";
import { AppShell } from "@/components/AppShell";

const HUB: {
  href: string;
  title: string;
  text: string;
  tone: "settings" | "docs" | "search";
  soon?: boolean;
}[] = [
  {
    href: "/settings",
    title: "Основные настройки",
    text: "Клиенты, Telegram, календарь, внешний вид и описание возможностей.",
    tone: "settings",
  },
  {
    href: "/documents-lab",
    title: "Разработка документов",
    text: "Шаблоны и генерация пакета документов под вакансию.",
    tone: "docs",
    soon: true,
  },
  {
    href: "/vacancies",
    title: "Поиск сотрудников",
    text: "Вакансии, воронка кандидатов, поиск на HH и Яндекс.Диск.",
    tone: "search",
  },
];

export default function HomePage() {
  return (
    <AppShell variant="home" activePath="/" sidebar={null}>
      <div className="home-hero">
        <p className="home-kicker">Рабочее пространство рекрутера</p>
        <h1 className="home-title">HR AI Agent</h1>
        <p className="home-lead">
          Выберите раздел. Позже здесь появятся новые модули — блоки уже готовы к расширению.
        </p>
      </div>
      <div className="hub-grid home-hub">
        {HUB.map((item) =>
          item.soon ? (
            <div
              key={item.href}
              className={`hub-card hub-card-tone-${item.tone} hub-card-soon`}
              aria-disabled
            >
              <span className="hub-card-index" aria-hidden />
              <h2>{item.title}</h2>
              <p>{item.text}</p>
              <span className="soon">скоро</span>
            </div>
          ) : (
            <Link
              key={item.href}
              href={item.href}
              className={`hub-card hub-card-tone-${item.tone}`}
            >
              <span className="hub-card-index" aria-hidden />
              <h2>{item.title}</h2>
              <p>{item.text}</p>
              <span className="hub-card-go">Открыть →</span>
            </Link>
          ),
        )}
      </div>
    </AppShell>
  );
}
