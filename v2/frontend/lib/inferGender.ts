/** Эвристика пола по ФИО (если в карточке нет явного gender). */
export type CandidateGender = "male" | "female";

const FEMALE_PATRONYMIC = /(овна|евна|ична|inichna)$/i;
const MALE_PATRONYMIC = /(ович|евич|ич|vich|ovich)$/i;

const FEMALE_FIRST = new Set(
  "анна мария елена ольга наталья татьяна ирина светлана алиса виктория юлия дарья алина".split(
    " ",
  ),
);

export function inferGenderFromName(name: string): CandidateGender | null {
  const parts = (name || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return null;

  const patronymic = parts.length >= 3 ? parts[2] : parts.length === 2 ? parts[1] : "";
  if (FEMALE_PATRONYMIC.test(patronymic)) return "female";
  if (MALE_PATRONYMIC.test(patronymic)) return "male";

  const first = parts[0].replace(/[^a-zа-яё-]/gi, "");
  if (FEMALE_FIRST.has(first)) return "female";
  if (first.endsWith("а") || first.endsWith("я")) {
    const exceptions = new Set(["никита", "илья", "фома", "кузьма", "лука"]);
    if (!exceptions.has(first)) return "female";
  }
  if (first.endsWith("й") || first.endsWith("н") || first.endsWith("р") || first.endsWith("л")) {
    return "male";
  }
  return null;
}

export function resolveCandidateGender(
  gender: string | null | undefined,
  name: string,
): CandidateGender | null {
  const g = (gender || "").trim().toLowerCase();
  if (g === "male" || g === "m" || g === "муж" || g === "мужской") return "male";
  if (g === "female" || g === "f" || g === "жен" || g === "женский") return "female";
  return inferGenderFromName(name);
}
