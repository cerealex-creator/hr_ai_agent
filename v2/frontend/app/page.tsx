import { BrandLogo } from "@/components/BrandLogo";
import { HomeHubCards } from "@/components/HomeHubCards";

export default function HomePage() {
  return (
    <div className="home-v3">
      <header className="home-v3-hero">
        <BrandLogo size={80} className="home-v3-logo" />
        <h1 className="home-v3-title">HR-помогатор</h1>
        <p className="home-v3-lead">
          Рабочее пространство рекрутера и HR-команды. Модули портала доступны по мере подключения
          функций организации.
        </p>
      </header>

      <HomeHubCards />
    </div>
  );
}
