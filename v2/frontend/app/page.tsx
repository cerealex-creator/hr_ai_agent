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
    href: "/management-system",
    title: "Настройки управления персоналом",
    text: "Создаёт и внедряет систему управления:\n— цели компании и собственника, задачи и показатели;\n— описания процессов и оргсхемы;\n— должностные инструкции, регламенты, KPI, чек-листы.",
    tone: "mgmt",
  },
  {
    title: "Кадровое делопроизводство",
    text: "Готовит документы и автоматизирует кадровые процедуры:\n— генерация и актуализация кадровых документов;\n— правильное оформление приёма и увольнения;\n— контроль соблюдения трудового законодательства по чек-листам обязательных документов и локальных актов.",
    tone: "kdp",
    soon: true,
  },
  {
    title: "Управление и работа с персоналом",
    text: "Создаёт и внедряет инструменты повседневной работы с персоналом:\n— регламенты, NDA и соглашения;\n— опросы удовлетворённости и вовлечённости;\n— другие инструменты по мере необходимости.",
    tone: "people",
    soon: true,
  },
  {
    title: "Корректировка и развитие",
    text: "Настраивает инструменты роста сотрудников:\n— автоматизация адаптации и обучения;\n— кадровый резерв и индивидуальные планы развития;\n— аттестации, грейды, мониторинг профессиональных навыков.",
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
          Рабочее пространство рекрутера и HR-команды. Доступны поиск сотрудников и модуль
          «Настройки управления персоналом» — остальные блоки портала появятся по мере развития.
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
          {modules.map((item) =>
            item.href ? (
              <Link
                key={item.title}
                href={item.href}
                className={`home-v3-card home-v3-tone-${item.tone}`}
              >
                <div className="home-v3-card-head">
                  <h2>{item.title}</h2>
                </div>
                <p>{item.text}</p>
                <span className="home-v3-card-go">Открыть →</span>
              </Link>
            ) : (
              <div
                key={item.title}
                className={`home-v3-card home-v3-card-soon home-v3-tone-${item.tone}`}
                aria-disabled
              >
                <div className="home-v3-card-head">
                  <h2>{item.title}</h2>
                  <span className="home-v3-soon">В разработке</span>
                </div>
                <p>{item.text}</p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
