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

export type ThemeId =
  | "light"
  | "dark"
  | "contrast"
  | "earth"
  | "citrus"
  | "sky"
  | "oak";

export const THEME_IDS: ThemeId[] = [
  "light",
  "dark",
  "contrast",
  "earth",
  "citrus",
  "sky",
  "oak",
];

function isThemeId(v: unknown): v is ThemeId {
  return typeof v === "string" && (THEME_IDS as string[]).includes(v);
}

type UiPrefs = {
  theme: ThemeId;
  fontScale: number;
};

type UiPrefsContextValue = UiPrefs & {
  setTheme: (theme: ThemeId) => void;
  setFontScale: (scale: number) => void;
  ready: boolean;
};

const STORAGE_KEY = "hr_v2_ui_prefs";
const DEFAULTS: UiPrefs = { theme: "oak", fontScale: 1.05 };

/** Inline in layout <head> so theme/font apply before paint. Keep in sync with STORAGE_KEY / DEFAULTS / THEME_IDS. */
export const UI_PREFS_BOOT_SCRIPT = `(function(){try{var k=${JSON.stringify(STORAGE_KEY)};var ok=${JSON.stringify(THEME_IDS)};var raw=localStorage.getItem(k);if(!raw)return;var p=JSON.parse(raw);var r=document.documentElement;if(ok.indexOf(p.theme)>=0)r.dataset.theme=p.theme;var n=Number(p.fontScale);if(!Number.isNaN(n)&&n>=0.9&&n<=1.3){r.style.setProperty("--font-scale",String(Math.round(n*100)/100));r.style.fontSize=(16*(Math.round(n*100)/100))+"px";}}catch(e){}})();`;

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
    const theme = isThemeId(parsed.theme) ? parsed.theme : DEFAULTS.theme;
    return { theme, fontScale: clampScale(Number(parsed.fontScale ?? DEFAULTS.fontScale)) };
  } catch {
    return DEFAULTS;
  }
}

function applyToDom(prefs: UiPrefs) {
  const root = document.documentElement;
  root.dataset.theme = prefs.theme;
  root.style.setProperty("--font-scale", String(prefs.fontScale));
  // Explicit px so scale is visible even if some rules use fixed px on children of body.
  root.style.fontSize = `${16 * prefs.fontScale}px`;
}

export function UiPrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<UiPrefs>(DEFAULTS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const next = readStored();
    setPrefs(next);
    applyToDom(next);
    setReady(true);
  }, []);

  const persist = useCallback((updater: (prev: UiPrefs) => UiPrefs) => {
    setPrefs((prev) => {
      const next = updater(prev);
      applyToDom(next);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const setTheme = useCallback(
    (theme: ThemeId) => {
      if (!ready) return;
      persist((prev) => ({ ...prev, theme }));
    },
    [persist, ready],
  );
  const setFontScale = useCallback(
    (fontScale: number) => {
      if (!ready) return;
      persist((prev) => ({ ...prev, fontScale: clampScale(fontScale) }));
    },
    [persist, ready],
  );

  const value = useMemo(
    () => ({ ...prefs, setTheme, setFontScale, ready }),
    [prefs, setTheme, setFontScale, ready],
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
