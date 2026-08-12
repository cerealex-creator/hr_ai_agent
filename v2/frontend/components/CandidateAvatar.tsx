"use client";

import { resolveCandidateGender, type CandidateGender } from "@/lib/inferGender";

type Props = {
  name: string;
  photoUrl?: string | null;
  gender?: string | null;
  size?: number;
  className?: string;
};

function initialsFromName(name: string): string {
  const parts = (name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function GenderSilhouette({ gender, size }: { gender: CandidateGender; size: number }) {
  const icon = size * 0.52;
  return (
    <svg
      className="cand-avatar-silhouette"
      width={icon}
      height={icon}
      viewBox="0 0 24 24"
      aria-hidden
    >
      <circle cx="12" cy="8" r="4" fill="currentColor" />
      <path d="M4 22c0-4 4-7 8-7s8 3 8 7" fill="currentColor" />
      {gender === "female" ? (
        <>
          <path d="M12 14v4" stroke="var(--card, #f2f3f5)" strokeWidth="1.6" />
          <path d="M10 16h4" stroke="var(--card, #f2f3f5)" strokeWidth="1.6" />
        </>
      ) : null}
    </svg>
  );
}

/** Avatar: photo, gender silhouette, or initials. */
export function CandidateAvatar({
  name,
  photoUrl,
  gender,
  size = 48,
  className = "",
}: Props) {
  const url = (photoUrl || "").trim();
  const resolvedGender = resolveCandidateGender(gender, name);
  const initials = initialsFromName(name);
  const px = `${size}px`;
  const fontSize = Math.max(11, Math.round(size * 0.32));

  if (url) {
    return (
      <img
        src={url}
        alt=""
        className={`cand-avatar cand-avatar-img ${className}`.trim()}
        width={size}
        height={size}
        style={{ width: px, height: px, fontSize }}
        loading="lazy"
        referrerPolicy="no-referrer"
      />
    );
  }

  if (resolvedGender) {
    return (
      <span
        className={`cand-avatar cand-avatar-silhouette-wrap ${className}`.trim()}
        aria-hidden
        style={{ width: px, height: px }}
      >
        <GenderSilhouette gender={resolvedGender} size={size} />
      </span>
    );
  }

  return (
    <span
      className={`cand-avatar cand-avatar-fallback ${className}`.trim()}
      aria-hidden
      style={{ width: px, height: px, fontSize }}
    >
      {initials}
    </span>
  );
}
