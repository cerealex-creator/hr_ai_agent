import Link from "next/link";
import { AppShell } from "@/components/AppShell";

const HUB: {
  href: string;
  title: string;
  text: string;
  soon?: boolean;
}[] = [
  {
    href: "/settings",
    title: "Основные настройки",
    text: "Telegram-чаты, календарь, внешний вид и клиенты.",
  },
  {
    href: "/documents-lab",
    title: "Разработка документов",
    text: "Шаблоны и генерация пакета документов. Скоро.",
    soon: true,
  },
  {
    href: "/vacancies",
    title: "Поиск сотрудников",
    text: "Вакансии, кандидаты, HH и Яндекс.Диск.",
  },
];

export default function HomePage() {
  return (
    <AppShell activePath="/" sidebar={null}>
      <h1 className="page-title">Главная</h1>
      <p className="muted">Выберите раздел, с которым хотите работать.</p>
      <div className="hub-grid">
        {HUB.map((item) =>
          item.soon ? (
            <div key={item.href} className="hub-card hub-card-soon" aria-disabled>
              <h2>{item.title}</h2>
              <p>{item.text}</p>
              <span className="soon">скоро</span>
            </div>
          ) : (
            <Link key={item.href} href={item.href} className="hub-card">
              <h2>{item.title}</h2>
              <p>{item.text}</p>
            </Link>
          ),
        )}
      </div>
    </AppShell>
  );
}
