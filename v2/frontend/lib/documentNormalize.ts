/**
 * Bring any vacancy/history document payload to the same readable structure
 * as well-formed JSON profiles (e.g. «Графический дизайнер»).
 */

import { fieldLabel } from "@/lib/labels";

const PROFILE_FIELD_MAP: Record<string, string> = {
  подразделение: "подразделение",
  "непосредственный руководитель": "непосредственный_руководитель",
  "непосредственный руководитель сотрудника": "непосредственный_руководитель",
  "количество работников в непосредственном подчинении": "подчинённые",
  цкп: "цкп",
  "цкп должности": "цкп",
  "основные обязанности": "задачи",
  "личные качества": "психологические_черты",
  "режим, формат работы": "условия_работы.формат",
  "режим работы": "условия_работы.режим",
  "формат работы": "условия_работы.формат",
  оклад: "условия_работы.зарплата",
  "оклад (несгораемая цифра)": "условия_работы.зарплата",
  "длительность испытательного срока, критерии перехода с испытательного срока на постоянную работу":
    "условия_работы.испытательный_срок",
  "зарплатные условия на период испытательного срока": "условия_работы.зарплата_ис",
};

function tryParseJson(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (!(trimmed.startsWith("{") || trimmed.startsWith("["))) return value;
  try {
    return JSON.parse(trimmed);
  } catch {
    return value;
  }
}

function looksLikePipeTable(text: string): boolean {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length < 2) return false;
  const pipeLines = lines.filter((l) => l.includes("|"));
  return pipeLines.length >= 2 && pipeLines.length / lines.length >= 0.5;
}

function splitPipeRow(line: string): string[] {
  return line.split("|").map((p) => p.replace(/\u00a0/g, " ").trim());
}

function normalizeHeader(header: string): string {
  return header
    .toLowerCase()
    .replace(/\(.*?\)/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function setNested(target: Record<string, unknown>, path: string, value: unknown) {
  const parts = path.split(".");
  let cur: Record<string, unknown> = target;
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i];
    if (!cur[key] || typeof cur[key] !== "object" || Array.isArray(cur[key])) {
      cur[key] = {};
    }
    cur = cur[key] as Record<string, unknown>;
  }
  const last = parts[parts.length - 1];
  const prev = cur[last];
  if (prev == null || prev === "") {
    cur[last] = value;
  } else if (Array.isArray(prev)) {
    if (Array.isArray(value)) cur[last] = [...prev, ...value];
    else cur[last] = [...prev, value];
  } else if (typeof prev === "string" && typeof value === "string") {
    cur[last] = `${prev}; ${value}`;
  } else {
    cur[last] = value;
  }
}

function parseAnketaLine(line: string, anketa: Record<string, unknown>) {
  const m = line.match(/^([^:]+):\s*(.*)$/);
  if (!m) {
    const stop = anketa.стоп_факторы;
    if (Array.isArray(stop)) stop.push(line);
    else anketa.прочее = anketa.прочее ? `${anketa.прочее}; ${line}` : line;
    return;
  }
  const key = m[1].trim().toLowerCase();
  const val = m[2].trim();
  if (key.startsWith("возраст")) anketa.возраст = val;
  else if (key.startsWith("пол")) anketa.пол = val;
  else if (key.includes("стоп")) {
    anketa.стоп_факторы = val.toLowerCase() === "нет" ? [] : [val];
  } else if (key.startsWith("образование")) anketa.образование = val;
  else if (key.includes("семейн")) anketa.семейное_положение = val;
  else anketa[m[1].trim()] = val;
}

type Accum =
  | { kind: "scalar"; key: string }
  | { kind: "list"; key: string }
  | { kind: "anketa" }
  | { kind: "req"; key: "обязательные_требования" | "желательные_требования" | "психологические_черты" }
  | null;

