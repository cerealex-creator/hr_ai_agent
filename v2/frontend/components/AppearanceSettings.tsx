"use client";

import { useUiPrefs, type ThemeId } from "@/components/UiPrefsProvider";

const THEMES: { id: ThemeId; label: string; hint: string }[] = [
  { id: "light", label: "Светлая", hint: "тёплый фон, синий акцент" },
  { id: "dark", label: "Тёмная", hint: "для работы вечером" },
  { id: "contrast", label: "Контраст", hint: "крупнее контраст текста" },
];

export function AppearanceSettings() {
  const { theme, fontScale, setTheme, setFontScale } = useUiPrefs();

  return (
    <section className="card-edit">
      <p className="muted hh-micro">Тема и размер шрифта сохраняются в этом браузере.</p>
      <div className="chip-row" role="group" aria-label="Тема">
        {THEMES.map((t) => (
          <button
            key={t.id}
            type="button"
            className={theme === t.id ? "chip chip-active" : "chip"}
            onClick={() => setTheme(t.id)}
            title={t.hint}
          >
            {t.label}
          </button>
        ))}
      </div>
      <label className="hh-field" style={{ marginTop: "0.85rem" }}>
        <span className="hh-label">Размер шрифта · {Math.round(fontScale * 100)}%</span>
        <input
          type="range"
          min={90}
          max={130}
          step={5}
          value={Math.round(fontScale * 100)}
          onChange={(e) => setFontScale(Number(e.target.value) / 100)}
        />
      </label>
    </section>
  );
}
