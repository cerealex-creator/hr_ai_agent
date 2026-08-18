"use client";

import type { CSSProperties } from "react";

export const VACANCY_AVATAR_KEYS = [
  "design",
  "marketing",
  "sales",
  "it",
  "hr",
  "logistics",
  "finance",
  "support",
  "admin",
  "legal",
  "education",
  "general",
  "pencil",
  "monitor",
  "cargo",
  "alert",
  "people",
  "question",
] as const;

export type VacancyAvatarKey = (typeof VACANCY_AVATAR_KEYS)[number];

export const VACANCY_AVATAR_LABELS: Record<VacancyAvatarKey, string> = {
  design: "Дизайн",
  marketing: "Маркетинг",
  sales: "Продажи",
  it: "IT / разработка",
  hr: "HR / подбор",
  logistics: "Логистика",
  finance: "Финансы",
  support: "Поддержка",
  admin: "Админ / офис",
  legal: "Юриспруденция",
  education: "Обучение",
  general: "Общая",
  pencil: "Карандаш",
  monitor: "Монитор",
  cargo: "Ящик / груз",
  alert: "Восклицательный знак",
  people: "Люди",
  question: "Вопросительный знак",
};

const TONES: Record<VacancyAvatarKey, { bg: string; fg: string }> = {
  design: { bg: "#efe7ff", fg: "#6b4fd6" },
  marketing: { bg: "#ffe8d6", fg: "#d35400" },
  sales: { bg: "#e6f6ec", fg: "#1f8a45" },
  it: { bg: "#e4eefc", fg: "#2e6fd6" },
  hr: { bg: "#fde8ef", fg: "#c2185b" },
  logistics: { bg: "#e8f4f8", fg: "#0e7490" },
  finance: { bg: "#eef6e4", fg: "#4d7c0f" },
  support: { bg: "#e8f7f4", fg: "#0f766e" },
  admin: { bg: "#f1f3f6", fg: "#475569" },
  legal: { bg: "#f3ebe4", fg: "#92400e" },
  education: { bg: "#fff4d6", fg: "#b45309" },
  general: { bg: "#eef2f7", fg: "#3b4a63" },
  pencil: { bg: "#fff1e8", fg: "#c2410c" },
  monitor: { bg: "#e8eef8", fg: "#334155" },
  cargo: { bg: "#f3ebe0", fg: "#9a3412" },
  alert: { bg: "#fde8e8", fg: "#b91c1c" },
  people: { bg: "#e8f1fb", fg: "#1d4ed8" },
  question: { bg: "#f3eefc", fg: "#6d28d9" },
};