function parseProfilePipeTable(text: string): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  let accum: Accum = null;

  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  for (const line of lines) {
    if (!line.includes("|")) continue;
    const parts = splitPipeRow(line);
    const left = parts[0] || "";
    const mid = parts[1] || "";
    const right = parts[2] || "";

    // title / header rows
    if (/^профиль должности/i.test(left) && !mid) {
      out.должность = left.replace(/^профиль должности\s*/i, "").trim();
      continue;
    }
    if (/^описание$/i.test(left) && /^комментарии$/i.test(right || mid)) {
      continue;
    }

    if (!left && mid && accum) {
      // continuation of previous multi-value section
      if (accum.kind === "list") {
        const arr = (out[accum.key] as string[]) || [];
        arr.push(mid);
        out[accum.key] = arr;
      } else if (accum.kind === "anketa") {
        const anketa = (out.анкетные_требования as Record<string, unknown>) || {};
        parseAnketaLine(mid, anketa);
        out.анкетные_требования = anketa;
      } else if (accum.kind === "req") {
        const arr = (out[accum.key] as Array<Record<string, string>>) || [];
        if (accum.key === "психологические_черты") {
          arr.push({ качество: mid, проявление: "" });
        } else {
          arr.push({ навык: mid, описание: "" });
        }
        out[accum.key] = arr;
      } else if (accum.kind === "scalar" && right) {
        // rare
      }
      continue;
    }

    if (!left) continue;

    const headerNorm = normalizeHeader(left);
    const mapped = PROFILE_FIELD_MAP[headerNorm];

    if (headerNorm.startsWith("анкетные")) {
      accum = { kind: "anketa" };
      const anketa: Record<string, unknown> = {};
      if (mid) parseAnketaLine(mid, anketa);
      out.анкетные_требования = anketa;
      continue;
    }

    if (
      headerNorm.includes("необходимые профессиональные навыки") &&
      headerNorm.includes("без которых")
    ) {
      accum = { kind: "req", key: "обязательные_требования" };
      const arr: Array<Record<string, string>> = [];
      if (mid) arr.push({ навык: mid, описание: "" });
      out.обязательные_требования = arr;
      continue;
    }

    if (
      headerNorm.includes("необходимые профессиональные навыки") &&
      (headerNorm.includes("освоить") || headerNorm.includes("первые"))
    ) {
      accum = { kind: "req", key: "желательные_требования" };
      const arr: Array<Record<string, string>> = [];
      if (mid) arr.push({ навык: mid, описание: "" });
      out.желательные_требования = arr;
      continue;
    }

    if (headerNorm === "личные качества" || headerNorm.startsWith("психологическ")) {
      accum = { kind: "req", key: "психологические_черты" };
      const arr: Array<Record<string, string>> = [];
      if (mid) arr.push({ качество: mid, проявление: "" });
      out.психологические_черты = arr;
      continue;
    }

    if (mapped === "задачи" || headerNorm.includes("обязанност")) {
      accum = { kind: "list", key: "задачи" };
      const arr: string[] = [];
      if (mid) arr.push(mid);
      out.задачи = arr;
      continue;
    }

    if (mapped?.startsWith("условия_работы.")) {
      accum = { kind: "scalar", key: mapped };
      if (mid) setNested(out, mapped, mid);
      if (right && mapped.endsWith("зарплата")) {
        setNested(out, mapped, mid ? `${mid} (${right})` : right);
      }
      continue;
    }

    if (headerNorm.startsWith("переменная часть")) {
      accum = { kind: "scalar", key: "условия_работы.бонус" };
      const bonus = [mid, right].filter(Boolean).join(" — ");
      if (bonus) setNested(out, "условия_работы.бонус", bonus);
      // also append to salary line if present
      const cond = (out.условия_работы as Record<string, unknown>) || {};
      if (cond.зарплата && bonus) {
        cond.зарплата = `${cond.зарплата}; бонус: ${bonus}`;
        out.условия_работы = cond;
      }
      continue;
    }

    if (mapped) {
      accum = { kind: "scalar", key: mapped };
      if (mid) setNested(out, mapped, mid);
      continue;
    }

    // fallback: keep as labeled field (readable, Russian header preserved)
    accum = null;
    const key = left.replace(/\s+/g, " ").trim();
    const val = [mid, right].filter(Boolean).join(" — ");
    if (val) out[key] = val;
  }

  // merge зарплата_ис into зарплата if useful
  const cond = out.условия_работы as Record<string, unknown> | undefined;
  if (cond?.зарплата_ис && cond.зарплата) {
    cond.зарплата = `${cond.зарплата}; на ИС: ${cond.зарплата_ис}`;
    delete cond.зарплата_ис;
  }

  return out;
}

