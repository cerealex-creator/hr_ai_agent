/** UI labels (RU). Keep storage keys in English; show Russian in UI. */

export const HR_STAGE_LABELS: Record<string, string> = {
  resume_screening: "Отсев резюме",
  primary_contact: "Первичный контакт",
  no_response_3d: "Кандидат не отвечает более 3 дней",
  interview_scheduled: "Собеседование назначено",
  interview_done: "Собеседование проведено",
  test_task: "Тестовое задание",
  client_review: "На оценке у заказчика",
  client_pause: "Пауза",
  client_meeting: "Встреча с заказчиком",
  offer: "Оффер",
  internship: "Выход на стажировку",
  started_work: "Вышел на работу",
  rejected: "Отказ",
  archived: "Архив",
  rejected_candidate: "Отказ кандидата",
  rejected_client: "Отказ заказчика",
  rejected_hr: "Отказ мой",
  rejected_vacancy_closed: "Отказ: вакансия закрыта",
};

/** Positive funnel for stage progress UI (excludes rejects / archive). */
export const HR_FUNNEL_STAGES = [
  "resume_screening",
  "primary_contact",
  "no_response_3d",
  "interview_scheduled",
  "interview_done",
  "offer",
  "test_task",
  "client_review",
  "client_pause",
  "client_meeting",
  "internship",
  "started_work",
] as const;

export const REJECTION_STAGES = new Set([
  "rejected",
  "rejected_candidate",
  "rejected_client",
  "rejected_hr",
  "rejected_vacancy_closed",
]);

export function isRejectionStage(stage: string): boolean {
  return REJECTION_STAGES.has(stage);
}

const CONTROL_WORD_LABELS: Record<string, string> = {
  exact: "совпало",
  fuzzy: "почти совпало",
  missing: "не найдено",
  no_cover_letter: "нет письма",
};

export function controlWordStatusLabel(status: string | null | undefined): string {
  const key = (status || "").trim().toLowerCase();
  return CONTROL_WORD_LABELS[key] || status || "";
}

/** Visual tone for list markers (кружок у этапа). */
export type StageTone =
  | "none"
  | "yellow"
  | "green-1"
  | "green-2"
  | "green-3"
  | "green-4"
  | "green-5"
  | "rejected";

/**
 * Отсев — без цвета; Первичный контакт — жёлтый;
 * дальше зелёный светлее→ярче к офферу; отказ — красный.
 */
export function getStageTone(stage: string | null | undefined): StageTone {
  if (!stage) return "none";
  if (isRejectionStage(stage)) return "rejected";
  switch (stage) {
    case "resume_screening":
    case "archived":
      return "none";
    case "primary_contact":
      return "yellow";
    case "no_response_3d":
      return "yellow";
    case "interview_scheduled":
      return "green-1";
    case "interview_done":
      return "green-2";
    case "offer":
      return "green-3";
    case "test_task":
      return "green-2";
    case "client_review":
      return "green-3";
    case "client_pause":
      return "green-3";
    case "client_meeting":
      return "green-4";
    case "internship":
      return "green-5";
    case "started_work":
      return "green-5";
    default:
      return "none";
  }
}

export const CLIENT_STATUS_LABELS: Record<string, string> = {
  new: "Новый",
  wait: "Ждёт оценки",
  ready: "Встреча",
  reject: "Отказ",
  think: "Подумать",
  offer: "Оффер",
  started: "Вышел на работу",
};

const CLIENT_ZONE_STAGES = new Set([
  "client_review",
  "client_pause",
  "client_meeting",
  "offer",
  "internship",
  "started_work",
]);

/** Nested document / profile field keys → RU */
export const FIELD_LABELS: Record<string, string> = {
  profile: "Профиль",
  vacancy_text: "Текст вакансии",
  questions: "Опросник",
  keywords: "Ключевые слова",
  notes: "Заметки",
  профиль: "Профиль",
  текст_вакансии: "Текст вакансии",
  опросник: "Опросник",
  ключевые_слова: "Ключевые слова",
  должность: "Должность",
  цкп: "ЦКП",
  "цкп (ценный конечный продукт - за что именно платятся деньги) должности": "ЦКП",
  подчинённые: "Подчинённые",
  бонус: "Бонус",
  образование: "Образование",
  семейное_положение: "Семейное положение",
  прочее: "Прочее",
  "что уже есть в резюме": "Что уже есть в резюме",
  категория: "Категория",
  уточняющие_вопросы: "Уточняющие вопросы",
  проверяет_требование: "Проверяет требование",
  "Прочие требования": "Прочие требования",
  подразделение: "Подразделение",
  непосредственный_руководитель: "Непосредственный руководитель",
  задачи: "Задачи",
  анкетные_требования: "Анкетные требования",
  обязательные_требования: "Обязательные требования",
  желательные_требования: "Желательные требования",
  психологические_черты: "Психологические черты",
  условия_работы: "Условия работы",
  возраст: "Возраст",
  пол: "Пол",
  стоп_факторы: "Стоп-факторы",
  навык: "Навык",
  описание: "Описание",
  качество: "Качество",
  проявление: "Проявление",
  формат: "Формат",
  режим: "Режим",
  зарплата: "Зарплата",
  испытательный_срок: "Испытательный срок",
  вопрос: "Вопрос",
  пример_ответа: "Пример ответа",
  name: "Название",
  title: "Название",
  city: "Город",
  phone: "Телефон",
  metro: "Метро",
  salary_expected: "Ожидания по зарплате",
  соответствие: "Соответствие",
  опыт_и_навыки: "Опыт и навыки",
  риски: "Риски",
  проверить_на_интервью: "Проверить на интервью",
  итог: "Итог",
};

export function hrStageLabel(stage: string | null | undefined): string {
  if (!stage) return "—";
  return HR_STAGE_LABELS[stage] || stage;
}

export function clientStatusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return CLIENT_STATUS_LABELS[status] || status;
}

/** Client-status line on card: don't say «ждёт оценки» if never sent / rejected by HR. */
export function clientStatusLabelForCard(
  hrStage: string,
  clientStatus: string | null | undefined,
): string {
  const status = (clientStatus || "wait").trim() || "wait";
  if (isRejectionStage(hrStage) && (status === "wait" || status === "new")) {
    return "Заказчику не показывался";
  }
  if (status === "wait" && !CLIENT_ZONE_STAGES.has(hrStage)) {
    return "В чат заказчика не отправлен";
  }
  return clientStatusLabel(status);
}

export function fieldLabel(key: string): string {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/\bhr\b/gi, "HR")
    .replace(/^\w/, (c) => c.toUpperCase());
}
