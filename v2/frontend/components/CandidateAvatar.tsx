"use client";

import { resolveCandidateGender, type CandidateGender } from "@/lib/inferGender";

type Props = {
  name: string;
  photoUrl?: string | null;
  gender?: string | null;
  size?: number;
  className?: string;
};

const PLACEHOLDER_MALE = "/candidate-placeholder-male.png";
const PLACEHOLDER_FEMALE = "/candidate-placeholder-female.png";

function placeholderForGender(gender: CandidateGender): string {
  return gender === "female" ? PLACEHOLDER_FEMALE : PLACEHOLDER_MALE;
}

/** Avatar: фото кандидата или плейсхолдер по полу. */
export function CandidateAvatar({
  name,
  photoUrl,
  gender,
  size = 48,
  className = "",
}: Props) {
  const url = (photoUrl || "").trim();
  const resolvedGender = resolveCandidateGender(gender, name) ?? "male";
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

  return (
    <img
      src={placeholderForGender(resolvedGender)}
      alt=""
      className={`cand-avatar cand-avatar-img cand-avatar-placeholder ${className}`.trim()}
      width={size}
      height={size}
      style={{ width: px, height: px, fontSize }}
      loading="lazy"
      aria-hidden
    />
  );
}
