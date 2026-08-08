"use client";

import Link from "next/link";

type Props = {
  active?: boolean;
  aboutActive?: boolean;
};

/** Compact entry to /settings (+ about) — top of left sidebar on all shells. */
export function SettingsRail({ active = false, aboutActive = false }: Props) {
  return (
    <div className="settings-rail">
      <Link
        href="/settings"
        className={active && !aboutActive ? "settings-rail-link is-active" : "settings-rail-link"}
      >
        <span className="settings-rail-title">Основные настройки</span>
        <span className="settings-rail-desc">Внешний вид и инструменты</span>
      </Link>
      <Link
        href="/settings/about"
        className={aboutActive ? "settings-rail-link is-active" : "settings-rail-link"}
      >
        <span className="settings-rail-title">Описание функционала</span>
        <span className="settings-rail-desc">Что умеет программа</span>
      </Link>
    </div>
  );
}
