import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { BrandLogo } from "@/components/BrandLogo";

type HubCard = {
  href?: string;
  title: string;
  text: string;
  tone: "search" | "mgmt" | "kdp" | "people" | "dev";
  soon?: boolean;
  featured?: boolean;
};

const HUB: HubCard[] = [
  {
    href: "/vacancies",
    title: "Поиск сотрудников",
    text: "Генерация документов по вакансии (Профиль, опросник и др), управление воронкой поиска с ИИ-поддержкой, статистика, умный поиск на HH.",
    tone: "search",
    featured: true,
  },
  {
    title: "Настройки управления персоналом",
    text:
      "Цели, задачи, показатели, процессы, оргсхема и руководящие документы (должностные инструкции, регламенты, KPI, чек-листы).",
    tone: "mgmt",
    soon: true,
  },
  {
    title: "Кадровое делопроизводство",
    text:
      "Приём, кадровые документы, увольнение, чек-листы обязательных документов и локальные акты.",
    tone: "kdp",
    soon: true,
  },
  {
    title: "Управление персоналом",
    text: "Правила, NDA и соглашения, опросы удовлетворённости и вовлечённости.",
    tone: "people",
    soon: true,
  },
  {
    title: "Корректировка и развитие",
    text:
      "Обучение, кадровый резерв, индивидуальные планы развития (ИПР), аттестации, грейды, мониторинг.",
    tone: "dev",
    soon: true,
  },
];

export default function HomePage() {
  const featured = HUB.filter((c) => c.featured);
  const modules = HUB.filter((c) => !c.featured);

  return (
    <AppShell variant="home" activePath="/">
      <div className="home-hero">
        <h1 className="home-title">
          <BrandLogo size={96} />
          HR-помогатор
        </h1>
        <p className="home-lead">
          Рабочее пространство рекрутера и HR-команды. Сейчас доступен поиск сотрудников —
          остальные модули портала появятся по мере развития.
        </p>
      </div>

      <div className="home-portal">
        {featured.map((item) => (
          <Link
            key={item.title}
            href={item.href || "/"}
            className={`hub-card hub-card-tone-${item.tone} hub-card-featured`}
          >
            <span className="hub-card-index" aria-hidden />
            <h2>{item.title}</h2>
            <p>{item.text}</p>
            <span className="hub-card-go">Открыть →</span>
          </Link>
        ))}

        <div className="home-modules">
          {modules.map((item) =>
            item.soon || !item.href ? (
              <div
                key={item.title}
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
                key={item.title}
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
      </div>
    </AppShell>
  );
}
