"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ThemeId = "light" | "dark" | "contrast";

type UiPrefs = {
  theme: ThemeId;
  fontScale: number;
};

type UiPrefsContextValue = UiPrefs & {
  setTheme: (theme: ThemeId) => void;
  setFontScale: (scale: number) => void;
};

const STORAGE_KEY = "hr_v2_ui_prefs";
const DEFAULTS: UiPrefs = { theme: "light", fontScale: 1.05 };

const UiPrefsContext = createContext<UiPrefsContextValue | null>(null);

function clampScale(n: number): number {
  if (Number.isNaN(n)) return DEFAULTS.fontScale;
  return Math.min(1.3, Math.max(0.9, Math.round(n * 100) / 100));
}

function readStored(): UiPrefs {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<UiPrefs>;
    const theme =
      parsed.theme === "dark" || parsed.theme === "contrast" || parsed.theme === "light"
        ? parsed.theme
        : DEFAULTS.theme;
    return { theme, fontScale: clampScale(Number(parsed.fontScale ?? DEFAULTS.fontScale)) };
  } catch {
    return DEFAULTS;
  }
}

function applyToDom(prefs: UiPrefs) {
  const root = document.documentElement;
  root.dataset.theme = prefs.theme;
  root.style.setProperty("--font-scale", String(prefs.fontScale));
}

export function UiPrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<UiPrefs>(DEFAULTS);

  useEffect(() => {
    const next = readStored();
    setPrefs(next);
    applyToDom(next);
  }, []);

  const persist = useCallback((next: UiPrefs) => {
    setPrefs(next);
    applyToDom(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  const setTheme = useCallback(
    (theme: ThemeId) => persist({ ...prefs, theme }),
    [persist, prefs],
  );
  const setFontScale = useCallback(
    (fontScale: number) => persist({ ...prefs, fontScale: clampScale(fontScale) }),
    [persist, prefs],
  );

  const value = useMemo(
    () => ({ ...prefs, setTheme, setFontScale }),
    [prefs, setTheme, setFontScale],
  );

  return (
    <UiPrefsContext.Provider value={value}>{children}</UiPrefsContext.Provider>
  );
}

export function useUiPrefs(): UiPrefsContextValue {
  const ctx = useContext(UiPrefsContext);
  if (!ctx) {
    throw new Error("useUiPrefs must be used within UiPrefsProvider");
  }
  return ctx;
}
