/** UI labels (RU). Keep storage keys in English; show Russian in UI. */

export const HR_STAGE_LABELS: Record<string, string> = {
  resume_screening: "Отсев резюме",
  primary_contact: "Первичный контакт",
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
};

/** Positive funnel for stage progress UI (excludes rejects / archive). */
export const HR_FUNNEL_STAGES = [
  "resume_screening",
  "primary_contact",
  "interview_scheduled",
  "interview_done",
  "test_task",
  "client_review",
  "client_pause",
  "client_meeting",
  "offer",
  "internship",
  "started_work",
] as const;

export const REJECTION_STAGES = new Set([
  "rejected",
  "rejected_candidate",
  "rejected_client",
  "rejected_hr",
]);

export function isRejectionStage(stage: string): boolean {
  return REJECTION_STAGES.has(stage);
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
