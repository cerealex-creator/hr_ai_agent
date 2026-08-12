import Link from "next/link";
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
    href: "/dashboard",
    title: "Поиск сотрудников",
    text: "Рабочий стол, воронка, ИИ-оценка резюме, статистика, поиск на HH.",
    tone: "search",
    featured: true,
  },
  {
    title: "Настройки управления персоналом",
    text: "Цели, задачи, показатели, процессы, оргсхема и руководящие документы (должностные инструкции, регламенты, KPI, чек-листы).",
    tone: "mgmt",
    soon: true,
  },
  {
    title: "Кадровое делопроизводство",
    text: "Приём, кадровые документы, увольнение, чек-листы обязательных документов и локальные акты.",
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
    text: "Обучение, кадровый резерв, индивидуальные планы развития (ИПР), аттестации, грейды, мониторинг.",
    tone: "dev",
    soon: true,
  },
];

export default function HomePage() {
  const featured = HUB.filter((c) => c.featured);
  const modules = HUB.filter((c) => !c.featured);

  return (
    <div className="home-v3">
      <header className="home-v3-hero">
        <BrandLogo size={80} className="home-v3-logo" />
        <h1 className="home-v3-title">HR-помогатор</h1>
        <p className="home-v3-lead">
          Рабочее пространство рекрутера и HR-команды. Сейчас доступен поиск сотрудников —
          остальные модули портала появятся по мере развития.
        </p>
      </header>

      <div className="home-v3-cards">
        {featured.map((item) => (
          <Link
            key={item.title}
            href={item.href || "/"}
            className={`home-v3-card home-v3-card-featured home-v3-tone-${item.tone}`}
          >
            <h2>{item.title}</h2>
            <p>{item.text}</p>
            <span className="home-v3-card-go">Открыть →</span>
          </Link>
        ))}

        <div className="home-v3-grid">
          {modules.map((item) => (
            <div
              key={item.title}
              className={`home-v3-card home-v3-card-soon home-v3-tone-${item.tone}`}
              aria-disabled
            >
              <div className="home-v3-card-head">
                <h2>{item.title}</h2>
                <span className="home-v3-soon">скоро</span>
              </div>
              <p>{item.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