function Icon({ avatarKey }: { avatarKey: VacancyAvatarKey }) {
  const common = {
    width: "58%",
    height: "58%",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (avatarKey) {
    case "design":
      return (
        <svg {...common}>
          <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" />
          <path d="M5 19h14" />
        </svg>
      );
    case "marketing":
      return (
        <svg {...common}>
          <path d="M3 11v2a2 2 0 002 2h2l5 4V5L7 9H5a2 2 0 00-2 2z" />
          <path d="M16 9a4 4 0 010 6" />
        </svg>
      );
    case "sales":
      return (
        <svg {...common}>
          <path d="M4 19V5" />
          <path d="M4 19h16" />
          <path d="M8 15l3-4 3 2 4-6" />
        </svg>
      );
    case "it":
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="12" rx="2" />
          <path d="M8 21h8" />
          <path d="M9 9l-2 2 2 2" />
          <path d="M15 9l2 2-2 2" />
        </svg>
      );
    case "hr":
      return (
        <svg {...common}>
          <circle cx="9" cy="8" r="3" />
          <circle cx="17" cy="9" r="2.5" />
          <path d="M3 19c0-3 2.5-5 6-5s6 2 6 5" />
          <path d="M14 19c.4-2 2-3.5 4.5-3.5 1.2 0 2.2.3 3 .8" />
        </svg>
      );
    case "logistics":
      return (
        <svg {...common}>
          <path d="M3 7h11v10H3z" />
          <path d="M14 10h4l3 3v4h-7" />
          <circle cx="7" cy="18" r="2" />
          <circle cx="17" cy="18" r="2" />
        </svg>
      );
    case "finance":
      return (
        <svg {...common}>
          <rect x="3" y="6" width="18" height="12" rx="2" />
          <circle cx="12" cy="12" r="2.5" />
          <path d="M7 12h1M16 12h1" />
        </svg>
      );
    case "support":
      return (
        <svg {...common}>
          <path d="M4 12a8 8 0 0116 0" />
          <path d="M4 12v3a2 2 0 002 2h1v-5H4z" />
          <path d="M20 12v3a2 2 0 01-2 2h-1v-5h3z" />
          <path d="M12 19v1a2 2 0 002 2h1" />
        </svg>
      );
    case "admin":
      return (
        <svg {...common}>
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <path d="M8 8h8M8 12h8M8 16h5" />
        </svg>
      );
    case "legal":
      return (
        <svg {...common}>
          <path d="M12 3v18" />
          <path d="M5 8h14" />
          <path d="M7 8l-3 7h6L7 8z" />
          <path d="M17 8l-3 7h6l-3-7z" />
        </svg>
      );
    case "education":
      return (
        <svg {...common}>
          <path d="M2 9l10-5 10 5-10 5L2 9z" />
          <path d="M6 11.5V16c0 1.5 2.5 3 6 3s6-1.5 6-3v-4.5" />
        </svg>
      );
    case "pencil":
      return (
        <svg {...common}>
          <path d="M4 20l4.5-1.2L19.5 8l-3.3-3.3L5.7 15.2 4 20z" />
          <path d="M14.5 6.2l3.3 3.3" />
          <path d="M5.2 16.5l2.4 2.2" />
        </svg>
      );
    case "monitor":
      return (
        <svg {...common}>
          <rect x="3" y="4" width="18" height="13" rx="2" />
          <path d="M8 21h8" />
          <path d="M12 17v4" />
          <path d="M7 9h10" />
          <path d="M7 12h6" />
        </svg>
      );
    case "cargo":
      return (
        <svg {...common}>
          <path d="M4 8l8-3 8 3v10l-8 3-8-3V8z" />
          <path d="M12 5v13" />
          <path d="M4 8l8 3 8-3" />
          <path d="M9 11.2v3.2" />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path d="M12 3l9 16H3L12 3z" />
          <path d="M12 10v4" />
          <path d="M12 16.5h.01" />
        </svg>
      );
    case "people":
      return (
        <svg {...common}>
          <circle cx="7" cy="8" r="2.4" />
          <circle cx="12" cy="7" r="2.6" />
          <circle cx="17" cy="8" r="2.4" />
          <path d="M2.8 19c.4-2.6 2.4-4.2 4.4-4.2 1.1 0 2.1.5 2.8 1.2" />
          <path d="M7.5 19c.5-3 2.4-5 4.5-5s4 2 4.5 5" />
          <path d="M14 16c.7-.7 1.7-1.2 2.8-1.2 2 0 4 1.6 4.4 4.2" />
        </svg>
      );
    case "question":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M9.6 9.2a2.6 2.6 0 015 .9c0 1.5-1.2 2.1-2.1 2.7-.7.5-1.1 1-1.1 1.9" />
          <path d="M12 17.2h.01" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <rect x="4" y="4" width="16" height="16" rx="3" />
          <path d="M8 14h8M8 10h5" />
        </svg>
      );
  }
}

export function normalizeVacancyAvatarKey(raw: unknown): VacancyAvatarKey {
  const key = String(raw || "").trim().toLowerCase();
  if ((VACANCY_AVATAR_KEYS as readonly string[]).includes(key)) {
    return key as VacancyAvatarKey;
  }
  return "general";
}

type Props = {
  avatarKey?: string | null;
  size?: number;
  className?: string;
  title?: string;
};

export function VacancyAvatar({ avatarKey, size = 40, className = "", title }: Props) {
  const key = normalizeVacancyAvatarKey(avatarKey);
  const tone = TONES[key];
  const style: CSSProperties = {
    width: size,
    height: size,
    background: tone.bg,
    color: tone.fg,
  };
  return (
    <span
      className={`vac-avatar ${className}`.trim()}
      style={style}
      title={title || VACANCY_AVATAR_LABELS[key]}
      aria-hidden
    >
      <Icon avatarKey={key} />
    </span>
  );
}