function parseQuestionnairePipeTable(text: string): Array<Record<string, unknown>> {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return [];

  const rows = lines.map(splitPipeRow);
  // Find header
  let headerIdx = rows.findIndex((r) =>
    r.some((c) => /^вопрос$/i.test(c)) && r.some((c) => /^№/.test(c) || c === "№"),
  );
  if (headerIdx < 0) headerIdx = 0;
  const header = rows[headerIdx].map((h) => h.toLowerCase());
  const idxQuestion = header.findIndex((h) => h === "вопрос");
  const idxDesired = header.findIndex((h) => h.includes("желательн"));
  const idxResume = header.findIndex((h) => h.includes("резюме"));
  const qIdx = idxQuestion >= 0 ? idxQuestion : 1;
  const dIdx = idxDesired >= 0 ? idxDesired : 4;

  const result: Array<Record<string, unknown>> = [];
  let currentCategory = "";

  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    let num = (row[0] || "").trim();
    let question = (row[qIdx] || "").trim();
    let desired = (row[dIdx] || "").trim();
    let resume = idxResume >= 0 ? (row[idxResume] || "").trim() : "";

    // Rows without №: question text sits in column 0
    if (num && !/^\d+(\.\d+)?$/.test(num) && qIdx > 0) {
      question = num;
      // shift: original col1 may be empty resume, desired moves
      resume = (row[1] || "").trim() || resume;
      desired = (row[dIdx - 1] || row[dIdx] || "").trim() || desired;
      // preferred: find longest "desirable" looking cell
      if (!desired || desired === "False" || desired === "True") {
        const candidates = row
          .slice(1)
          .map((c) => c.trim())
          .filter((c) => c && !/^(true|false)$/i.test(c));
        desired = candidates.sort((a, b) => b.length - a.length)[0] || "";
      }
      num = "";
    }

    const filled = row.filter((c) => c).length;

    // Section header: "4.0 | Hard Skills title"
    if (/^\d+(\.0)?$/.test(num) && question && filled <= 2 && !desired) {
      currentCategory = question;
      continue;
    }

    if (question) {
      const cleanQ = question.replace(/\s+/g, " ").trim();
      if (cleanQ.length < 12 || /^итог:?$/i.test(cleanQ)) {
        continue;
      }
      const item: Record<string, unknown> = { вопрос: cleanQ };
      if (desired && !/^(true|false)$/i.test(desired)) item.пример_ответа = desired;
      if (resume && !/^(true|false)$/i.test(resume)) item["что уже есть в резюме"] = resume;
      if (currentCategory) item.категория = currentCategory;
      // skip pure section markers mistaken as questions
      if (/^\d+(\.0)?$/.test(num) && filled <= 2 && !item.пример_ответа) {
        currentCategory = cleanQ;
        continue;
      }
      result.push(item);
    }
  }

  return result.length ? result : [{ вопрос: text }];
}

function unwrapRaw(data: unknown): unknown {
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const obj = data as Record<string, unknown>;
    const keys = Object.keys(obj);
    if (keys.length === 1 && keys[0] === "raw" && typeof obj.raw === "string") {
      return obj.raw;
    }
  }
  return data;
}

function normalizeKeywords(value: unknown): unknown {
  if (typeof value !== "string") return value;
  if (value.includes("|") && looksLikePipeTable(value)) return value;
  if (value.includes(",") && !value.includes("\n")) {
    const parts = value.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length >= 2) return parts;
  }
  return value;
}

function normalizeQuestions(value: unknown): unknown {
  let data = value;
  if (typeof data === "string") data = tryParseJson(data);
  data = unwrapRaw(data);

  if (typeof data === "string" && looksLikePipeTable(data)) {
    return parseQuestionnairePipeTable(data);
  }

  if (Array.isArray(data)) {
    // Single item holding a full markdown table in "вопрос"
    if (
      data.length === 1 &&
      data[0] &&
      typeof data[0] === "object" &&
      typeof (data[0] as Record<string, unknown>).вопрос === "string" &&
      looksLikePipeTable(String((data[0] as Record<string, unknown>).вопрос))
    ) {
      return parseQuestionnairePipeTable(String((data[0] as Record<string, unknown>).вопрос));
    }
    return data;
  }

  return data;
}

function normalizeProfile(value: unknown): unknown {
  let data = value;
  if (typeof data === "string") data = tryParseJson(data);
  data = unwrapRaw(data);

  if (typeof data === "string" && looksLikePipeTable(data)) {
    return parseProfilePipeTable(data);
  }

  // Already structured object — keep
  if (data && typeof data === "object" && !Array.isArray(data)) {
    return data;
  }

  return data;
}

/** Normalize one document field for readable UI. */
export function normalizeDocumentValue(docKey: string, value: unknown): unknown {
  const key = docKey.toLowerCase();
  if (key === "profile" || key === "профиль") {
    return normalizeProfile(value);
  }
  if (key === "questions" || key === "опросник") {
    return normalizeQuestions(value);
  }
  if (key === "keywords" || key === "ключевые_слова" || key === "ключевые слова") {
    let data = value;
    if (typeof data === "string") data = tryParseJson(data);
    data = unwrapRaw(data);
    return normalizeKeywords(data);
  }
  if (key === "vacancy_text" || key === "текст_вакансии" || key === "текст вакансии") {
    let data = value;
    if (typeof data === "string") data = tryParseJson(data);
    data = unwrapRaw(data);
    return data;
  }

  let data = value;
  if (typeof data === "string") data = tryParseJson(data);
  data = unwrapRaw(data);
  if (typeof data === "string" && looksLikePipeTable(data)) {
    // generic pipe table → list of {поле, значение}
    const rows = data
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.includes("|"))
      .map(splitPipeRow)
      .filter((r) => r[0] || r[1]);
    const obj: Record<string, unknown> = {};
    for (const r of rows) {
      if (r[0] && r[1]) obj[r[0]] = r[1];
      else if (!r[0] && r[1]) {
        // skip orphan continuations in generic mode
      }
    }
    return Object.keys(obj).length ? obj : data;
  }
  return data;
}

export function documentSectionTitle(docKey: string): string {
  return fieldLabel(docKey);
}
