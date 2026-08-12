# DEVLOG — hr_ai_agent

Журнал разработки для восстановления контекста между сессиями AI/разработчика.  
Только факты: код, git, `data/`, `deploy/`.

---

## 2026-08-12 — Брендинг сайдбара + компактная шапка аналитики

**Тип:** `ui`

**Сделано:**
- В сайдбаре рядом с логотипом текст «HR-помогатор» (`RecruitingShell`, `.rec-logo`).
- Шапка «Аналитика»: заголовок и период слева, три режима — компактная горизонтальная строка справа (grid, без высокой колонки).
- Уменьшены отступы и шрифты mode-plaques в row-режиме.

**Файлы:** `RecruitingShell.tsx`, `stats/page.tsx`, `globals.css`

**Git:** (commit после push)

**Следующий шаг:**
- Деплой sidecar на hr-toolbox.ru.

---

## 2026-08-12 — Аналитика: закрытые вакансии по причинам + деплой sidecar

**Тип:** `feature` + `deploy`

**Сделано:**
- Режим «Взгляд руководителя»: блок «Закрытые вакансии по причинам» (успех / заказчик / без результата) + список вакансий.
- API `closed_breakdown` в `/stats/dashboard` (executive).
- Деплой на Timeweb: `feature/v2` → `/opt/hr_ai_agent/v2`, sidecar пересобран; health OK.

**Файлы:** `stats_service.py`, `schemas.py`, `stats/page.tsx`, `settings.py`, `offer_docx.py`, `CandidateOfferPanel.tsx`

**Git:** `e036bca` push `feature/v2`

**Следующий шаг:**
- Проверить `/stats` режим руководителя на hr-toolbox.ru.

---

## 2026-08-12 — Оффер: загрузка шаблона + история этапов rec-card

**Тип:** `feature` + `ui`

**Сделано:**
- API `GET/POST/DELETE /settings/offer-template` — свой `.docx` в `data/offer_template.docx`.
- UI в разделе «Оффер»: загрузка шаблона и возврат к встроенному.
- «История этапов» на вкладке воронки — отдельный `rec-card`.

**Файлы:** `offer_docx.py`, `settings.py`, `schemas.py`, `CandidateOfferPanel.tsx`, `CandidateEditor.tsx`, `OFFER_TEMPLATE.md`

**Git:** коммит + push

**Следующий шаг:**
- Загрузить фирменный шаблон и проверить Word.

---

## 2026-08-12 — Оффер Word: маркеры условий и срок в месяцах

**Тип:** `fix`

**Сделано:**
- Условия работы в Word — маркированный список с «•», как обязанности.
- Испытательный срок: в поле только число (`3` → «3 месяца» в письме).

**Файлы:** `offer_docx.py`, `offer_draft.py`, `CandidateOfferPanel.tsx`, `OFFER_TEMPLATE.md`

**Git:** незакоммичено

**Следующий шаг:**
- Скачать Word и проверить списки.

---

## 2026-08-12 — Скачивание оффера Word: кириллица в имени файла

**Тип:** `fix`

**Сделано:**
- Ошибка 500 при «Скачать Word»: `Content-Disposition` с русским именем не кодировался в latin-1.
- Добавлен `attachment_content_disposition`: ASCII fallback + `filename*=UTF-8''…`.

**Файлы:** `offer_docx.py`, `candidates.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить скачивание в карточке кандидата.

---

## 2026-08-12 — Оффер ИИ: таймаут прокси Next

**Тип:** `fix`

**Сделано:**
- `experimental.proxyTimeout: 180s` в `next.config.js` — «Дописать ИИ» больше не обрывается на 30 сек.
- Понятный статус ожидания в UI; шире перехват ошибок API.

**Файлы:** `next.config.js`, `CandidateOfferPanel.tsx`, `candidates.py`, `offer_draft.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить `npm run dev`, снова нажать «Дописать ИИ».

---

## 2026-08-12 — Раздел «Оффер» в карточке кандидата

**Тип:** `feature`

**Сделано:**
- Вкладка «Оффер»: черновик полей (в т.ч. ЗП+премия на ИС и после), сохранение в `payload.offer`.
- Кнопки: заполнить из данных, дописать ИИ (режим/обязанности), сохранить, скачать Word.
- Логотип компании → `clients.payload.offer_logo_data_url`, в колонтитул Word.
- Шаблон `app/assets/offer_template.docx` с плейсхолдерами под письмо.

**Файлы:** `offer_draft.py`, `offer_docx.py`, `candidates.py`, `schemas.py`, `CandidateOfferPanel.tsx`, `CandidateEditor.tsx`, `OFFER_TEMPLATE.md`, `offer_template.docx`

**Данные / конфиг:** `payload.offer`; `OFFER_TEMPLATE_PATH` (опц.)

**Git:** незакоммичено

**Следующий шаг:**
- Проверить на кандидате: вкладка Оффер → заполнить → Word.

---

## 2026-08-12 — Макет раздела «Оффер»

**Тип:** `ui` (макет)

**Сделано:**
- Страница-макет `/design-preview/offer`: вкладка «Оффер», поля письма, лого, обязанности, превью, кнопки авто/ИИ/Word.

**Файлы:** `design-preview/offer/page.tsx`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Согласовать макет → реализация боевого раздела в карточке.

---

## 2026-08-12 — Аватарки вакансий + оффер Word

**Тип:** `feature`

**Сделано:**
- Аватарки вакансий: тема по названию (12 иконок), показ в списке и шапке; ручной выбор в Настройках вакансии (`payload.avatar_key`).
- Оффер → Word: `GET /api/v1/candidates/{id}/offer.docx`, кнопка «Скачать оффер (Word)» во вкладке Воронка.
- Шаблон: `v2/backend/app/assets/offer_template.docx` (+ инструкция `OFFER_TEMPLATE.md`); опционально `OFFER_TEMPLATE_PATH` в `.env`.

**Файлы:** `vacancy_avatar.py`, `offer_docx.py`, `assets/OFFER_TEMPLATE.md`, `VacancyAvatar.tsx`, `VacancyCompactRow.tsx`, `VacancySettingsPanel.tsx`, `CandidateEditor.tsx`, `vacancies/[id]/page.tsx`, `vacancies.py`, `candidates.py`, `schemas.py`, `config.py`, `globals.css`, `.env.example`

**Данные / конфиг:** `OFFER_TEMPLATE_PATH` (опц.); `payload.avatar_key`

**Git:** незакоммичено

**Следующий шаг:**
- Подложить свой фирменный `offer_template.docx` по инструкции; проверить список вакансий и скачивание оффера.

---

## 2026-08-12 — Статистика: убрать dynamic ssr:false

**Тип:** `fix`

**Сделано:**
- На серверной `/stats` нельзя `next/dynamic` с `ssr: false` — вернули обычный импорт клиентского `StatsAiBriefPanel`.

**Файлы:** `stats/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Обновить `/stats`, проверить «Помощь ИИ».

---

## 2026-08-11 — Статистика: фикс ИИ + «Все компании»

**Тип:** `fix` + `ui`

**Сделано:**
- Плашка «Все компании» (`company=all`): статистика по всей организации без выбора одной компании.
- AI-brief: `client_id` необязателен (сценарий «все компании»).

**Файлы:** `stats/page.tsx`, `StatsAiBriefPanel.tsx`, `StatsPeriodEditor.tsx`, `schemas.py`, `stats_ai_brief.py`

**Git:** незакоммичено

**Следующий шаг:**
- Обновить страницу `/stats`, проверить «Помощь ИИ» и «Все компании».

---

## 2026-08-11 — Аналитика: режим «Помощь ИИ»

**Тип:** `feature`

**Сделано:**
- Третий режим на `/stats`: плашка «Помощь ИИ» — свободный запрос → структурированный расклад (KPI, блоки, шаги).
- API `POST /api/v1/stats/ai-brief`: контекст из dashboard (executive + attention), ответ через `chat_json`.
- UI: `StatsAiBriefPanel` (поле, примеры, расклад в `rec-card` / KPI).

**Файлы:** `stats_ai_brief.py`, `stats_history.py`, `schemas.py`, `StatsAiBriefPanel.tsx`, `stats/page.tsx`, `StatsPeriodEditor.tsx`, `globals.css`

**Данные / конфиг:** без новых env-ключей (тот же RouterAI / AI, что и остальные JSON-задачи)

**Git:** незакоммичено

**Следующий шаг:**
- Проверить на `/stats?mode=ai` с выбранной компанией: запрос → расклад.

---

## 2026-08-11 — Архив / Настройки / режим Анкеты

**Тип:** `ui`

**Сделано:**
- Архив вакансий: сортировка по дате закрытия — новые сверху.
- Все страницы `/settings/*` переведены на `RecruitingShell` (общий сайдбар); хаб настроек слегка в `rec-*`.
- Вкладки «Материалы» и «Воронка» у кандидата: просмотр по умолчанию, «Редактировать» как в Анкете.

**Файлы:** `vacancies/page.tsx`, `app/settings/**`, `CandidateEditor.tsx`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить `/settings`, архив вакансий, карточку кандидата (Материалы / Воронка).

---


**Тип:** `ui` + `feature`

**Сделано:**
- Режимы «Моя эффективность» / «Взгляд руководителя» — крупные плашки справа сверху.
- Период под заголовком: даты с–по + пресеты; API `from`/`to` + `period=custom`.
- Фильтр: Компания (плашки, по умолчанию ничего не выбрано) → Отдел → Вакансия → Область.
- Бэкенд: компания раскрывается в id компании + всех отделов для статистики.

**Файлы:** `stats/page.tsx`, `StatsPeriodEditor.tsx`, `stats_service.py`, `stats_history.py`, `globals.css`

**Данные / конфиг:** query `company`, `dept`, `from`, `to`

**Git:** незакоммичено

**Следующий шаг:**
- Открыть `/stats`, выбрать компанию, проверить период и отделы.

---


**Тип:** `ui`

**Сделано:**
- `/vacancies`: KPI `rec-dash-kpi`, вкладки `cand-tabs`, список через `VacancyCompactRow` вместо таблицы.
- `/stats`: KPI и секции в стиле рабочего стола; внимание/воронка/вакансии/возвраты — компактные `rec-row`; фильтры в `rec-card`.

**Файлы:** `vacancies/page.tsx`, `stats/page.tsx`, `VacancyCompactRow.tsx`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить обе страницы в браузере.

---


**Тип:** `ui`

**Сделано:**
- Шапка вакансии в `rec-card`: название, мета, чипы, кнопка «Закрыть вакансию» с подтверждением.
- Вкладки в стиле кандидата: Кандидаты / Документы / Поиск HH / Я.Диск / Настройки.
- Список кандидатов — `CandidateCompactRow` вместо таблицы.
- Настройки, сводка и удаление — во вкладке «Настройки»; закрытие/возврат — в шапке.

**Файлы:** `v2/frontend/app/vacancies/[id]/page.tsx`, `VacancyCloseButton.tsx`, `VacancyLifecycle.tsx`, `VacancySettingsPanel.tsx`, `VacancyTitleEditor.tsx`, `VacancyDigestButton.tsx`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить карточку вакансии в браузере (закрытие, список, вкладки).

---


**Тип:** `fix`

**Сделано:**
- После миграции на `RecruitingShell` на `/vacancies` вернули выбор клиента — chip-фильтр как на странице аналитики (боковая `ClientSidebar` больше не используется).

**Файлы:** `v2/frontend/app/vacancies/page.tsx`

**Git:** незакоммичено

---


**Тип:** `ui`

**Сделано:**
- Заменён `AppShell` на `RecruitingShell` на страницах jobs, stats, vacancies, history.
- Jobs: основной контент (stats, chip-row, panel, table) обёрнут в `rec-card`.
- History: весь контент обёрнут в `rec-card`.
- На `/vacancies` убран prop `sidebar` (RecruitingShell его не поддерживает); фильтр по клиенту через URL сохранён.

**Файлы:** `v2/frontend/app/jobs/page.tsx`, `stats/page.tsx`, `vacancies/page.tsx`, `vacancies/[id]/page.tsx`, `history/page.tsx`, `history/[id]/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- При необходимости вернуть фильтр клиентов на `/vacancies` через toolbar или inline-блок.

---

## 2026-08-11 — CandidateEditor: rec-card на вкладках воронка/интервью/заказчик/ИИ

**Тип:** `ui`

**Сделано:**
- Вкладки pipeline, interview, client, ai: внешние `CollapsibleCard` заменены на `div.rec-card` + `h3.rec-card-title`.
- Текст из `hint` перенесён в `<span className="muted hh-micro">` рядом с заголовком.
- Внутренний блок «История этапов» на вкладке воронки оставлен в `CollapsibleCard`.

**Файлы:** `v2/frontend/components/CandidateEditor.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- При необходимости — «История этапов» тоже перевести на rec-card.

---

## 2026-08-11 — UI гибрид v3: рабочий стол + sidebar + compact avatars

**Тип:** `ui`

**Сделано:**
- `/dashboard`: KPI (внимание, встречи сегодня, ждут заказчика) + очередь «Сегодня».
- `RecruitingShell`: «Рабочий стол» первым, «Аналитика», «Импорт» в «Ещё»; лого → `/dashboard`.
- Список кандидатов: строки ~56px, аватар 40px; `CandidateAvatar` — фото или силуэт M/F.
- Карточка кандидата на `RecruitingShell`; gender в API + извлечение из резюме.
- Backend: KPI `meetings_today`, `waiting_client`; `gender` в list/detail/attention.

**Файлы:** `app/dashboard/page.tsx`, `RecruitingShell.tsx`, `CandidateAvatar.tsx`, `CandidateCompactRow.tsx`, `DashboardQueue.tsx`, `globals.css`, `stats_service.py`, `candidate_fields.py`, `schemas.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перенести `/vacancies` и `/stats` на `RecruitingShell`.

---

## 2026-08-11 — Макет изначального плана UI (A+C)

**Тип:** `ui`

**Сделано:**
- Canvas и страница `/design-preview/plan`: рабочий стол, вакансии, кандидаты, карточка с вкладками, аналитика.
- Переключатель экранов; сравнение с компромиссом `/design-preview`.
- Ссылка «изначальный план» на странице компромисса.

**Файлы:** `canvases/ui-original-plan-pages.canvas.tsx`, `app/design-preview/plan/*`, `design-preview/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Выбор: план A+C vs компромисс sidebar.

---

## 2026-08-11 — Localhost: перезапуск API и frontend

**Тип:** `fix` (ops)

**Сделано:**
- Причина: backend на `:8000` не был запущен → страницы с `apiGet` падали с `fetch failed`; на `:3000` висел старый процесс Next.js с 500.
- Docker `db`/`redis` были живы; перезапущены `uvicorn` и `npm run dev`.
- Проверка: `/api/v1/health`, `/`, `/candidates`, `/design-preview` → 200.

**Git:** без коммита

**Следующий шаг:**
- При «не работает localhost» сначала проверить `:8000` и перезапустить оба dev-сервера.

---

## 2026-08-11 — Компромисс UI: sidebar + compact list

**Тип:** `ui`

**Сделано:**
- `RecruitingShell`: боковое меню 260px, палитра макета, «Ещё» для шаблонов/задач.
- Компактные строки с аватаром + группировка по этапам (сворачивание >6).
- `/candidates` переведён на новый layout; `/design-preview` показывает v2 + сравнение с карточками.

**Файлы:** `RecruitingShell.tsx`, `CandidateCompactRow.tsx`, `CandidatesGroupedList.tsx`, `groupCandidates.ts`, `globals.css`, `candidates/page.tsx`, `design-preview/*`

**Git:** незакоммичено

**Следующий шаг:**
- Утвердить; перенести shell на `/vacancies`, `/stats`.

---

## 2026-08-11 — Preview макета «Список кандидатов»

**Тип:** `ui`

**Сделано:**
- Статичная страница `/design-preview` по текстовой спецификации.
- CSS-модуль, lucide-react; `/design-preview` без auth.

**Файлы:** `app/design-preview/*`, `AuthGate.tsx`, `package.json`

**Git:** незакоммичено

**Следующий шаг:**
- Утверждение макета, перенос на `/candidates`.

---

## 2026-08-10 — Выжимка: показ из payload + UX

**Тип:** `fix`

**Сделано:**
- Выжимка в БД у Манаенковой уже была; UI мог не брать её с top-level поля.
- QuestionnairePanel читает `interview_digest` и из `payload`; нормализует q/a.
- После задачи собеседования открывается блок опросника и скролл к `#interview-digest`.
- Hint заголовка: «N вопросов · есть выжимка».

**Файлы:** `QuestionnairePanel.tsx`, `CandidateEditor.tsx`

**Следующий шаг:**
- Обновить карточку Манаенковой (жёсткое обновление страницы).

---

## 2026-08-11 — UI вкладки карточки + фото из PDF

**Тип:** `feature`

**Сделано:**
- Карточка кандидата: workspace-шапка (аватар, бейджи), вкладки Обзор/Анкета/Воронка/Интервью/Заказчик/ИИ вместо длинной простыни.
- Фото кандидата: `photo_extract.py` (PyMuPDF + OpenCV Haar), загрузка в S3 `photos/{id}.jpg`, `payload.photo_url`.
- Интеграция фото: inbox PDF, upload/bulk links, evaluate-resume; HH — URL из snapshot/API.
- UI: `CandidateAvatar` в шапке и списке кандидатов.

**Файлы:** `photo_extract.py`, `candidate_photo.py`, `CandidateEditor.tsx`, `CandidateAvatar.tsx`, `CollapsibleCard.tsx`, `globals.css`, `candidate_resume_eval.py`, `disk_inbox_router.py`, `hh_to_candidate.py`, `requirements.txt`

**Данные / конфиг:** `payload.photo_url`; нужны Yandex S3 ключи для PDF-фото

**Git:** незакоммичено

**Следующий шаг:**
- Рабочий стол `/dashboard` и перегруппировка top-nav (этап 2 UI).

---

## 2026-08-11 — ARCHITECTURE.md: актуализация + каталог функций

**Тип:** `docs`

**Сделано:**
- Обновлён `ARCHITECTURE.md`: стек (auth, Bitrix, client zone, interview digest), схема, ARQ jobs, навигация UI.
- Добавлен **каталог функций** (~70 пунктов) с ID, ролью, местом в UI и зрелостью — для перераспределения UI.
- Заметки: перегруз карточки кандидата, смешение операционки и настроек в «Поиск сотрудников».

**Файлы:** `ARCHITECTURE.md`

**Следующий шаг:**
- На основе каталога набросать группы UI (операции / sourcing / аналитика / админ).

---

## 2026-08-10 — UI /stats: аудит high-фиксы

**Тип:** `fix`

**Сделано:**
- Иерархия: режим — крупные tabs; область — chips + hint про «Закрыто» при «Только в работе».
- Полка фильтров, 8px rhythm, KPI без тени, скролл длинных chip-рядов.
- Empty states: attention / воронка / вакансии; даты периода; «Отчёт»; таблицы в overflow-wrap.
- Подписи графика DD.MM; select периода «Ещё».

**Файлы:** `v2/frontend/app/stats/page.tsx`, `StatsPeriodControls.tsx`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Глянуть `/stats` в браузере (оба режима + «Только в работе»).

---

## 2026-08-10 — Выжимка собеседования (вопрос–ответ)

**Тип:** `feature`

**Сделано:**
- После «Расшифровать и оценить» ИИ строит `interview_digest`: summary + пары вопрос→ответ + характеристика стиля речи (только для HR).
- В карточке кандидата выжимка сверху, полная расшифровка как раньше свёрнута.
- Публичная страница `/i/{token}` без логина; в Telegram/Bitrix — ссылка «Выжимка собеседования» (если задан `PUBLIC_APP_URL` или Bitrix `public_api_base`).
- Характеристика коммуникации на публичную страницу не попадает.

**Файлы:** `interview_digest.py`, `tasks.py`, `candidate_fields.py`, `card_html.py`, `gateway.py`, `inbound.py`, `bitrix/outbound.py`, `routes/interview_digest.py`, `QuestionnairePanel.tsx`, `app/i/[token]/page.tsx`, `AuthGate.tsx`, `JobsLive.tsx`, `globals.css`, `.env.example`

**Данные / конфиг:** payload `interview_digest` + `interview_digest_token`; опционально `PUBLIC_APP_URL`

**Git:** незакоммичено

**Следующий шаг:**
- На сервере задать `PUBLIC_APP_URL` (или уже есть `public_api_base`) и прогнать расшифровку на кандидате с записью.

---

## 2026-08-10 — Inbox: видео по ФИО → «Записи»

**Тип:** `feature`

**Сделано:**
- Inbox различает PDF и видео/аудио.
- PDF — как раньше: ИИ → папка «Резюме».
- Видео/аудио — **без скачивания**: матч кандидата по ФИО в имени файла → папка вакансии «Записи» + `video_link` (`yadisk-app:`).
- Нет матча → `_unsorted` с понятной причиной.
- Ручная привязка unsorted: видео → «Записи» (+ video_link при матче ФИО).

**Файлы:** `v2/backend/app/services/disk_inbox_router.py`

**Следующий шаг:**
- Положить в `_inbox` файл вида `Манаенкова Ирина.mp4` и запустить роутинг.

---

## 2026-08-10 — UX: отправка заказчику + перезапуск API

**Тип:** `fix`

**Сделано:**
- API завис на reload («Waiting for connections to close») — после клика «Отправить» казалось, что ничего не происходит.
- Принудительный перезапуск API + worker.
- Баннер результата отправки всегда сверху карточки; блок «Заказчик» раскрывается и прокручивается к нему.

**Файлы:** `CandidateEditor.tsx`

**Следующий шаг:**
- Обновить страницу и снова нажать «Отправить заказчику» у Манаенковой.

---

## 2026-08-10 — Fix: ссылка на резюме yadisk-app в Telegram/Bitrix

**Тип:** `fix`

**Сделано:**
- Резюме из inbox хранится как `yadisk-app:/…` — не открывается в Telegram (ссылка пропадала).
- При отправке заказчику путь конвертируется в публичный `https` (publish через OAuth при необходимости).
- В карточке Telegram/Bitrix в ссылку попадает только http(s); иначе fallback на HH.

**Файлы:** `yandex_disk_oauth.py`, `yandex_public.py`, `card_html.py`, `bitrix/outbound.py`

**Следующий шаг:**
- Переотправить карточку Манаенковой заказчику.

---

## 2026-08-10 — Async: оценка резюме + опросник (фоновая задача)

**Тип:** `feature`

**Сделано:**
- `POST …/evaluate-resume` → **202 + job** `candidate_evaluate_resume` (ARQ), как у расшифровки собеседования.
- Воркер: скачивание PDF → ИИ-оценка → опросник; прогресс в job.
- UI: кнопка «Оценить…», строка статуса, задача в «Задачи»; при возврате на карточку — восстановление активного job.
- Защита от двойного запуска (`reused`).
- API и ARQ worker перезапущены локально.

**Файлы:** `tasks.py`, `settings.py`, `common.py`, `candidates.py`, `CandidateEditor.tsx`, `QuestionnairePanel.tsx`, `JobsLive.tsx`, `jobs/page.tsx`

**Следующий шаг:**
- Проверить на Манаенковой: запуск → уйти в другой раздел → вернуться / «Задачи».

---

## 2026-08-10 — Fix: «Открыть» на «Оценить резюме ИИ»

**Тип:** `fix`

**Сделано:**
- Кнопка «Следующий шаг → Открыть» для «Оценить резюме ИИ» вела в `#ai-comment-block`, который не рендерится до первой оценки (`ai_score == null`) — клик ничего не делал.
- Следующий шаг теперь открывает блок «Опросник и собеседование» (`section: quest`), где кнопка «Оценить и сформировать опросник».

**Файлы:** `v2/frontend/lib/nextAction.ts`

**Риски:** нет

**Следующий шаг:**
- Проверить на карточке Манаенковой: «Открыть» прокручивает к опроснику.

---

## 2026-08-09 — Push: async generate + no_response_3d

**Тип:** `ops`

**Сделано:**
- Локально = функционал с сервера (generate async, этап «не отвечает», repair labels).
- Push `feature/v2`.

**Git:** commit `fc051b2` → `origin/feature/v2`

**Не в коммите:** `simple-russian.mdc`, favicon-prototype*.png

---

## 2026-08-09 — Fix: перепутанные подписи этапов (Lamoda)

**Тип:** `fix`

**Сделано:**
- На вакансии #15 сброшены подписи: `interview_scheduled` / `interview_done` / `no_response_3d` к каталогу (из‑за ручного переименования «Собеседование назначено» было на `interview_done` → не было даты/времени + дубль «не отвечает»).
- В `normalize_stage_schema` — автопочинка этой типичной путаницы.

**Файлы:** `stage_schema.py` (+ данные `vacancies.payload` на sidecar)

**Следующий шаг:**
- Обновить страницу кандидата; выбрать «Собеседование назначено» — появятся дата/время.

---

## 2026-08-09 — Домен hr-toolbox.ru LIVE

**Тип:** `ops`

**Сделано:**
- Let's Encrypt для `hr-toolbox.ru` + `www` (до 2026-11-07), auto-renew certbot.timer.
- nginx: HTTPS apex → sidecar `:8080`; www → `https://hr-toolbox.ru`; HTTP → HTTPS.
- Smoke: health/home/login 200; cookies Secure; pilot login `pilot@demo.ru` → Demo Sandbox.

**Данные / конфиг:** `/etc/nginx/sites-available/hr-toolbox`, `/etc/letsencrypt/live/hr-toolbox.ru/`, `.env.sidecar`

**Следующий шаг:**
- В Bitrix `public_api_base` = `https://hr-toolbox.ru` при необходимости.

---

## 2026-08-09 — Домен hr-toolbox.ru (частично)

**Тип:** `ops`

**Сделано:**
- Host nginx site `hr-toolbox` → `127.0.0.1:8080` (apex); www → apex (HTTP).
- certbot установлен; выпуск TLS **не прошёл**: LE валидирует чужой AAAA `2a00:f940:2:2:1:1:0:299` (404) + лишний A `31.31.197.50`.
- `.env.sidecar`: `PUBLIC_HOST=hr-toolbox.ru`, `AUTH_COOKIE_SECURE=true`, `CORS_ORIGINS=https://hr-toolbox.ru`; api перезапущен.

**Данные / конфиг:** `/etc/nginx/sites-available/hr-toolbox`, `.env.sidecar` (+ backup)

**Следующий шаг:**
- В Reg.ru удалить AAAA и лишний A `31.31.197.50`; оставить только A → `201.34.137.208`. Затем `certbot --nginx -d hr-toolbox.ru -d www.hr-toolbox.ru`.

---

## 2026-08-09 — Этап «не отвечает 3 дня» в каталоге

**Тип:** `feature`

**Сделано:**
- Новый HR-этап `no_response_3d` («Кандидат не отвечает более 3 дней») между первичным контактом и «Собеседование назначено».
- Без панели даты/времени (она только у `interview_scheduled`).
- Порядок в схеме вакансии, воронке UI и сортировке списка кандидатов.

**Файлы:** `candidate_write.py`, `stage_schema.py`, `vacancies.py`, `labels.ts`

**Git:** незакоммичено

**Следующий шаг:**
- На пилоте: обновить страницу схемы этапов; если «Собеседование назначено» было переименовано вручную — вернуть подпись.

---

## 2026-08-09 — Fix: перегенерация документа async (HTTP 500)

**Тип:** `fix`

**Сделано:**
- `POST .../documents/generate` → 202 + ARQ `vacancy_docs_generate` (proxy больше не рвёт долгий ИИ).
- UI `DocumentsEditor` поллит job и обновляет черновик.

**Файлы:** `vacancies.py`, `tasks.py`, `settings.py`, `common.py`, `DocumentsEditor.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- В пилоте: «Перегенерировать» опросник — ждать 1–2 мин без Internal Server Error.

---

## 2026-08-09 — Push: pilot + docs-from-brief

**Тип:** `ops`

**Сделано:**
- Локально синхронизировано с функционалом пилота/документов (серверные секреты/sidecar не трогали).
- Коммит и push `feature/v2`.

**Git:** commit `6ea569f` → `origin/feature/v2`

**Не в коммите:** `simple-russian.mdc`, favicon-prototype*.png

**Следующий шаг:**
- По необходимости — PR в main.

---

## 2026-08-09 — Опросник: порядок обязательных вопросов

**Тип:** `fix`

**Сделано:**
- В `QUESTIONNAIRE_RULES`: сначала причина поиска/ухода; в конце — вдохновляет / расстраивает / рекомендации; посередине skills/опыт.

**Файлы:** `v2/backend/app/services/document_generate.py`

**Git:** незакоммичено

**Следующий шаг:**
- Новые опросники уже с новым порядком (sidecar api/worker пересобраны).

---

## 2026-08-09 — from-brief: async job (fix HTTP 500)

**Тип:** `fix`

**Сделано:**
- `POST /vacancies/{id}/documents/from-brief` → 202 + ARQ job `vacancy_docs_from_brief` (ИИ ~1–2 мин больше не рвёт HTTP proxy).
- Worker task + регистрация в `WorkerSettings`.
- UI `DocumentsFromBrief` поллит `/api/v1/jobs/{id}` как «из материалов».
- Выложено на sidecar: api/web/worker rebuilt; worker видит `vacancy_docs_from_brief`.

**Файлы:** `vacancies.py`, `tasks.py`, `settings.py`, `common.py`, `DocumentsFromBrief.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- У пилота: «Собрать через ИИ» — ждать прогресс 1–2 мин, без HTTP 500.

---

## 2026-08-09 — Sidecar: ROUTERAI_API_KEY

**Тип:** `ops`

**Сделано:**
- В `/opt/hr_ai_agent/v2/.env.sidecar` добавлены `ROUTERAI_API_KEY` / `AI_API_KEY` (из локального корневого `.env`).
- Перезапущены api/worker; в контейнере ключ виден.
- В `.env.sidecar.example` добавлены поля AI.

**Данные / конфиг:** `.env.sidecar` на сервере (не в git)

**Следующий шаг:**
- Повторить «Собрать через ИИ» у пилота.

---

## 2026-08-09 — Форма «по вопросам» → всегда ИИ

**Тип:** `feature`

**Сделано:**
- Ответы формы идут в `generate_package_from_sources` (ИИ всегда).
- UI: «Собрать через ИИ», подсказка про ожидание 15–60 с.
- Выложено на sidecar.

**Файлы:** `documents_from_brief.py`, `vacancies.py`, `DocumentsFromBrief.tsx`

**Следующий шаг:**
- Проверить на вакансии пилота с ключом ИИ в `.env.sidecar`.

---

## 2026-08-09 — Шаблоны в Demo + документы по вопросам

**Тип:** `feature`

**Сделано:**
- 4 шаблона скопированы в Demo Sandbox (client 8) и в org владельца; список шаблонов фильтруется по org.
- Форма «Собрать документы по вопросам» (без ИИ) на вкладке документов вакансии.
- Выложено на sidecar.

**Файлы:** `documents_from_brief.py`, `DocumentsFromBrief.tsx`, `DocumentsEditor.tsx`, `seed_demo_templates.py`, `stats_history.py` (templates list)

**Данные / конфиг:** `vacancy_templates_seed.json` → сервер

**Следующий шаг:**
- Пилот: /templates и «Собрать по вопросам» на вакансии.

---

## 2026-08-08 — Fix: создание вакансии в пустой org (404)

**Тип:** `fix`

**Сделано:**
- Вакансия без клиента невидима в org → 404 после создания у пилота.
- При создании без клиента — авто «Моя компания» / root в org.
- На сервере: vac #16 привязана к «Demo Sandbox».

**Файлы:** `vacancy_write.py`, `clients_write.py`, `CreateVacancyForm.tsx`

**Следующий шаг:**
- Пилот открывает `/vacancies/16` или создаёт новую.

---

## 2026-08-08 — Fix: настройки пилота (путь data в Docker)

**Тип:** `fix`

**Сделано:**
- Падение «Способы добавления» у `pilot@demo.ru`: `parents[4]` в контейнере → 500.
- Починен `resolved_legacy_data_dir`; статус Я.Диска не роняет страницу.
- Выложено на sidecar (api+web).

**Файлы:** `config.py`, `yandex_disk_oauth.py`, `candidate-intake/page.tsx`

**Следующий шаг:**
- Обновить страницу у пилота и проверить настройки.

---

## 2026-08-08 — Demo Sandbox org + pilot на сервере

**Тип:** `feature`

**Сделано:**
- Новая пустая org «Demo Sandbox» + user `pilot@demo.ru` / `password123` (recruiter, Bitrix id `32`).
- Owner `owner@hr.local` в default org; YourBox-данные не трогали (3 clients).
- У recruiter Telegram — заглушка «Недоступно»; Bitrix только чтение; задачи пилота → Bitrix user 32.
- Код выложен, api/web/worker пересобраны.

**Файлы:** `users.py`, `create_demo_sandbox.py`, `auth.py`, `app_settings.py`, UI settings/channels/calendar, alembic `g7h8i9j0k1l2`

**Данные / конфиг:** сервер `/opt/hr_ai_agent/v2`; логин пилота выше

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Войти пилотом на `:8080` и проверить пустой кабинет + настройки.

---

## 2026-08-08 — Sidecar: pilot YourBox subset

**Тип:** `ops`

**Сделано:**
- Собрали урезанный снимок из локальной PG: YourBox (Маркетинг+Продажи), 3 вакансии, 55 кандидатов.
- Архив: «Графический дизайнер» (41), «Нейро-дизайнер» (12); активная: «Менеджер по маркетплейсам (Lamoda)» (2).
- Залили на Timeweb (`import_json --replace`), подняли дерево YourBox; owner@hr.local сохранён.
- Локально: `data_pilot_yourbox/` (+ в `.gitignore` как `data_pilot*/`).

**Файлы:** `data_pilot_yourbox/` (не в git), `.gitignore`

**Данные / конфиг:** сервер `/opt/hr_ai_agent/v2/data_pilot_yourbox`; users не трогали

**Git:** без коммита данных

**Следующий шаг:**
- Второй user в той же org (recruiter): без Telegram в хабе, Bitrix как сейчас.

---

## 2026-08-08 — Commit + push: intake, UX, sidecar

**Тип:** `chore`

**Сделано:**
- Закоммичены и запушены на `origin/feature/v2` изменения до/после sidecar-деплоя.
- В gitignore: `.env.sidecar`, `.env.prod` (секреты не в репо).
- Прототипы favicon оставлены локально untracked.

**Файлы:** `v2/` (intake, Disk panels, themes, notify/calendar, Zoom alembic, `docker-compose.sidecar.yml`, brand assets), `.cursor/DEVLOG.md`

**Данные / конфиг:** `.env.sidecar` на сервере не пушили

**Git:** `04b5086` на `origin/feature/v2`

**Следующий шаг:**
- Логин owner на `http://IP:8080`; после домена — TLS + prod compose.

---

## 2026-08-08 — v2: sidecar-деплой рядом с LexForge (Timeweb)

**Тип:** `deploy`

**Сделано:**
- На `201.34.137.208` поднят HR v2 sidecar: UI `http://IP:8080`, свои db/redis/api/worker/web.
- LexForge не трогали (nginx/systemd/docker lexforge живы).
- Compose: `docker-compose.sidecar.yml`, `APP_ENV=pilot`, cookies без Secure (до домена/TLS).
- Smoke: UI 200, `/api/v1/health` ok; available RAM ~2.5 Gi.

**Файлы:** `v2/docker-compose.sidecar.yml`, `v2/.env.sidecar.example`, `v2/DEPLOY.md` (+ фикс alembic zoom path на сервере)

**Данные / конфиг:** `/opt/hr_ai_agent/v2/.env.sidecar` на сервере (не в git)

**Git:** вошло в `04b5086`

**Следующий шаг:**
- Проверить логин owner; после покупки домена — TLS + `docker-compose.prod.yml`.

---

**Тип:** `ux`

**Сделано:**
- Zoom у пользователя без длинного описания; календарь — opt-in + пошаговая инструкция, без путей к файлам.
- Чекбоксы уведомлений ×3, зелёная подсветка блока при включении; default `google_calendar_enabled=false`.
- Хаб: статусы «взаимодействие» и «уведомления» как у intake; обновлено «Описание функционала».

**Файлы:** `calendar/page.tsx`, `notify_prefs.py`, `routes/auth.py`, `settings/page.tsx`, `about/page.tsx`, `globals.css`

**Git:** вошло в `04b5086`

**Следующий шаг:**
- Проверить хаб и страницу уведомлений под обычным пользователем.

---

**Тип:** `ux`

**Сделано:**
- В «Внешний вид» три темы: коричнево-зелёная (`earth`), оранжево-белая (`citrus`), бело-синяя (`sky`).
- В сайдбаре кнопка полезных ссылок: «Добавить сервис» вместо «+ Своя».

**Файлы:** `UiPrefsProvider.tsx`, `AppearanceSettings.tsx`, `globals.css`, `settings/page.tsx`, `UsefulLinksBar.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Выбрать новую тему в настройках и проверить сайдбар.

---

## 2026-08-08 — v2: предупреждение «настройте Диск ниже»

**Тип:** `ux`

**Сделано:**
- На блоках sync/inbox при включении без OAuth Диска — предупреждение про настройку подключения ниже.
- Статус `connected` обновляется после сохранения/отвязки токена.

**Файлы:** `candidate-intake/page.tsx`, `YandexDiskConnectPanel.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Включить sync без токена и проверить исчезновение warn после «Сохранить токен».

---

**Тип:** `ux`

**Сделано:**
- Чекбоксы заменены на кликабельные блоки: зелёный «Подключено» / светло-красный «Отключено», подсказки «Нажмите для…».
- «Основные» — всегда зелёные, «Подключено по умолчанию».
- В хабе настроек карточка intake: столбик статусов (Вручную / По ссылке / Через Яндекс Диск + sync/роутинг).

**Файлы:** `candidate-intake/page.tsx`, `settings/page.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Проверить клики на intake и обновление статусов в хабе после возврата.

---

## 2026-08-08 — v2: inbox-роутинг заполняет анкету (город/email/возраст)

**Тип:** `fix`

**Сделано:**
- Роутер inbox извлекает email, age, city, metro, salary и пишет их в кандидата (раньше только phone).
- То же при ручной привязке из unsorted.

**Файлы:** `disk_inbox_router.py`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Уже созданных Манаенкову/Васильеву — «Оценить по резюме» или заполнить вручную; новые из inbox получат поля сразу.

---

## 2026-08-08 — v2: кнопка Inbox в верхней навигации

**Тип:** `feature`

**Сделано:**
- В панели поиска (рядом с Вакансии/Кандидаты…) кнопка «Inbox» — ручной роутинг `_inbox` → вакансии.
- Автомониторинг пока не делали (по решению).

**Файлы:** `InboxRouteNavButton.tsx`, `AppShell.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- При необходимости — автомониторинг с тоглом в настройках Диска.

---

## 2026-08-08 — v2: Я.Диск — фикс «Получить ключ» (popup)

**Тип:** `fix`

**Сделано:**
- `window.open` сразу по клику (до await) — иначе браузер блокирует окно.
- Запасная кнопка/ссылка «Открыть вручную» + полный URL под кнопкой.

**Файлы:** `yandex-disk/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-08 — v2: Я.Диск — инструкция шаг 3 (доп. доступы)

**Тип:** `ux`

**Сделано:**
- Шаг 2: убрано «нажать +»; шаг 3: не трогать «Основные», Диск — через «Дополнительные» / название доступа.

**Файлы:** `yandex-disk/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-08 — v2: Я.Диск — инструкция шаг 2 (Redirect URI)

**Тип:** `ux`

**Сделано:**
- В инструкции расписаны все 4 шага; на шаге 2 — Redirect URI `https://oauth.yandex.ru/verification_code` и Hostname.
- В ссылку «Получить ключ» добавлен тот же `redirect_uri`.

**Файлы:** `yandex-disk/page.tsx`, `yandex_disk_oauth.py`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-08 — v2: Я.Диск — инструкция про 4 шага создания приложения

**Тип:** `ux`

**Сделано:**
- В инструкции: шаг 1 — только название/почта; доступы Диска — на следующих шагах мастера.

**Файлы:** `yandex-disk/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-08 — v2: Я.Диск — отвязка + инструкция по своим папкам

**Тип:** `feature` / `ux`

**Сделано:**
- `POST /integrations/yandex-disk/disconnect` — локальный сброс токена, Client ID, путей (дефолты); Диск не чистит.
- UI: «Отвязать Диск» + подтверждение; блок «Папки на Диске» с правилами кастомных путей и валидацией.

**Файлы:** `yandex_disk_oauth.py`, `integrations.py`, `yandex-disk/page.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Проверить отвязку и смену корня/inbox на стенде.

---

## 2026-08-08 — v2: Я.Диск — уточнение инструкции OAuth

**Тип:** `ux`

**Сделано:**
- В инструкции: тип «Для авторизации пользователей»; доступы disk.app_folder / disk.read / disk.write.

**Файлы:** `yandex-disk/page.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-08 — v2: Я.Диск — Client ID + пошаговая OAuth-инструкция

**Тип:** `ux` / `feature`

**Сделано:**
- Поле Client ID, кнопка «Создать приложение на Яндексе», «Получить ключ» только при заполненном ID.
- Client ID в `app_settings.json` через PATCH `/settings/app` (`yandex_disk_client_id`).
- Пошаговая инструкция на русском в блоке «Подключение».

**Файлы:** `yandex-disk/page.tsx`, `yandex_disk_oauth.py`, `app_settings.py`, `schemas.py`, `settings.py`, `globals.css`

**Данные / конфиг:** ключ `yandex_disk_client_id` в app_settings

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Пройти OAuth по новой инструкции на стенде.

---

## 2026-08-08 — v2: Zoom Concierge — токены per-org в БД

**Тип:** `feature`

**Сделано:**
- `organizations.integrations` JSONB; Alembic `e5f6a7b8c9d0` (+ перенос legacy `zoom_oauth_token.json` в default org, если был).
- `zoom_oauth`: `get/save_zoom_token(org_id)`; Client ID/Secret по-прежнему из `.env`.
- OAuth status/start/complete — только `platform_owner`, токен пишется в org текущего админа.
- Создание встречи берёт Zoom-токен org кандидата.
- UI: «подключено для компании»; non-owner видит locked-текст.

**Файлы:** `models.py`, `e5f6a7b8c9d0_*.py`, `zoom_oauth.py`, `zoom_meetings.py`, `integrations.py`, `calendar/page.tsx`, `.env.example`

**Данные / конфиг:** колонка `organizations.integrations`; `ZOOM_CLIENT_*` без изменений

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Подключить Zoom под platform_owner и проверить встречу у recruiter той же org.

---

## 2026-08-08 — v2: кто вошёл — рядом с «Выйти»

**Тип:** `ux`

**Сделано:**
- Справа от «Выйти» показывается имя пользователя (или email), tooltip — email если имя другое.

**Файлы:** `AppShell.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-08 — v2: логотип рядом с названием ×2

**Тип:** `ux`

**Сделано:**
- Логотип у «HR-помогатор» увеличен в 2 раза: topbar 32→64 / home 40→80; герой главной 48→96; логин 36→72.

**Файлы:** `AppShell.tsx`, `page.tsx`, `login/page.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Визуально проверить topbar на узком экране.

---

## 2026-08-08 — v2: Zoom User OAuth + назначение встречи

**Тип:** `feature`

**Сделано:**
- Zoom User OAuth: status / start / complete API; токен в `LEGACY_DATA_DIR/zoom_oauth_token.json`.
- `POST /candidates/{id}/zoom-meeting` — создание встречи, сохранение `join_url` в payload.
- Карточка кандидата: «Назначить встречу» → модалка → Zoom; «Скопировать приглашение» + `mailto` (без SMTP).
- Опциональный `email` в анкете; автозаполнение из парсера резюме; кнопка Email неактивна без адреса.
- Настройки уведомлений: блок Zoom OAuth (как Google Calendar).

**Файлы:** `zoom_oauth.py`, `zoom_meetings.py`, `integrations.py`, `candidates.py`, `schemas.py`, `config.py`, `candidate_fields.py`, `candidate_write.py`, `candidate_resume_eval.py`, `CandidateEditor.tsx`, `settings/calendar/page.tsx`, `.env.example`

**Данные / конфиг:** `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_REDIRECT_URI` (default `http://localhost:8765/`)

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Заполнить Zoom credentials в `.env`, пройти OAuth, проверить создание встречи на карточке.

---

## 2026-08-08 — v2: зависла генерация документов (вакансия 15)

**Тип:** `fix` / `ops`

**Сделано:**
- Причина: job `vacancy_docs_from_materials` висел в `queued` — не был запущен `arq` worker.
- Запущен arq; задача `e06d7af5-…` для вакансии 15 («Менеджер по маркетплейсам») завершилась `completed`, документы записаны (profile/questions/vacancy_text/keywords).

**Данные / конфиг:** Redis queue + PG job; Excel в `data/tmp/vacancy_docs/…` на месте

**Git:** незакоммичено

**Следующий шаг:**
- Держать `arq` запущенным вместе с API при локальной работе.

**Тип:** `fix` / `ux`

**Сделано:**
- InfoTip больше не режется `overflow` у CollapsibleCard.
- Bitrix в каналах связи для non-owner: только текст «В данной версии настройки не редактируются».
- Убрано слово «Заглушка» у WhatsApp/Max.
- `LockedTextField` + locked Chat ID по умолчанию; TG/тест-чат без префилла; название-пример «Тестовый».

**Файлы:** `globals.css`, `LockedTextField.tsx`, `CommunicationChannelsPanel.tsx`, `TestChatSettings.tsx`, `ChatIdField.tsx`, `CompanyEditor.tsx`, `calendar/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Zoom «Назначить встречу» — после уточнений; инструкция смены бота — в ответе пользователю.

**Тип:** `feature`

**Сделано:**
- Хаб: переименованы карточки (Я.Диск, внешний вид, взаимодействие, уведомления); about и тест-чат убраны из хаба.
- Левая панель: отдельно «Основные настройки» и «Описание функционала».
- «Настройка взаимодействия»: flow компания→подразделения, нейтральные плейсхолдеры, каналы Bitrix/Telegram + stubs WA/Max, тестовый чат внутри.
- Chat ID: закрыты по умолчанию, правка через «Изменить» → «Ок».
- «Настройка уведомлений»: GC по умолчанию вкл.; Telegram личный — opt-in + prefs API; stubs WA/Max.
- InfoTip по ключевым полям; `users.notify_prefs` + migration/ensure.

**Файлы:** `settings/page.tsx`, `SettingsRail.tsx`, `CompaniesSettings.tsx`, `CompanyEditor.tsx`, `ChatIdField.tsx`, `CommunicationChannelsPanel.tsx`, `calendar/page.tsx`, `auth.py`, `notify_prefs.py`, `models.py`, alembic `c4d5e6f7a8b9_*`

**Данные / конфиг:** колонка `users.notify_prefs` (JSONB)

**Git:** незакоммичено на `feature/v2`

**Риски/регрессии:**
- Если API/Postgres держат lock — перезапустить uvicorn, чтобы `ensure_notify_prefs_column` применился.
- Отправка личных TG-дайджестов по prefs пока сохраняется в UI/API; wiring в tick — следующий шаг при необходимости.

**Следующий шаг:**
- Перезапустить API при необходимости и пройти сценарий рекрутером: `/settings` → взаимодействие → уведомления.

---

## 2026-08-07 — v2: демо-пространство обычного рекрутера

**Тип:** `chore` (+ `fix` tenancy)

**Сделано:**
- Создана пустая org `demo-recruiter-empty` и пользователь `recruiter@local.test` / `recruiter1` (`hr_recruiter`).
- Вход проверен: 0 клиентов/вакансий/кандидатов; без пунктов «Задачи»/«История».
- Исправлен leak: `GET /stats/import` считает counts по org, а не глобально.

**Файлы:** `stats_history.py` (counts по tenancy); данные в PG (org + user)

**Данные / конфиг:** org slug `demo-recruiter-empty`; email `recruiter@local.test`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Ознакомиться в UI: http://localhost:3000/login

---

## 2026-08-07 — v2: опечатка в бренде на главной

**Тип:** `fix`

**Сделано:**
- В home-варианте `AppShell`: «HR-памагатор» → «HR-помогатор».

**Файлы:** `AppShell.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-07 — v2: синий лого + в шапке рядом с названием

**Тип:** `chore`

**Сделано:**
- Лого перерисовано: яркий синий фон, белые ладони + 3 силуэта.
- Favicon укрупнён: master `app/icon.png` 1024px, добавлен `favicon-48.png`, 512/180/32/16.
- `BrandLogo` рядом с «HR-помогатор» в topbar (`AppShell`), на главной и на логине.

**Файлы:** `BrandLogo.tsx`, `AppShell.tsx`, `page.tsx`, `login/page.tsx`, `layout.tsx`, `globals.css`, `public/logo.png`, `public/favicon-*.png`, `app/icon.png`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Hard-refresh (Cmd+Shift+R), если вкладка показывает старый favicon.

---

## 2026-08-07 — v2: вернуть бренд HR-помогатор

**Тип:** `fix`

**Сделано:**
- Восстановлено «HR-помагатор» в UI (ошибочно убрали префикс HR).

**Файлы:** `layout.tsx`, `AppShell.tsx`, `page.tsx`, `login/page.tsx`, `about/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Favicon — после отдельного одобрения прототипа.

---

## 2026-08-07 — v2: бренд «помогатор» (+ favicon prototype)

**Тип:** `chore`

**Сделано:**
- UI-бренд переименован: «HR-помогатор» → «помогатор» (title, shell, login, about, home).
- Показан прототип favicon (ещё не установлен в `public/`).

**Файлы:** `layout.tsx`, `AppShell.tsx`, `page.tsx`, `login/page.tsx`, `about/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Одобрить favicon и положить в `frontend/public/`.

---

## 2026-08-07 — v2: текст карточки «Поиск сотрудников»

**Тип:** `chore`

**Сделано:**
- Обновлено описание блока «Поиск сотрудников» на главной.

**Файлы:** `app/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- —

---

## 2026-08-07 — v2: settings rail + тексты модулей

**Тип:** `feature`

**Сделано:**
- «Основные настройки» → компактный sticky SettingsRail слева на всех страницах; подпись «Внешний вид и инструменты».
- Главная: обновлены названия/описания модулей; убран HR-брендинг и карточка настроек с контента.

**Файлы:** `SettingsRail.tsx`, `AppShell.tsx`, `page.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Smoke главной и `/vacancies` — rail сверху сайдбара.

---

## 2026-08-07 — v2: главная — карта модулей портала

**Тип:** `feature`

**Сделано:**
- Главная: крупный «Поиск сотрудников»; 5 модулей «скоро» по схеме портала; компактная «Основные настройки».
- Убрана заглушка «Разработка документов»; ИПР расшифрован в тексте.

**Файлы:** `app/page.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Смоук главной на `/`.

---

## 2026-08-07 — v2: Задачи/История только owner

**Тип:** `chore`

**Сделано:**
- Вкладки «Задачи» и «История» в topbar только для `platform_owner`.

**Файлы:** `AppShell.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- При желании — OwnerOnly на самих `/jobs` и `/history`.

---

## 2026-08-07 — v2: add candidate tabs + provider links + InfoTip

**Тип:** `feature`

**Сделано:**
- Owner-only ссылки RouterAI/Я.Облако в сайдбаре и на `/settings/ai`.
- «Добавить кандидата»: вкладки Вручную / По ссылкам / Из файла; отдельный BulkLinks убран.
- `POST /vacancies/{id}/candidates/from-file` (pdf/docx/txt…) → extract → карточка.
- `InfoTip` (кружок i); убраны тех. пояснения (Smart-inbox, ключи этапов и т.п.) в затронутых местах.

**Файлы:** `AddCandidateForm.tsx`, `ClientSidebar.tsx`, `settings/ai`, `stats/page`, `VacancyStageSchemaPanel`, `InfoTip.tsx`, `candidate_resume_eval.py`, `vacancies.py` routes; удалён `BulkLinksForm.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Smoke: owner видит провайдеров; upload PDF на вакансии; InfoTip на «Требуют внимания».

---

## 2026-08-07 — v2: stats периоды + hide meeting link

**Тип:** `feature`

**Сделано:**
- Период на обоих табах: chips + select 1/2/3/6/12 мес.; operational default `week` (пн→сейчас), ещё mtd/ytd; executive — week/month/all + months.
- Default scope = «Только в работе» (`scope` отсутствует или не `all`).
- UI ссылки Zoom/Телемост и чекбокса в карточке кандидата скрыт (`{false && …}`), state/save сохранены.

**Файлы:** `stats_service.py`, `routes/stats_history.py`, `stats/page.tsx`, `StatsPeriodControls.tsx`, `CandidateEditor.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Smoke `/stats` смена периода и default «в работе».

---

## 2026-08-07 — v2: stats dashboard (2 режима + гарантия)

**Тип:** `feature`

**Сделано:**
- `GET /api/v1/stats/dashboard?mode=operational|executive&period=week|month|all` (+ client/vacancy/scope).
- Tab «Моя эффективность»: KPI сейчас, активность 14д, smart attention, HH accordion.
- Tab «Отчет руководителю»: KPI закрытий/найма/срока/конверсии, flow-воронка, таблица вакансий.
- Блок «Риски и гарантия»: возвраты (hire→reject в срок warranty.months), гарантийные поиски + multi-hire; реестр гарантий внизу Tab 2.

**Файлы:** `stats_service.py`, `schemas.py`, `routes/stats_history.py`, `stats/page.tsx`, `CollapsibleHhBlock.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Smoke `/stats` оба таба; проверить возвраты на данных с историей этапов.

---

## 2026-08-07 — v2: сервисы в сайдбар + свернуть Клиент

**Тип:** `feature`

**Сделано:**
- Кнопки сервисов перенесены из topbar в левый сайдбар под блок «Клиент» (заголовок «Сервисы»).
- Блок «Клиент» сворачивается (▾/▸), состояние в localStorage; в свёрнутом виде виден текущий фильтр.
- На страницах без клиентского сайдбара (главная, настройки) лаунчер не показывается.

**Файлы:** `ClientSidebar.tsx`, `UsefulLinksBar.tsx`, `AppShell.tsx`, `globals.css`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Smoke: свернуть/развернуть Клиент; клик по сервисам на `/vacancies`.

---

## 2026-08-07 — v2: скрыть «Общение с кандидатом»

**Тип:** `chore`

**Сделано:**
- Убрана карточка «Общение с кандидатом» из хаба `/settings` (раздел сырой; страница `/settings/candidate-comms` не удалена).

**Файлы:** `frontend/app/settings/page.tsx`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Доработать candidate-comms и вернуть в хаб.

---

## 2026-08-07 — v2: полезные ссылки (лаунчер)

**Тип:** `feature`

**Сделано:**
- Заменён «Быстрый доступ» (🔒 → настройки) на блок «Полезные ссылки» в topbar на всех страницах.
- Предустановки: Телемост, Zoom (`app.zoom.us`), Google Диск, Яндекс Диск — всегда открывают ресурс в новой вкладке.
- Свои кнопки per-user (`users.useful_links` JSONB + `GET/PUT /auth/useful-links`); при AUTH_DISABLED — localStorage.
- Settings sidebar без quick-access (шире контент настроек).

**Файлы:** `UsefulLinksBar.tsx`, `AppShell.tsx`, `globals.css`, `lib/api.ts`, `models.py`, `useful_links.py`, `routes/auth.py`, `schemas.py`, alembic `b3c4d5e6f7a8_*`; удалён `QuickAccessLinks.tsx`

**Данные / конфиг:** миграция `users.useful_links`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Прогнать alembic upgrade; smoke: добавить/удалить свою кнопку под реальным логином.

---

## 2026-08-06 — v2: Wave E UI polish

**Тип:** `feature`

**Сделано:**
- Ребрендинг UI → «HR-помогатор».
- Быстрый доступ Zoom/Телемост/Диск в settings sidebar (🔒 → настройки).
- RBAC: owner-only AI/Bitrix/Telegram/Гарантия/Функции + PATCH guards.
- Inline rename вакансии; ручные вопросы опросника + merge `is_manual` при regenerate.

**Файлы:** `AuthGate.tsx`, `QuickAccessLinks.tsx`, `VacancyTitleEditor.tsx`, `AppShell`, settings/*, `QuestionnairePanel`, `candidate_questionnaire.py`, `auth.py`, `routes/settings.py`, `vacancies`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Коммит Wave E; smoke RBAC + опросник merge.

---

## 2026-08-06 — v2: D5 Polish / deploy

**Тип:** `feature`

**Сделано:**
- Production fail-fast (JWT_SECRET + AUTH_COOKIE_SECURE).
- `docker-compose.prod.yml` + `deploy/nginx.conf` (TLS, SSE buffering off).
- `DEPLOY.md`, `.env.production.example`; login hint; alembic on API boot.

**Файлы:** `core/startup.py`, `main.py`, `Dockerfile`, `docker-compose.prod.yml`, `deploy/*`, `DEPLOY.md`, `.env.production.example`, `login/page.tsx`, `AUDIT.md`

**Данные / конфиг:** prod env keys в `.env.production.example` (не коммитить `.env.prod`)

**Git:** незакоммичено на `feature/v2` (после `f7c229b`)

**Следующий шаг:**
- Заполнить `.env.prod` + сертификаты; `compose … up`; или коммит D5.

---

## 2026-08-06 — v2: commit D1–D4 + бриф D5

**Тип:** `git` / `docs`

**Сделано:**
- Commit `f7c229b` — D1 Auth, D2 Tenancy/client zone, D3 Bitrix providers, D4 SSE jobs.
- Бриф D5 Polish/deploy в `AUDIT.md` (ждёт одобрения).

**Файлы:** весь v2 D1–D4; `v2/AUDIT.md`, `.cursor/DEVLOG.md`

**Git:** `f7c229b` на `feature/v2` (не запушено)

**Следующий шаг:**
- Одобрение D5 + ответы по неоднозначностям → код.

---

## 2026-08-06 — v2: demo job stuck (worker + tenancy)

**Тип:** `fix`

**Сделано:**
- Demo/orphan jobs без vacancy/client при создании получают `client_id` org — иначе пропадали из списка после D2.
- Причина «сразу прерывается»: ARQ worker не был запущен + job не виден в org filter.

**Файлы:** `api/v1/routes/jobs.py`

**Следующий шаг:**
- Держать `arq app.workers.settings.WorkerSettings` запущенным; повторить «Запустить демо».

---

## 2026-08-06 — v2: D4 SSE jobs widget

**Тип:** `feature`

**Сделано:**
- `GET /api/v1/events/stream` (org jobs, poll ~1.5s, heartbeat, X-Accel-Buffering: no).
- Next rewrite `/api/v1/*` → API; browser API base = same-origin.
- Topbar badge активных задач + toast complete/fail; pollers не трогали.

**Файлы:** `routes/events.py`, `router.py`, `next.config.js`, `lib/api.ts`, `JobsLive.tsx`, `AppShell.tsx`, `layout.tsx`, `globals.css`, `docker-compose.yml`, `AUDIT.md`

**Данные / конфиг:** `API_REWRITE_URL`, `API_INTERNAL_URL` в `.env.example`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Перелогиниться (cookies теперь на :3000); smoke demo_progress; бриф D5.

**Риски/регрессии:**
- После перехода на same-origin нужен повторный логин (старые cookies были на :8000).

---

## 2026-08-06 — v2: бриф D4 SSE jobs widget

**Тип:** `docs`

**Сделано:**
- Бриф D4 в `AUDIT.md`: SSE stream + глобальный виджет/toast; 4 неоднозначности (transport, push source, UX, pollers).

**Файлы:** `v2/AUDIT.md`, `.cursor/DEVLOG.md`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Одобрение D4 + ответы по неоднозначностям → код.

---

## 2026-08-06 — v2: login error UX + missing user

**Тип:** `fix`

**Сделано:**
- Login больше не показывает сырой JSON (`Invalid credentials` → «Неверный email или пароль»).
- Создан локальный user `dialex307@gmail.com` (его не было в БД).

**Файлы:** `frontend/lib/api.ts`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Войти новым аккаунтом; далее бриф D4 или коммит.

---

## 2026-08-06 — v2: D3 Bitrix + provider registry

**Тип:** `feature`

**Сделано:**
- MessagingProvider registry (bitrix/web/telegram + WhatsApp/Max stubs); UI из каталога.
- `client_notify` default + one-shot migrate → `["bitrix","web"]`; gateway через адаптеры.
- HR Telegram notify только при outbound + `TELEGRAM_HR_USER_ID`.
- `POST /settings/bitrix/test-task` + кнопка в settings.
- CandidateEditor fallback channels → bitrix+web.

**Файлы:** `messaging/providers/*`, `gateway.py`, `app_settings.py`, `routes/settings.py`, `bitrix/outbound.py`, `frontend/.../bitrix/page.tsx`, `AUDIT.md`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Бриф D4 (SSE jobs) или коммит D1–D3.

---

## 2026-08-06 — v2: бриф D3 Bitrix + Telegram flag

**Тип:** `decision`

**Сделано:**
- Бриф D3 в `AUDIT.md`: Bitrix-first client notify; Telegram gated; HR-notify опционально; checklist Bitrix.
- Код D3 не писали.

**Файлы:** `v2/AUDIT.md`, `.cursor/DEVLOG.md`

**Следующий шаг:**
- Одобрение брифа D3 (ответы 1–4) → реализация.

---

## 2026-08-06 — v2: D2 Tenancy + Client zone

**Тип:** `feature`

**Сделано:**
- Org isolation: helpers + 404 IDOR; lists/stats/jobs/history/search scoped by `organization_id`.
- Client zone: public token URL `/c/{token}`, decide ready/think/reject + meeting; rotate token в карточке компании.
- Middleware ContextVar для Request → tenancy в sync handlers.

**Файлы:** `services/tenancy.py`, `client_zone.py`, `routes/client_zone.py`, `main.py`, routes/*, frontend `/c/[token]`, `CompanyEditor`, `AUDIT.md`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Бриф D3 (Bitrix + Telegram feature flag).

---

## 2026-08-06 — v2: бриф D2 Tenancy + Client zone

**Тип:** `decision`

**Сделано:**
- Бриф D2 в `AUDIT.md`: слой A org_id isolation; слой B web client zone; 5 неоднозначностей на одобрение.
- Код D2 не писали.

**Файлы:** `v2/AUDIT.md`, `.cursor/DEVLOG.md`

**Следующий шаг:**
- Одобрение брифа D2 (ответы 1–5) → реализация.

---

## 2026-08-06 — v2: D1 Auth (JWT cookies)

**Тип:** `feature`

**Сделано:**
- Users / org members / refresh_tokens; Alembic `a1b2c3d4e5f6`.
- Login/refresh/logout/me; httpOnly cookies; protected API (health + webhooks public).
- `AUTH_DISABLED` (non-production), bootstrap env + `create_user` CLI.
- Frontend `/login`, AuthGate, `apiFetch` credentials + SSR cookies, logout.

**Файлы:** `v2/backend/app/core/auth.py`, `services/users.py`, `api/v1/routes/auth.py`, `router.py`, `models.py`, migration, `v2/frontend/lib/api.ts`, `AuthGate.tsx`, `login/page.tsx`, `AUDIT.md`

**Данные / конфиг:** `JWT_SECRET`, `AUTH_*`, `APP_ENV` в `v2/.env.example`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Бриф D2 (Tenancy + Client zone) → одобрение → код.

---

## 2026-08-06 — v2: Волна D переплан под пилот + бриф D1

**Тип:** `decision`

**Сделано:**
- Зафиксирован порядок пилота: D1 Auth → D2 Tenancy+Client zone → D3 Bitrix/Telegram-flag → D4 SSE → D5 Polish.
- Каналы заказчика: Bitrix + Web Client Zone; Telegram off для клиентов (опц. HR-notify).
- Формат: Бриф → Одобрение → Код. RLS не в D1.
- В `AUDIT.md` таблица D1–D5 + полный бриф D1 (код не писали).

**Файлы:** `v2/AUDIT.md`, `.cursor/DEVLOG.md`

**Git:** план незакоммичен; предыдущий коммит Waves A–C: `f284110`

**Следующий шаг:**
- Одобрение брифа D1 (token storage / refresh / AUTH_DISABLED) → реализация Auth.

---

## 2026-08-06 — v2: M9 Pydantic + M6 split endpoints

**Тип:** `refactor`

**Сделано:**
- M9: typed request bodies вместо `dict` (settings, tokens, HH, messaging, history…).
- M6: API разбит на `routes/*` + `common.py` + `router.py`; `endpoints.py` — shim.

**Файлы:** `schemas.py`, `app/api/v1/{common,router,endpoints,routes/*}.py`, `AUDIT.md`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Волна D / target architecture (auth, SSE jobs) или коммит накопленного.

---

## 2026-08-06 — v2: M8 HH dedup + M10 S3 + M7 UX inbox

**Тип:** `fix` + `ux`

**Сделано:**
- M8: reuse active `hh_cold_search` per vacancy (`reused=true`).
- M10: delete PCM from Yandex Object Storage in STT `finally`.
- M7: sticky next-action на карточке; `/candidates` hub + `preset=attention`.

**Файлы:** `jobs.py`, `endpoints.py`, `transcription.py`, `candidate_query.py`, `nextAction.ts`, `CandidateEditor.tsx`, `candidates/page.tsx`, `schemas.py`, `api.ts`, `globals.css`, `AUDIT.md`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- M9 Pydantic / M6 split endpoints.

---

## 2026-08-06 — v2: M4 HH 429 + M5 job Session isolation

**Тип:** `fix`

**Сделано:**
- HH `_get`: 429 → Retry-After / exponential backoff, до 5 retries.
- `update_job_isolated` / `is_cancelled_isolated`; callbacks STT в to_thread используют их.

**Файлы:** `hh_client.py`, `jobs.py`, `tasks.py`, `v2/AUDIT.md`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Волна B: M8 HH job dedup / M10 S3 cleanup / M7 UX.

---

## 2026-08-06 — v2: M2 AI JSON + M3 HH token persist

**Тип:** `refactor` + `fix`

**Сделано:**
- M2: `parse_ai_json` с repair как в legacy; `resume_eval` / `hh_criteria_prefill` → `chat_json`.
- M3: `hh_oauth.json` persist после refresh; файл приоритетнее `.env`; один `HhClient` на HH job.
- `hh_oauth.py` пишет токены в `data/hh_oauth.json`.

**Файлы:** `ai_json.py`, `resume_eval.py`, `hh_criteria_prefill.py`, `hh_tokens.py`, `hh_client.py`, `tasks.py`, `scripts/hh_oauth.py`, `v2/AUDIT.md`

**Данные / конфиг:** новый файл `data/hh_oauth.json` (секреты; не коммитить)

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Волна B: M4 HH 429 backoff.

---

## 2026-08-06 — v2: M11 JSONB normalize + M1 Alembic baseline

**Тип:** `infra`

**Сделано:**
- Скрипт `normalize_jsonb` + defaults: deep-fill missing keys в payload/documents (без overwrite).
- Применено на локальной БД: 99 candidates, 12 vacancies.
- Alembic baseline `d22a995b8f9c` (create_all + indexes clients); `alembic upgrade head` на локальной БД.
- README: `alembic upgrade head` + пример normalize; AUDIT: M11/M1 done.

**Файлы:** `v2/backend/app/services/jsonb_defaults.py`, `v2/backend/app/scripts/normalize_jsonb.py`, `v2/backend/alembic/versions/d22a995b8f9c_baseline_v2_schema.py`, `v2/backend/app/main.py`, `v2/README.md`, `v2/AUDIT.md`

**Данные / конфиг:** изменена JSONB в Postgres (добавлены missing keys); alembic_version → `d22a995b8f9c`

**Git:** незакоммичено на `feature/v2`

**Следующий шаг:**
- Волна B: M2 единый AI JSON repair.

---

## 2026-08-06 — Bitrix: синхронизация DESCRIPTION + комментарий

**Тип:** `feature`

**Сделано:**
- При смене статуса (Встреча/Подумать/Отказ/Оффер) — обновление блока «Текущий статус» в DESCRIPTION задачи оценки + комментарий в ленте.
- При подтверждении HR — блок «Встреча подтверждена HR» в задаче встречи + комментарий.
- Маркеры `---HRA_STATUS---` / `---HRA_MEETING---` для безопасной подмены блока.
- Синхронизация из Bitrix decide, Telegram-кнопок, confirm-meeting.

**Файлы:** `bitrix/task_sync.py`, `client.py`, `decide.py`, `outbound.py`, `meeting_task.py`, `inbound.py`, `endpoints.py`

**Следующий шаг:**
- Перезапустить backend; сменить статус / подтвердить встречу — проверить описание и ленту задачи.

---


**Тип:** `feature`

**Сделано:**
- **A:** кнопка «Подтвердить встречу» в карточке → `POST …/confirm-meeting`.
- **B:** после назначения встречи (Bitrix/Telegram) — Telegram HR с кнопкой подтверждения.
- Задача Bitrix «Встреча: …» с DEADLINE/START_DATE_PLAN на дату встречи.
- «Подумать»: при закрытии задачи решения — follow-up через 3 рабочих дня (пн–пт); polling каждые 60 с в фоне API; webhook OnTaskUpdate тоже.
- Новая задача «Принять решение» при истечении срока; цикл повторяется, пока статус think и вакансия активна.

**Файлы:** `bitrix/hr_notify.py`, `meeting_task.py`, `think_followup.py`, `decide.py`, `inbound.py`, `main.py`, `endpoints.py`, `CandidateEditor.tsx`

**Конфиг:** `TELEGRAM_HR_USER_ID` для варианта B.

**Следующий шаг:**
- Перезапустить backend; проверить встречу + подтверждение + сценарий «Подумать» → закрыть задачу → через 3 раб. дня новая задача.

---


**Тип:** `fix`

**Сделано:**
- Повторная отправка в Bitrix сбрасывает старую встречу и статус → «ждёт оценки».
- Переход на этап «На оценке у заказчика» очищает дату/время прошлой встречи.
- Кнопка «Встреча» в Bitrix открывает форму (дата, время, формат), как в Telegram.

**Файлы:** `bitrix/decide.py`, `bitrix/pages.py`, `bitrix/outbound.py`, `candidate_write.py`, `main.py`

**Следующий шаг:**
- Перезапустить backend, переотправить Чупрову, назначить встречу через форму.

---


**Тип:** `fix`

**Сделано:**
- `client_notify_has()` — единая проверка канала в настройках.
- `send-to-chat` не трогает Telegram, если галочка снята; нет fallback на telegram по умолчанию при пустом списке.
- Напоминания, доп. материал, refresh карточки — пропуск без сетевых вызовов.
- В карточке кандидата Telegram-кнопки скрыты, если канал отключён.

**Файлы:** `app_settings.py`, `gateway.py`, `ops.py`, `CandidateEditor.tsx`

**Следующий шаг:**
- Сохранить настройки (только Bitrix), перезапустить backend, отправить кандидата.

---


**Тип:** `fix` / `ux`

**Сделано:**
- `send_candidate_to_client`: каналы Telegram и Bitrix параллельно (отдельные DB-сессии), этап меняется один раз.
- Короткие сообщения об ошибках (таймаут Telegram, ngrok); частичный успех — жёлтый баннер.
- Раздел карточки переименован «Telegram» → «Заказчик».
- В настройках Bitrix — предупреждение: ngrok должен быть запущен, старые ссылки умирают при смене URL.

**Файлы:** `messaging/gateway.py`, `CandidateEditor.tsx`, `ActionBanner.tsx`, `settings/bitrix/page.tsx`

**Риски:** при обоих каналах Telegram-таймаут всё ещё возможен — снимите галочку Telegram, если используете только Bitrix локально.

**Следующий шаг:**
- Запустить `ngrok http 8000`, обновить `public_api_base`, переотправить кандидата для новых ссылок в задаче.

---


**Тип:** `ux`

**Сделано:**
- Описание задачи: `DESCRIPTION_IN_BBCODE=Y`, ссылки `[url=…]подпись[/url]` вместо голых URL.
- Блоки «Материалы» и «Ваше решение» с иконками (🟢🟡🔴🟣) как в Telegram.
- Убраны `candidate_id` и длинные decide-URL из видимого текста.

**Файлы:** `bitrix/outbound.py`, `bitrix/tokens.py`, `settings/bitrix/page.tsx`

**Следующий шаг:**
- Отправить кандидата заново и проверить вид задачи в Bitrix.

---


**Тип:** `feature`

**Сделано:**
- Облачный Bitrix через входящий webhook не даёт `task.item.userfield.*` (`Action not allowed`) — отказались от UF как основного пути.
- В описании задачи — HMAC-ссылки ready/think/reject/offer → `GET/POST /integrations/bitrix/decide`.
- Для think/reject — HTML-форма комментария; иначе сразу `apply_client_update`.
- Настройка `public_api_base` (публичный HTTPS API); `decide_secret` генерируется при сохранении.
- UI `/settings/bitrix` и инструкция обновлены под ссылки.

**Файлы:** `bitrix/tokens.py`, `decide.py`, `pages.py`, `outbound.py`, `app_settings.py`, `main.py`, `settings/bitrix/page.tsx`

**Данные / конфиг:** `bitrix.public_api_base`, `bitrix.decide_secret`

**Следующий шаг:**
- Указать public_api_base (ngrok/прод), включить канал Bitrix, проверить create task + клик по ссылке.

---


**Тип:** `feature`

**Сделано:**
- Настройки `bitrix` + `client_notify.channels` (telegram / bitrix / оба) в `app_settings.json`.
- UI `/settings/bitrix`: подключение, UF-поля, маппинг enum, инструкция настройки портала.
- `send-to-chat` диспатчит по выбранным каналам; Bitrix создаёт задачу (`tasks.task.add`) со сроком N часов и ссылками.
- Webhook `POST /integrations/bitrix/webhook` (`OnTaskUpdate`) → чтение UF → `apply_client_update` (те же статусы, что в Telegram).
- Задел: `vacancy.payload.bitrix_responsible_id` перекрывает глобальный `default_responsible_id`.

**Файлы:** `app_settings.py`, `services/bitrix/*`, `messaging/gateway.py`, `endpoints.py`, `main.py`, `schemas.py`, `settings/bitrix/page.tsx`, `settings/page.tsx`

**Данные / конфиг:** ключи в `app_settings.json`: `bitrix`, `client_notify`

**Git:** незакоммичено

**Следующий шаг:**
- На реальном портале: входящий/исходящий webhook, UF-поля, проверить create task + смену статуса.

---


**Тип:** `feature`

**Сделано:**
- Добавлен флаг `functions.hh_search_enabled` в `app_settings.json` (UI: `/settings/functions`).
- UI вакансии: при выключенном флаге скрывается таб “Поиск HH”.
- Backend: `POST /api/v1/jobs` запрещает создание `job_type=hh_cold_search`, если флаг выключен.

**Файлы:** `app_settings.py`, `endpoints.py`, `settings/page.tsx`, `settings/functions/page.tsx`, `vacancies/[id]/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- В браузере выключить флаг и проверить: таб пропадает и запуск `hh_cold_search` возвращает 403.

## 2026-08-05 — HH статус резюме: откат функции

**Тип:** `decision`

**Сделано:**
- Убраны UI (карточка + колонка «Обновлено»), endpoint `POST …/hh-resume-status`, авто-refresh при PATCH, сервис `hh_resume_status.py`.
- Причина: `GET /resumes/{id}` часто 404 даже когда сайт показывает резюме — нужен другой подход.

**Файлы:** удален `hh_resume_status.py`; правки в `endpoints.py`, `schemas.py`, `candidate_fields.py`, `CandidateEditor.tsx`, `HhSearchPanel.tsx`, `api.ts`

**Данные / конфиг:** поля в `candidate.payload` оставлены (безвредный мусор)

**Следующий шаг:**
- Новый подход к свежести/доступности HH-резюме (не через простой GET по ссылке).

---

## 2026-08-05 — HH статус: 404 = неактивен + явная причина

**Тип:** `fix`

**Сделано:**
- На Квядаравичюте: `GET /resumes/{id}` → 404, поиск по ФИО/телефону → 0; дата с API недоступна.
- В payload пишем `hh_resume_unavailable_reason`; в карточке — «неактивен» + причина, без ложного «обновлено —».

**Файлы:** `hh_resume_status.py`, `candidate_fields.py`, `schemas.py`, `CandidateEditor.tsx`, `api.ts`

**Следующий шаг:**
- Если нужно показывать дату при 404 — отдельное решение (ручной ввод / другая HH-сессия).

---

## 2026-08-05 — HH резюме: активен/неактивен + дата обновления

**Тип:** `feature`

**Сделано:**
- Статус резюме HH: «активен» = `GET /resumes/{id}` успешен; «неактивен» = 404/403/ошибка.
- Парсинг id из ссылки; сохранение в payload кандидата (`hh_resume_available`, `hh_resume_status_label`, `hh_resume_updated_at`, `hh_resume_checked_at`).
- API `POST /candidates/{id}/hh-resume-status`; авто-проверка при смене `hh_resume_link` в PATCH.
- UI карточки: статус + дата + «Обновить с HH»; в таблице HH-поиска колонка «Обновлено».

**Файлы:** `hh_resume_status.py`, `endpoints.py`, `schemas.py`, `candidate_fields.py`, `CandidateEditor.tsx`, `HhSearchPanel.tsx`, `api.ts`

**Данные / конфиг:** поля в `candidate.payload` (без миграции схемы)

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить API; на карточке кандидата с ссылкой HH нажать «Обновить с HH».

---

## 2026-08-05 — Документы из записи + шаблоны + meeting link + last contact

**Тип:** `feature`

**Сделано:**
- Пакет документов из upload/ссылок (аудио/видео/docx/xlsx/pdf) → ARQ `vacancy_docs_from_materials` → сразу в docs + `meeting_brief` Q&A.
- История: «Применить к вакансии»; UI шаблонов `/templates`.
- Zoom/Телемост: default-ссылка из настроек → `meeting_link` при remote.
- Поиск/список кандидатов: колонка «Последний контакт».

**Файлы:** `vacancy_docs_pack.py`, `source_extract.py`, `transcription.py`, `tasks.py`, `endpoints.py`, `DocumentsFromMaterials.tsx`, `DocumentsEditor.tsx`, `templates/page.tsx`, `HistoryApplyButton.tsx`, `CandidateEditor.tsx`, `candidate_query.py`

**Данные / конфиг:** deps `python-docx`, `openpyxl`, `pypdf`, `python-multipart`; uploads в `data/tmp/vacancy_docs/`

**Следующий шаг:**
- Перезапустить API + ARQ worker; проверить сценарий с реальной записью и ссылкой Я.Диска.

---

## 2026-08-04 — HH preset: русские подписи в селектах

**Тип:** `fix`

**Сделано:**
- Подписи `form_options` (логика/поле/период текста, образование, label, сортировка и др.) на русском.

**Файлы:** `hh_preset.py`, `HhPresetBlock.tsx`

**Следующий шаг:**
- Prefill ИИ → draft preset; cron + Telegram digest.

---

## 2026-08-04 — HH preset: модель + UI + worker

**Тип:** `feature`

**Сделано:**
- SoT поиска: `vacancy.documents.hh_preset` (`api` / `soft` / `run`); миграция из `hh_search_criteria`.
- API `GET/PUT …/hh-preset`; `POST /jobs` и worker `hh_cold_search` гоняют только params из preset.
- UI: вкладки **Пресет | Результаты | Вручную**; форма зеркалит фильтры HH (text triad, area, role, experience…).
- Live smoke: role=50 + area=2 + «казначей» → резюме «Казначей», СПб.

**Файлы:** `hh_preset.py`, `hh_client.py`, `tasks.py`, `endpoints.py`, `schemas.py`, `HhPresetBlock.tsx`, `HhSearchPanel.tsx`, `ARCHITECTURE.md`

**Следующий шаг:**
- Prefill ИИ → draft preset; cron + Telegram digest; вычистить dead plan/criteria UI.

---

## 2026-08-04 — HH preset: этап 0 (smoke API)

**Тип:** `decision`

**Сделано:**
- Smoke `GET /resumes` живым employer-токеном: auth OK; почти все фильтры HH реально меняют `found`.
- Подтверждено: `age_from/to`, `gender`, `professional_role` (id `50` = Казначей), multi-`text` + triad.
- `specialization` — 200, но `found` не меняется (игнор/deprecated); `text.period=last_six_months` — `bad_argument`.
- Зафиксированы слоты формы vs soft vs unavailable; черновик `hh_preset` schema в чате.

**Файлы:** (код не трогали) smoke через Settings/`hh_client`

**Следующий шаг:**
- Этап 1: `hh_preset` model + CRUD API + замена UI настроек поиска.

---

## 2026-08-04 — HH text.logic: ИЛИ / И как на сайте

**Тип:** `feature`

**Сделано:**
- Правила HH в стратеге: `keywords` = ИЛИ (любое из), `keywords_and` = И (напр. 1С).
- API: `text.logic=any|all`; (A|B) AND C → запросы `A C`, `B C`.
- В плане UI — строка «ИЛИ / И»; в job — `query_plan`.

**Файлы:** `hh_search_criteria.py`, `hh_client.py`, `hh_search_plan.py`, `tasks.py`, `HhSearchPlanBlock.tsx`

**Следующий шаг:**
- Перегенерировать план и прогнать поиск по Казначею

---


**Тип:** `feature`

**Сделано:**
- Удаление поиска из БД + «Очистить failed/queued»; в списке результатов — только оценённые.
- Hard-отсев другого города до ИИ; `schedule` больше не уходит в HH API (мешал гибрид/remote).
- period по умолчанию 7; стратег — многословные запросы («бухгалтер банк-клиент»).
- После поиска — debrief: статистика отсева + предложения ИИ что менять.

**Файлы:** `hh_prefilter.py`, `hh_search_criteria.py`, `hh_search_plan.py`, `hh_search_debrief.py`, `jobs.py`, `endpoints.py`, `tasks.py`, `HhSearchPanel.tsx`

**Следующий шаг:**
- Перегенерировать план на вакансии и прогнать поиск (старый approved plan ещё со schedule/period=30).

---


**Тип:** `fix`

**Сделано:**
- Баг: после «Утвердить и начать поиск» `onStart` видел старый `plan.status` и отменял job — передаём `fromApprove` + criteria сразу.
- Лимиты «найти / оценить» снова в UI плана (были только в скрытой «воронке»).
- На результатах показываются лимиты и счётчики found/evaluated.

**Файлы:** `HhSearchPanel.tsx`, `HhSearchPlanBlock.tsx`

**Риски/регрессии:**
- Если ARQ worker не запущен или `HH_ACCESS_TOKEN` просрочен — job упадёт (раньше в логах был `token-expired`).

**Следующий шаг:**
- Перезапустить worker при необходимости; обновить HH OAuth token

---

## 2026-08-04 — HH UI: только план + результаты

**Тип:** `ux`

**Сделано:**
- В `HhSearchPanel` флаг `HH_ADVANCED_UI = false`: скрыты вкладки «Расшир.» / «Вручную» и футер «Искать на HH».
- Остались вкладки **План** и **Результаты**; код расширенных форм не удалён (вернуть: `true`).
- Поиск из плана: утвердить → автозапуск; без approve — ошибка.

**Файлы:** `HhSearchPanel.tsx`, `HhSearchPlanBlock.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Прогнать сценарий план → правка → поиск на живой вакансии

---

## 2026-08-03 — HH план поиска + Disk inbox L3

**Тип:** `feature`

**Сделано:**
- HH: вкладка «План» — generate/revise/approve (`hh_search_plan`); machine → criteria + `soft_rules` в оценку; расширенные критерии в «Расшир.»
- Disk L3: таблица `inbox_items`, `disk_inbox_router` (download → PDF text → ИИ → move в `Резюме/` / `_unsorted` → кандидат)
- API: inbox process/bind/settings; UI `/settings/yandex-disk` — порог, роутинг, привязка unsorted
- Документы: `ARCHITECTURE.md` обновлён (план + L3); TARGET — оставшиеся OCR/cron/auth

**Файлы:** `hh_search_plan.py`, `hh_search_criteria.py`, `disk_inbox_router.py`, `models.py`, `endpoints.py`, `tasks.py`, `HhSearchPlanBlock.tsx`, `HhSearchPanel.tsx`, `settings/yandex-disk/page.tsx`, `ARCHITECTURE.md`

**Данные / конфиг:** `inbox_items` (create_all); `disk_inbox_confidence` / `disk_inbox_auto` / `disk_inbox_evaluate` в `app_settings.json`

**Git:** незакоммичено на `feature/v2`

**Риски/регрессии:**
- Сканы без текста → error; OCR нет
- Синхронный process из UI (job ARQ есть, UI пока вызывает sync endpoint)

**Следующий шаг:**
- Проверить на живом Диске: PDF в `_inbox` → роутинг; HH утвердить план и поиск

---

## 2026-08-03 — ARCHITECTURE.md = текущая SoT v2

**Тип:** `docs`

**Сделано:**
- `ARCHITECTURE.md` переписан под PostgreSQL + Next/FastAPI/ARQ после cutover.
- `ARCHITECTURE_TARGET.md` — шапка: оставшиеся фазы, ссылка на актуальный ARCHITECTURE.

**Файлы:** `ARCHITECTURE.md`, `ARCHITECTURE_TARGET.md`

**Git:** незакоммичено (или вместе со следующим коммитом docs)

**Следующий шаг:**
- При желании закоммитить docs на `feature/v2`.

---

## 2026-08-03 — Пресет этапов вакансии + Яндекс.Диск L1/L2-stub

**Тип:** `feature`

**Сделано:**
- Пресет HR-этапов на вакансию: подписи + вкл/выкл; после появления кандидатов структура заморожена (только labels).
- UI в «Управление вакансией» → «Этапы и статусы»; карточка кандидата берёт опции из схемы вакансии.
- Яндекс.Диск OAuth: настройки `/settings/yandex-disk`, токен в `data/yandex_disk_oauth.json`, корень `/HR_AI_Agent` + `_inbox`.
- Кнопка «Создать папки на Диске» у вакансии (mkdir + publish → public URL для старого синка).
- Inbox L2-stub: список файлов + эвристика вакансии по имени `Вакансия__ФИО.pdf` (без auto-move).

**Файлы:** `stage_schema.py`, `yandex_disk_oauth.py`, `endpoints.py`, `vacancy_write.py`, `VacancyStageSchemaPanel.tsx`, `YandexDiskPanel.tsx`, `settings/yandex-disk/page.tsx`, `config.py`, `.env.example`

**Данные / конфиг:** `YANDEX_DISK_OAUTH_TOKEN`, `YANDEX_DISK_CLIENT_ID`; `app_settings.json` ключи `yandex_disk_root` / `yandex_disk_inbox`

**Git:** `feature/v2` (после push предыдущего коммита; этот набор — следующий коммит)

**Следующий шаг:**
- Прописать OAuth-токен Диска и проверить create folders + inbox на живом аккаунте.

---

## 2026-08-03 — Шрифт, цвета этапов, ИИ/связь, HH вручную

**Тип:** `fix` / `feature` / `ux`

**Сделано:**
- Шрифт: boot-script до paint, functional persist, явный `html` font-size; `font: inherit` на form controls.
- Списки кандидатов: цветной кружок по HR-этапу (жёлтый → зелёная шкала → оффер → красный отказ).
- Настройки: `/settings/ai` (модель без смены ключа; ссылки Яндекс/RouterAI), сайдбар «Ресурсы»; `/settings/candidate-comms` (Zoom/Телемост/мессенджеры — только хранение).
- HH вкладка «Вручную»: массовая оценка ссылок + сравнительная таблица; ИИ-чек-лист смягчения фильтров (по ручным резюме или автопоиску) с применением отмеченных пунктов.
- `app_settings.json`: `ai_model`, `ai_provider`, `provider_links`, `candidate_comms`; model override в `ai_json` / `resume_eval` / `hh_criteria_prefill`.

**Файлы:** `UiPrefsProvider.tsx`, `layout.tsx`, `StageMarker.tsx`, `labels.ts`, `globals.css`, `app_settings.py`, `endpoints.py`, `hh_manual_eval.py`, `HhManualEvalBlock.tsx`, `HhSearchPanel.tsx`, `settings/ai`, `settings/candidate-comms`, `AppShell.tsx`, `ProviderResourceLinks.tsx`

**Данные / конфиг:** `data/app_settings.json` (новые ключи); ключи API ИИ по-прежнему из `.env`

**Git:** `feature/v2`, незакоммичено

**Следующий шаг:**
- Перезапустить API/worker и проверить шрифт, сайдбар настроек, HH «Вручную».

---

## 2026-08-03 — Главная: hub + навигация по разделам

**Тип:** `ux`

**Сделано:**
- Главная `/`: hero + тональные карточки-кнопки (настройки / документы / поиск), без верхнего меню поиска.
- `AppShell` variants: `home` | `search` | `settings`; меню Вакансии/Кандидаты… только в `search`.
- В Поиске и Настройках — «← Вернуться в главное меню».
- Настройки: карточка и страница «Описание функционала» (`/settings/about`).

**Файлы:** `AppShell.tsx`, `app/page.tsx`, `app/settings/page.tsx`, `app/settings/about/page.tsx`, `globals.css`, страницы `settings/*` / search

**Git:** `feature/v2`, незакоммичено

**Следующий шаг:**
- Проверить главную и переходы в UI.

---

## 2026-08-03 — Настройки: хаб вместо одной длинной страницы

**Тип:** `ux`

**Сделано:**
- `/settings` — оглавление из 6 карточек-ссылок (минимум текста на экране).
- Разделы вынесены: appearance, companies, test-chat, telegram, calendar, warranty.
- В Telegram внутренние блоки свёрнуты по умолчанию.

**Файлы:** `settings/page.tsx`, `settings/*/page.tsx`, `globals.css`

**Git:** `feature/v2`, незакоммичено

**Следующий шаг:**
- Пройти хаб глазами в UI.

---

## 2026-08-03 — Настройки: создание компании отдельно + страница компании

**Тип:** `feature` / `ux`

**Сделано:**
- Блок «Создать клиента / компанию» отдельно от списка.
- Существующие компании — свёрнутые карточки + ссылка на `/settings/companies/{id}`.
- Страница компании: название, режим чатов, общий чат или подразделения.
- API `GET /companies/{id}`.

**Файлы:** `CompaniesSettings.tsx`, `CompanyEditor.tsx`, `settings/companies/[id]/page.tsx`, `lib/companies.ts`, `endpoints.py`

**Git:** `feature/v2`, незакоммичено

**Следующий шаг:**
- Проверить UX YourBox / Пульс на новых страницах.

---

## 2026-08-03 — Компании / подразделения / тестовый чат в Настройках

**Тип:** `feature`

**Сделано:**
- В `clients`: `parent_id`, `chat_mode` (company|departments), `kind` (company|department|test).
- Миграция: YourBox + 6 отделов; Пульс Групп — один чат; Тестировочный — `kind=test`.
- API: `/companies`, CRUD клиентов, подразделения, `/settings/test-chat`.
- UI: блоки «Компании и чаты», «Тестировочный чат»; сайдбар группирует YourBox.

**Файлы:** `models.py`, `clients_write.py`, `endpoints.py`, `schemas.py`, `main.py`, `CompaniesSettings.tsx`, `TestChatSettings.tsx`, `ClientSidebar.tsx`, `settings/page.tsx`

**Данные / конфиг:** ALTER clients; YourBox id=101

**Git:** ветка `feature/v2`, незакоммичено (после предыдущего push)

**Следующий шаг:**
- Проверить Настройки в UI и переключение режима у Пульс Групп.

---

## 2026-08-03 — Git: ветка feature/v2 на GitHub

**Тип:** `deploy` / `git`

**Сделано:**
- Создана ветка `feature/v2` от `main`.
- Закоммичен v2 (API/UI/workers) + сопутствующие правки Streamlit и docs.
- Запушено на `origin/feature/v2` (`c482924`). `v2/.env` не в репозитории.

**Git:** branch `feature/v2`, commit `c482924`, remote pushed

**Следующий шаг:**
- При необходимости — PR: https://github.com/cerealex-creator/hr_ai_agent/pull/new/feature/v2

---

## 2026-08-03 — UX-пакет: Telegram comment, HH history, хаб, темы

**Тип:** `feature` / `fix`

**Сделано:**
- Telegram: «Подумать»/«Отказ» и «Комментарий» снова шлют reply-prompt под карточкой (как Streamlit); якорь MessagingPost из callback.
- HH: история поисков из `jobs` — последний результат после refresh + выбор прошлых прогонов.
- Карточка вакансии: вкладки сразу после meta; «Управление вакансией» свёрнуто внизу.
- Главная `/` — 3 блока; список вакансий на `/vacancies`.
- Настройки: темы (светлая/тёмная/контраст) + ползунок шрифта (localStorage).
- Убраны cutover/PostgreSQL/Streamlit-тексты из UI.

**Файлы:** `inbound.py`, `jobs.py`, `endpoints.py`, `schemas.py`, `HhSearchPanel.tsx`, `vacancies/[id]/page.tsx`, `VacancyLifecycle.tsx`, `page.tsx`, `vacancies/page.tsx`, `AppShell.tsx`, `AppearanceSettings.tsx`, `UiPrefsProvider.tsx`, `globals.css`, …

**Git:** незакоммичено

**Следующий шаг:**
- Согласовать модель «Компания → подразделения/чаты» и реализовать CRUD в Настройках.

---

## 2026-08-03 — HH поиск «Казначей»: ARQ был мёртв

**Тип:** `fix` / `ops`

**Сделано:**
- Диагностика: HH API и токен OK; джобы `hh_cold_search` висели в `queued`/`running` без прогресса, потому что ARQ worker не работал (процесс умирал после nohup / pkill).
- Поднят ARQ в постоянном терминале; отменены orphan-джобы; очищены stuck Redis `arq:in-progress:*`.
- Повторный поиск по вакансии 13 (Казначей) завершился: найдено 20, оценено 10, отсев 6, ~21 мин.

**Файлы:** (ops) `run/logs/v2_arq.log`; job `39d4534c-…`

**Git:** без правок кода

**Следующий шаг:**
- Держать ARQ живым (`arq app.workers.settings.WorkerSettings`); при «тихом» поиске сначала смотреть `/jobs` и процесс ARQ.

---

## 2026-08-03 — Новая вакансия из существующей / архива

**Тип:** `feature`

**Сделано:**
- В «Новая вакансия»: режимы «С нуля» / «Из существующей» (архив сверху списка).
- При выборе источника префиллятся title, client, chat; в API уходит `source_vacancy_id`.
- Копируются documents + настройки; кандидаты не переносятся; `seen_paths` Я.Диска обнуляются.
- В `VacancyListItem` добавлен `chat_id` для префилла.

**Файлы:** `CreateVacancyForm.tsx`, `page.tsx`, `api.ts`, `schemas.py`, `endpoints.py`, `vacancy_write.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить создание из архивной вакансии и наличие документов на новой карточке.

---

## 2026-08-03 — Cutover Streamlit → v2

**Тип:** `deploy` / `cutover`

**Сделано:**
- Snapshot `data/` → `data_snapshot_20260803/` (без `*.webm`).
- Финальный импорт `--replace`: 8 clients, 11 vacancies, 99 candidates, 36 messaging_posts, 17 history, 4 templates.
- Streamlit/`bot.py` не запущены; v2 на **боевом** токене `@hr_yourboxBot`.
- Запущены API `:8000`, ARQ worker, telegram_poller; UI `:3000` уже был up.
- `MESSAGING_INBOUND/OUTBOUND/POLL=true`.

**Данные / конфиг:** `data_snapshot_20260803/`, `v2/.env` TELEGRAM_BOT_TOKEN=prod

**Git:** незакоммичено (secrets в `.env` не коммитить)

**Риски:**
- Не запускать старый `bot.py` параллельно (409 Conflict).
- `data/` и snapshot хранить для отката.

**Следующий шаг:**
- Smoke: кнопка статуса в боевом чате + 2–3 карточки в UI vs snapshot.

---

## 2026-08-01 — Настройки: CRUD чатов как в Streamlit

**Тип:** `feature`

**Сделано:**
- Форма «Сохранить чат»: название + Chat ID + подразделение (существующее или «Создать новое»).
- Переименование (имя/chat_id), смена подразделения, удаление чата.
- Тест и инструкция — `<select>` из списка чатов, не ручной ввод.
- API: `POST /clients`, `POST/PATCH/DELETE /messaging/channels`; sync `vacancy.chat_id` по client_id.

**Файлы:** `clients_write.py`, `channels.py`, `schemas.py`, `endpoints.py`, `settings/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить в UI: создать чат с новым отделом, тест/инструкция из дропдауна, rename/delete.

---

## 2026-08-01 — HR-confirm refresh + сводка в чат

**Тип:** `fix` / `feature`

**Сделано:**
- После кнопки `mhc` / явки в ЛС HR карточка обновляется в чате **заказчика** (`find_client_chat_post` по `vacancy.chat_id`), а не по chat_id ЛС.
- В HTML карточки Telegram при встрече: «подтверждена HR» / «ожидает подтверждения HR».
- Кнопка «Сводка в чат» под meta-grid на странице вакансии → `POST /vacancies/{id}/digest-to-chat`.
- Инструкция заказчику по-прежнему только в Настройках.

**Файлы:** `inbound.py`, `card_html.py`, `VacancyDigestButton.tsx`, `vacancies/[id]/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить poller/API; нажать HR-confirm и проверить карточку в чате + F5 в веб.

---

## 2026-08-01 — UX: документы, календарь, чат, Я.Диск keys

**Тип:** `fix` / `polish`

**Сделано:**
- Пустые документы больше не считаются «есть» (убран fallback на Object.keys).
- Параметры вакансии / автозагрузка — свёрнуты по умолчанию.
- Календарь: по умолчанию не удалять; чекбокс «Удалить событие…».
- Chat: title канала + Редактировать; кандидаты сортируются как Streamlit.
- Статус «wait» при отказе/до клиента → «не показывался» / «не отправлен».
- HR-confirm встречи на карточке; Я.Диск RU + unique keys в логе.

**Файлы:** vacancy page, ChatSelect, VacancySettingsPanel, BulkLinksForm, CandidateEditor, labels, YandexDiskPanel, endpoints, schemas

**Git:** незакоммичено

**Следующий шаг:**
- Обновить UI и перепроверить вакансию «Менеджер по работе с блогерами» (синк Я.Диск).

---

**Тип:** `fix` / `polish`

**Сделано:**
- Выбор чата из списка каналов при создании/настройках вакансии (`ChatSelect`).
- Авто-refresh TG-карточки при save ссылок + кнопка «Обновить данные» с notify и deep-link.
- Комменты заказчика к статусу в summary; LinkField Open/Edit; ActionBanner у секции.
- Manual remind без ложных «5 дней»; OAuth parse `code=` + PKCE pending; сайдбар на Settings.

**Файлы:** `ChatSelect.tsx`, `LinkField.tsx`, `ActionBanner.tsx`, `CandidateEditor.tsx`, `ops.py`, `reminders.py`, `google_calendar.py`, Settings/CreateVacancy…

**Git:** незакоммичено

**Следующий шаг:**
- Для Андроповой: переотправить карточку из v2 (старые кнопки Streamlit не работают).

---

## 2026-07-30 — Cutover волны B → A1 → A2

**Тип:** `feature`

**Сделано:**
- Волна 0: import wipe messaging/hh, `telegram_posts`→`messaging_posts`, history ids, CUTOVER verify.
- A1: reminder tick (poller), attendance/HR-confirm, digests/commands/nav, ops API (remind/materials/digest/instruction/refresh), Settings UI.
- A2: task_link/materials/history/control_word/is_test, apply client stage, copy, search; warranty registry/create; Google Calendar sync + OAuth UI.

**Файлы:** `import_json.py`, `CUTOVER.md`, `messaging/*`, `telegram_poller.py`, `endpoints.py`, `warranty.py`, `google_calendar.py`, `interview_calendar.py`, `candidate_copy.py`, `candidate_search.py`, Settings/CandidateEditor/VacancySettingsPanel/…

**Данные / конфиг:** `TELEGRAM_HR_USER_ID`, reminder tz/interval, `GOOGLE_CALENDAR_*`, `data/app_settings.json` (warranty months)

**Git:** незакоммичено

**Следующий шаг:**
- Smoke: poller reminders + Settings OAuth + warranty на 1 вакансии; pip install google libs в v2 venv.

---

## 2026-07-30 — Чеклист фич до cutover

**Тип:** `docs`

**Сделано:**
- Файл `v2/CUTOVER_FEATURE_CHECKLIST.md`: Missing/Partial vs Streamlit + требования идентичности данных (вакансии/кандидаты/stats) и день cutover.

**Файлы:** `v2/CUTOVER_FEATURE_CHECKLIST.md`

**Git:** незакоммичено

**Следующий шаг:**
- Пользователь отмечает нужные пункты → приоритизация переноса.

---

## 2026-07-30 — Telegram poller как сервис


**Тип:** `feature`

**Сделано:**
- Модуль `python -m app.workers.telegram_poller` (getUpdates, снимает webhook).
- Флаг `MESSAGING_POLL_ENABLED`; docker profile `messaging` → `telegram-poller`.
- README / `.env.example` / `messaging/status` обновлены.

**Файлы:** `telegram_poller.py`, `config.py`, `endpoints.py`, `docker-compose.yml`, `README.md`, `.env.example`

**Данные / конфиг:** `MESSAGING_POLL_ENABLED`

**Git:** незакоммичено

**Следующий шаг:**
- Держать poller запущенным на тестовом токене; позже — HTTPS webhook без poll.

---

## 2026-07-30 — Cleanup чата после комментария + confirmation


**Тип:** `feature`

**Сделано:**
- После фиксации комментария: удаляются prompt бота и сообщение пользователя.
- Бот пишет подтверждение с текстом комментария и reply на карточку (+ `t.me/c/...` в супергруппах).

**Файлы:** `inbound.py`, `telegram_provider.py`

**Риски:** удаление чужих сообщений в группе требует прав админа у бота.

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить poller; сделать бота админом тестового чата при необходимости.

---

## 2026-07-30 — Комментарии к статусу отдельно в карточке чата


**Тип:** `polish`

**Сделано:**
- Комментарии к «Подумать»/«Отказ» сохраняются с пометкой `к статусу «…»:`.
- В Telegram-карточке: блок «Комментарий к статусу» vs обычный «Комментарий».

**Файлы:** `client_apply.py`, `card_html.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить poller и проверить think/reject + кнопку «Комментарий».

---

## 2026-07-30 — Удаление prompt-сообщения после комментария


**Тип:** `fix`

**Сделано:**
- Сообщение «Для статуса нужна короткая причина…» сохраняет `prompt_message_id` в pending action.
- После отправки комментария prompt удаляется из чата (`deleteMessage`).

**Файлы:** `v2/backend/app/services/messaging/inbound.py`, `telegram_provider.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить think/reject в тестовом чате: prompt исчезает после reply.

---

## 2026-07-29 — Карточка: встреча + live-обновление из чата


**Тип:** `feature`

**Сделано:**
- В summary карточки при назначенной встрече показываются дата/время, формат (онлайн/офис) и «подтверждено / не подтверждено» (`payload.meeting_hr_confirmed`).
- Пока открыта карточка — polling ~8 с: изменения из чата (статус / встреча / комментарий) подтягиваются сами; если форма грязная — баннер «Обновить карточку».
- Постоянный webhook без терминала — отложено (пока local poller / tunnel).

**Файлы:** `v2/frontend/components/CandidateEditor.tsx`, `v2/frontend/app/globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Smoke: смена статуса/встречи в тестовом чате → обновление summary без F5.

---

## 2026-07-28 — Messaging Gateway slice 2 (inbound)


**Тип:** `feature`

**Сделано:**
- Outbound `send-to-chat` шлёт карточку с inline-кнопками (статусы + комментарий), короткий `tg_callback_id`.
- Inbound: webhook обрабатывает `cs/cc/cchg/ccl` + wizard встречи `ivi/ivd/ivt/ivf/ivc/ivx` → PG (`client_status`, `hr_stage`, дата встречи, комментарии, `messaging_actions`).
- Pending-комментарии для think/reject живут в `messaging_actions` (не в памяти).
- Флаг `MESSAGING_INBOUND_ENABLED` (default false) — не конфликтует с polling `bot.py`.
- Документы: README, CUTOVER, `.env.example`.

**Файлы:** `messaging/keyboards.py`, `client_apply.py`, `inbound.py`, `gateway.py`, `telegram_provider.py`, `card_html.py`, `config.py`, `endpoints.py`, `main.py`, `CandidateEditor.tsx`

**Данные / конфиг:** `MESSAGING_INBOUND_ENABLED=false` по умолчанию

**Git:** незакоммичено

**Риски/регрессии:**
- Не включать inbound на боевом токене, пока крутится Streamlit-бот.
- HR-confirm встречи / attendance — ещё не в v2.

**Следующий шаг:**
- Smoke на тестовом токене (webhook или ручной POST update).

---

## 2026-07-28 — Анкета свёрнута по умолчанию

**Тип:** `polish`

**Сделано:**
- Блок «Анкета» в карточке кандидата свёрнут по умолчанию, разворачивается по клику (как остальные секции).
- Опросник тоже всегда свёрнут по умолчанию (раньше открывался, если уже были вопросы).

**Файлы:** `v2/frontend/components/CandidateEditor.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Inbound Messaging ближе к cutover.

---

## 2026-07-28 — Карточка: сводка сверху + свёртка блоков

**Тип:** `polish`

**Сделано:**
- Сверху сводка: оценка ИИ, HR-этап + статус заказчика, «в работе с … · N дн.» (teal), «ждёт решения с … · N дн.» (янтарный) при просроченном собеседовании/встрече или на оценке/паузе у заказчика.
- Дата встречи с заказчиком = `office_interview_date` (как ставит Telegram-бот).
- Ниже анкеты блоки сворачиваются по отдельности: Этап, Опросник, Telegram, Комментарий ИИ.
- `npm run build` OK.

**Файлы:** `CandidateEditor.tsx`, `CollapsibleCard.tsx`, `QuestionnairePanel.tsx`, `dates.ts`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Inbound Messaging ближе к cutover.

---

## 2026-07-28 — Полировка собеседования и карточки кандидата

**Тип:** `polish`

**Сделано:**
- Карточка кандидата упорядочена: Карточка → Этап → Опросник и собеседование → Telegram → Комментарий ИИ.
- Убраны дубли: отдельный блок «Оценка ИИ», поля расшифровки и замечаний опросника из тела карточки.
- Действия собеседования собраны в одном блоке; черновик ссылки на запись передаётся до сохранения; расшифровка — свёрнутый просмотр.
- Антидубль job `candidate_interview_process` + флаг `reused` в ответе API; fill опросника автогенерит шаблон при пустом.
- Подписи оценок ИИ по-русски (`satisfactory` → «Удовлетворительно»).
- `npm run build` OK.

**Файлы:** `CandidateEditor.tsx`, `QuestionnairePanel.tsx`, `globals.css`, `endpoints.py`, `schemas.py`, `jobs.py`, `candidate_questionnaire.py`

**Git:** незакоммичено

**Следующий шаг:**
- Inbound Messaging ближе к cutover.

---

## 2026-07-28 — Fix: next build (`defaultOpen` у details)

**Тип:** `fix`

**Сделано:**
- `DocumentBlock`: controlled `open`/`onToggle` вместо `defaultOpen` (React 19 types).
- Убран `defaultOpen={false}` в `DocumentsEditor`.
- `npm run build` проходит успешно.

**Файлы:** `v2/frontend/components/DocumentBlock.tsx`, `DocumentsEditor.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Inbound Messaging ближе к cutover.

---

## 2026-07-28 — Опросник: новый сценарий карточки кандидата

**Тип:** `feature`

**Сделано:**
- Блок `Опросник` переработан: вместо отдельной кнопки формирования теперь единый сценарий с подблоком `Настройки`.
- Если оценки кандидата еще нет, доступна кнопка `Оценить кандидата и сформировать опросник`; после оценки опросник создается автоматически.
- Добавлены замечания рекрутера для повторного создания опросника; повторное создание сохраняет уже внесенные заметки и оценки, где это возможно.
- После добавления ссылки на запись собеседования повторное создание опросника блокируется.
- Добавлена обработка записи собеседования: `Расшифровать и оценить`, очищенная расшифровка в карточке и `Заполнить опросник` по смыслу ответов кандидата.
- Добавлен переход из кандидата в шаблон опросника вакансии и ссылка обратно к кандидату.
- Проверка: `npm run build` зеленый; mocked smoke подтвердил создание, повторное создание, заполнение по расшифровке и блокировку после ссылки на запись.

**Файлы:** `v2/frontend/components/QuestionnairePanel.tsx`, `CandidateEditor.tsx`, `DocumentsEditor.tsx`, `v2/frontend/app/vacancies/[id]/page.tsx`, `v2/backend/app/services/candidate_questionnaire.py`, `questionnaire_normalize.py`, `transcription.py`, `v2/backend/app/workers/tasks.py`, `settings.py`, `endpoints.py`, `schemas.py`, `candidate_write.py`, `candidate_fields.py`

**Git:** незакоммичено

**Следующий шаг:**
- Прогнать вручную живой сценарий со ссылкой на запись собеседования и очередью Redis/ARQ.

---

## 2026-07-28 — Паритет: опросник на карточке кандидата

**Тип:** `feature`

**Сделано:**
- API: `GET/PUT /candidates/{id}/questionnaire`, `POST …/questionnaire/generate` (шаблон вакансии + «в резюме» + персональные уточнения).
- UI: блок опросника на карточке — сформировать, заметки, оценки HR, порядок вопросов, сохранение.
- Нормализация списка (в т.ч. pipe-dump) в `questionnaire_normalize.py`.

**Файлы:** `v2/backend/app/services/questionnaire_normalize.py`, `candidate_questionnaire.py`, `candidate_fields.py`, `endpoints.py`, `schemas.py`, `QuestionnairePanel.tsx`, `CandidateEditor.tsx`, `globals.css`, `lib/api.ts`, `v2/README.md`

**Git:** незакоммичено

**Следующий шаг:**
- Оценка по интервью (паритет Streamlit).

---

## 2026-07-28 — Паритет: оценка по интервью + автоген опросника

**Тип:** `feature`

**Сделано:**
- Добавлен `POST /candidates/{id}/evaluate-interview`: ИИ учитывает профиль вакансии, резюме, предварительную оценку по резюме, опросник с оценками HR, расшифровку и заметки интервью.
- После `POST /candidates/{id}/evaluate-resume` опросник кандидата формируется автоматически, если его еще нет.
- В payload сохраняются отдельные снапшоты `resume_ai_*` и `interview_ai_*`, а карточка показывает актуальную итоговую оценку с источником `interview`.
- UI карточки кандидата дополнен полями `transcript` и `interview_eval_notes` и кнопкой «Оценить по интервью».
- Прогнан mocked smoke: resume eval -> questionnaire autogen -> interview eval; цепочка записи в PostgreSQL подтверждена.

**Файлы:** `v2/backend/app/services/candidate_interview_eval.py`, `candidate_resume_eval.py`, `candidate_fields.py`, `endpoints.py`, `schemas.py`, `v2/frontend/components/CandidateEditor.tsx`, `v2/frontend/lib/api.ts`, `v2/README.md`

**Git:** незакоммичено

**Риски/регрессии:** `next build` падает на старой ошибке в `v2/frontend/components/DocumentBlock.tsx` (`defaultOpen` у `<details>`), не связанной с этой задачей.

**Следующий шаг:**
- Inbound Messaging ближе к cutover или отдельный фикс `DocumentBlock.tsx` для чистой production-сборки.

---

## 2026-07-28 — Паритет: CRUD вакансий

**Тип:** `feature`

**Сделано:**
- API: `POST /vacancies`, `POST …/close` (`success` | `client_cancelled`), `POST …/reopen`, `DELETE …/vacancies/{id}` (каскад кандидатов/HH/messaging posts).
- Успешное закрытие — только при hire (internship/started_work), как в Streamlit.
- UI: «+ Новая вакансия» на списке; блок «Жизненный цикл» на карточке вакансии.

**Файлы:** `v2/backend/app/services/vacancy_write.py`, `endpoints.py`, `schemas.py`, `CreateVacancyForm.tsx`, `VacancyLifecycle.tsx`, `app/page.tsx`, `vacancies/[id]/page.tsx`, `globals.css`, `v2/README.md`

**Git:** незакоммичено

**Следующий шаг:**
- P0 паритет: опросник на карточке кандидата.

---

## 2026-07-28 — Карточка: клик по оценке → разворот комментария ИИ

**Тип:** `fix`

**Сделано:**
- Строки «Оценка по резюме: N/4» и «Оценка ИИ: N/4 · …» кликабельны — раскрывают блок комментария ИИ и скроллят к нему.
- Подпись источника без английского: `resume` → «по резюме», `interview` → «по интервью».

**Файлы:** `v2/frontend/components/CandidateEditor.tsx`, `AiCommentBlock.tsx`, `globals.css`

**Следующий шаг:**
- P0 паритет: CRUD вакансий.

---

## 2026-07-28 — Паритет slice 1: оценка резюме + bulk PDF

**Тип:** `feature`

**Сделано:**
- `POST /candidates/{id}/evaluate-resume` — PDF→текст, extract полей, оценка 0–4 по профилю вакансии (как Streamlit «Оценить по резюме»).
- `POST /vacancies/{id}/candidates/bulk-links` — автозагрузка по списку PDF-ссылок (+ опция сразу оценить).
- UI: кнопка на карточке; блок «Автозагрузка по ссылкам» на вакансии.
- Зависимость `pypdf`.

**Файлы:** `v2/backend/app/services/pdf_extract.py`, `candidate_resume_eval.py`, `candidate_fields.py`, `endpoints.py`, `schemas.py`, `requirements.txt`, `CandidateEditor.tsx`, `BulkLinksForm.tsx`, `vacancies/[id]/page.tsx`, `lib/api.ts`, `v2/README.md`

**Проверка:** Докучаева — оценка 3/4, `profile_present=true`.

**Git:** незакоммичено

**Следующий шаг:**
- P0 паритет: CRUD вакансий (создать / закрыть / удалить).

---

## 2026-07-27 — v2: синхронизация Яндекс.Диска

**Тип:** `feature`

**Сделано:**
- Выбран следующий шаг после Messaging slice 1: автопривязка файлов с Диска (без cutover / без ломки Streamlit).
- `sync_vacancy_yandex_disk`: подпапки Резюме/Записи/Задания → `resume_link` / `video_link` / `task_link` по ФИО; опционально новые кандидаты из PDF.
- API: `GET/PATCH …/yandex-disk`, `POST …/yandex-disk/sync`; ARQ job `yandex_disk_sync`.
- UI: вкладка «Я.Диск» на вакансии. Telegram-карточки открывают `yadisk:` через view URL.

**Файлы:** `v2/backend/app/services/yandex_disk_sync.py`, `yandex_public.py`, `endpoints.py`, `schemas.py`, `workers/tasks.py`, `settings.py`, `messaging/card_html.py`, `YandexDiskPanel.tsx`, `vacancies/[id]/page.tsx`, `globals.css`, `v2/README.md`

**Git:** незакоммичено

**Следующий шаг:**
- Паритет / cutover prep или Messaging inbound ближе к переключению.

---

## 2026-07-27 — Messaging Gateway slice 1 (outbound)

**Тип:** `feature`

**Сделано:**
- Таблицы `messaging_posts`, `messaging_actions`; sync каналов из `vacancy.chat_id`.
- `TelegramProvider` + `POST /candidates/{id}/send-to-chat` (HTML-карточка без кнопок; опционально этап `client_review`).
- API: `GET/POST /messaging/channels`, `/messaging/status`, stub `POST /integrations/telegram/webhook` (polling Streamlit не трогаем).
- UI: кнопка «Отправить в чат заказчика» на карточке кандидата.

**Файлы:** `v2/backend/app/db/models.py`, `services/messaging/*`, `endpoints.py`, `schemas.py`, `config.py`, `main.py`, `CandidateEditor.tsx`, `globals.css`, `v2/.env.example`, `v2/README.md`, `ARCHITECTURE_TARGET.md`

**Данные / конфиг:** `TELEGRAM_BOT_TOKEN`, `MESSAGING_OUTBOUND_ENABLED` (из корневого `.env`)

**Git:** незакоммичено

**Риски/регрессии:**
- Не включать Telegram webhook на этот токен, пока жив Streamlit polling.
- Живая отправка идёт в реальные чаты вакансий.

**Следующий шаг:**
- Slice 2 inbound (кнопки → доменные события → PG) ближе к cutover; или паритет UX.

---

## 2026-07-27 — Статистика: drill-down в списки кандидатов

**Тип:** `feature`

**Сделано:**
- `GET /api/v1/candidates` — фильтры `client_id` / `vacancy_id` / `active_vacancies_only` / `hr_stage` / `client_status` / `preset` (`sent_to_client` | `in_client_zone` | `hires`); семантика как у `/stats/funnel`.
- Страница `/candidates` — таблица выборки со ссылками на карточку и вакансию.
- На `/stats` кликабельны KPI по кандидатам, строки воронки HR и статусов заказчика.

**Файлы:** `v2/backend/app/services/candidate_query.py`, `endpoints.py`, `schemas.py`, `v2/frontend/app/candidates/page.tsx`, `app/stats/page.tsx`, `lib/api.ts`, `globals.css`

**Git:** незакоммичено

**Следующий шаг:**
- Messaging Gateway или автопривязка PDF с Я.Диска.

---

## 2026-07-27 — Статистика v2: scope, HH, активность

**Тип:** `feature`

**Сделано:**
- Воронка: фильтр по вакансии/клиенту; метрики `sent_to_client` и «сейчас в зоне заказчика+»; блок оценки заказчика начинается с «отправлено на оценку».
- HH: `GET /stats/hh` — viewed / score>2 / shortlist / in_funnel / автоотсев / reject рекрутера / jobs.
- Активность: `GET /stats/activity?period=day|week|month|…` + мини-график на `/stats`.
- UI: чипы клиент/вакансия, период, легенда графика.

**Файлы:** `v2/backend/app/services/stats_service.py`, `endpoints.py`, `schemas.py`, `v2/frontend/app/stats/page.tsx`, `globals.css`, `lib/api.ts`, `v2/README.md`

**Git:** незакоммичено

**Следующий шаг:**
- Messaging Gateway или автопривязка PDF с Я.Диска.

---

## 2026-07-27 — Опросник: стена текста из дампа старой таблицы

**Тип:** `fix`

**Сделано:**
- Причина: в `documents.questions` / `interview_questionnaire` попал дамп старой grid-таблицы (`№ | Вопрос | … | False`) одной строкой — UI рисовал её как один вопрос.
- `normalize_questionnaire_list` / `parse_questionnaire_input` восстанавливают список вопросов из такого дампа.
- Починены данные вакансии «Менеджер по работе с блогерами» и кандидаты Белов / Пчельникова; бэкап `data/vacancies_db.json.bak_qfix`.

**Файлы:** `resume_ai.py`, `hri_full_v1.py`, `questionnaire_grid.py`, `data/vacancies_db.json`

**Следующий шаг:**
- Перезапустить Streamlit, открыть карточку — опросник списком по вопросам.

---



**Тип:** `feature`

**Сделано:**
- `POST /vacancies/{id}/documents/generate` — секции `profile` / `vacancy_text` / `questions` / `keywords`; поле `corrections` для перегенерации; `apply=true` пишет в PG.
- UI: в каждой строке аккордеона кнопка «Сгенерировать» / «Перегенерировать» + textarea коррективов (если уже есть текст).
- Заметки (`notes`) — только вручную. Streamlit не трогали.

**Файлы:** `v2/backend/app/services/ai_json.py`, `document_generate.py`, `endpoints.py`, `schemas.py`, `DocumentsEditor.tsx`, `DocumentBlock.tsx`, `globals.css`

**Следующий шаг:**
- Messaging Gateway или автопривязка PDF с Я.Диска.

---



**Тип:** `feature`

**Сделано:**
- `PATCH /vacancies/{id}/documents` — merge только `profile` / `vacancy_text` / `questions` / `keywords` / `notes` (не затирает `hh_search_criteria`).
- `GET …/documents/editor` — строки для textarea.
- UI вкладка «Документы»: редактор + просмотр; сохранение только в PostgreSQL.

**Файлы:** `v2/backend/app/services/vacancy_documents_write.py`, `endpoints.py`, `schemas.py`, `v2/frontend/components/DocumentsEditor.tsx`, `app/vacancies/[id]/page.tsx`, `v2/README.md`

**Следующий шаг:**
- Messaging Gateway или автопривязка PDF с Я.Диска.

---



**Тип:** `feature`

**Сделано:**
- API: `PATCH /candidates/{id}`, `POST /candidates/{id}/stage`, `POST /vacancies/{id}/candidates`, `DELETE /candidates/{id}`, `GET /meta/hr-stages`.
- Семантика этапа как в Streamlit (`hr_stage_history`, `client_review` → `client_status=wait`); без Google Calendar и warranty.
- UI: редактируемая карточка, фиксация этапа, создание/удаление; поля `resume_link` (PDF Я.Диск) и `hh_resume_link` (HH без контактов).
- Streamlit / `data/` не трогались.

**Файлы:** `v2/backend/app/services/candidate_write.py`, `endpoints.py`, `schemas.py`, `candidate_fields.py`, `v2/frontend/components/CandidateEditor.tsx`, `AddCandidateForm.tsx`, `app/candidates/[id]/page.tsx`, `vacancies/[id]/page.tsx`, `globals.css`, `v2/README.md`, `CUTOVER.md`, `ARCHITECTURE_TARGET.md`

**Следующий шаг:**
- Документы вакансии / ARQ или автопривязка PDF с Я.Диска к кандидату (без ломки Streamlit).

---



**Тип:** `feature`

**Сделано:**
- `POST /vacancies/{id}/hh-shortlist/{item_id}/to-candidate` — создаёт кандидата в PG (этап `resume_screening`, `cold_screening`, ссылка HH, AI-оценка из snapshot).
- Идемпотентность по `hh_resume_id`; после перевода — убрать из shortlist + `hh_seen` reason `in_funnel` (не попадает снова в cold search).
- UI: кнопка «В воронку» в shortlist + ссылка на карточку / список кандидатов.
- Имя без контактов: `HH · {title}` (FIO появятся после открытия контактов — отдельно).

**Файлы:** `v2/backend/app/services/hh_to_candidate.py`, `hh_seen.py`, `endpoints.py`, `schemas.py`, `v2/frontend/components/HhSearchPanel.tsx`, `globals.css`, `v2/README.md`, `ARCHITECTURE_TARGET.md`

**Следующий шаг:**
- Write path (этапы/карточки) или открытие контактов HH.

---



**Тип:** `decision` / `docs`

**Сделано:**
- Зафиксировано: Auth/роли/веб-кабинет заказчика не в ближайшем scope (один оператор; заказчик в мессенджере).
- Cutover — только после полной готовности и сверки актуальности данных (без dual-write).
- Обновлены актуальный план шагов и чеклист cutover.

**Файлы:** `ARCHITECTURE_TARGET.md`, `v2/README.md`, `v2/CUTOVER.md`

**Следующий шаг:**
- HH shortlist → кандидат + write path по сценариям HR.

---

## 2026-07-24 — v2: холодный поиск резюме HH + ИИ-оценка

**Тип:** `feature`

**Сделано:**
- Системный `HH_ACCESS_TOKEN` (вариант A): клиент поиска/просмотра **без** открытия контактов.
- ARQ job `hh_cold_search`: keywords → `GET /resumes` → `GET /resumes/{id}` → оценка ИИ (RouterAI).
- API defaults `GET /vacancies/{id}/hh-search-defaults`; создание job с `vacancy_id` + keywords.
- UI вкладка «Поиск HH» на карточке вакансии: shortlist со score 0–4, ссылка на HH, без контактов.

**Файлы:** `v2/backend/app/services/hh_*.py`, `resume_eval.py`, `vacancy_docs.py`, `workers/tasks.py`, `api/v1/endpoints.py`, `core/config.py`; `v2/frontend/components/HhSearchPanel.tsx`, `vacancies/[id]/page.tsx`; `v2/.env.example`

**Данные / конфиг:** `HH_ACCESS_TOKEN`, `HH_USER_AGENT`, `ROUTERAI_API_KEY` (из корневого `.env`)

**Git:** незакоммичено

**Риски/регрессии:**
- Нужен валидный employer token; иначе 403.
- Дневной лимит просмотров HH (~50 API) — `max_evaluate` по умолчанию 10.
- Открытие контактов / привязка в карточку — не сделаны.

**Следующий шаг:**
- Прописать `HH_ACCESS_TOKEN`, перезапустить API+worker, прогнать вкладку «Поиск HH».

---

## 2026-07-24 — HH: не оценивать повторно «не тех»

**Тип:** `feature`

**Сделано:**
- Таблица `hh_seen_resumes`: автобан при AI score ≤ 1; кнопка «✕» — отклонение рекрутером; shortlist тоже исключается из повторной оценки.
- При следующем поиске такие резюме пропускаются до ИИ, в выдаче пометка «уже смотрели».
- API: `GET/POST reject/DELETE` `/vacancies/{id}/hh-seen…`.

**Файлы:** `hh_seen.py`, `models.py`, `tasks.py`, `endpoints.py`, `schemas.py`, `HhSearchPanel.tsx`

**Данные:** новая таблица `hh_seen_resumes`

**Следующий шаг:**
- Прогнать поиск дважды на одной вакансии — низкие оценки не должны снова идти в ИИ.

---

## 2026-07-24 — HH: pre-filter + квоты запросов

**Тип:** `feature`

**Сделано:**
- Поиск по строкам keywords с приоритетом (квоты ~50/30/остаток) + добор при недоборе.
- Pre-filter до оценки: hard-отсев руководителей/reject по title; soft title — только для добора.
- Флаг `smart_prefilter` (вкл. по умолчанию) в воронке; в результатах — причина отсева и исходный запрос.

**Файлы:** `hh_prefilter.py`, `hh_client.py`, `hh_search_criteria.py`, `tasks.py`, `HhSearchPanel.tsx`

**Следующий шаг:**
- Прогнать поиск и проверить отсев «Руководитель направления» без траты слота ИИ.

---

## 2026-07-24 — HH UI: упрощение панели поиска

**Тип:** `refactor` / `ux`

**Сделано:**
- Три шага: Кого ищем → Воронка HH → Результаты.
- Портрет + комментарий на первом экране; must/reject/названия — в «Дополнительно».
- Убраны селекты приоритета у каждого фильтра и простыня FieldHint.
- Warnings: жёсткие сразу, info за «Подсказки»; primary CTA «Искать на HH» в футере.

**Файлы:** `HhSearchPanel.tsx`, `globals.css`

**Следующий шаг:**
- Открыть вкладку Поиск HH и пройти сценарий глазами.

---

## 2026-07-24 — HH: фильтр свежести резюме (period)

**Тип:** `feature`

**Сделано:**
- В воронку добавлено «Обновлено за»: 7 / 14 / 30 / 90 дней или без ограничения.
- В API HH уходит `period`; дефолт для новых критериев — 30 дней.
- Prefill ИИ может задавать `period_days`.

**Файлы:** `hh_search_criteria.py`, `hh_client.py`, `tasks.py`, `hh_criteria_prefill.py`, `HhSearchPanel.tsx`

**Следующий шаг:**
- Выбрать срок на вкладке Поиск HH, сохранить, прогнать поиск.

---

## 2026-07-24 — HH: AI-prefill критериев + комментарий рекрутера

**Тип:** `feature`

**Сделано:**
- Авто-prefill критериев при первом открытии пустых (профиль + документы + последняя расшифровка job по вакансии).
- Предупреждение `prefill_unreviewed` + confirm перед поиском, если правок рекрутера не было.
- Поле «Комментарий рекрутера» — приоритет №1 в оценке; усилен промпт (сфера, overqualified, ЗП).
- Кнопка «Перезаполнить из профиля (ИИ)».

**Файлы:** `hh_criteria_prefill.py`, `hh_search_criteria.py`, `resume_eval.py`, `endpoints.py`, `HhSearchPanel.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- На вакансии с профилем нажать «Перезаполнить из профиля», поправить комментарий, запустить поиск.

---

## 2026-07-24 — HH UI: правка портрета, пробелы, fit по-русски

**Тип:** `fix`

**Сделано:**
- Убран trim/filter при каждом нажатии в многострочных полях — можно ставить пробел, Enter и править середину строки портрета.
- Нормализация строк только при Save / запуске поиска.
- Fit в таблице: «Офис / Должность / Дорога» + да|частично|нет|неясно.

**Файлы:** `v2/frontend/components/HhSearchPanel.tsx`

**Следующий шаг:**
- Проверить правку портрета в середине строки после refresh UI.

---

## 2026-07-24 — HH поиск: критерии, портрет, shortlist

**Тип:** `feature`

**Сделано:**
- Критерии поиска хранятся в `vacancy.documents.hh_search_criteria` (сохранение сразу).
- UI: воронка HH + критерии ИИ + приоритеты Жёстко/Важно/Желательно + **редактируемый портрет** + warnings.
- Job/оценка: фильтры area/schedule/salary; промпт с портретом; флаги office/title/commute; сортировка.
- Shortlist у вакансии: таблица `hh_shortlist_items`, ★ из результатов, API list/add/delete.

**Файлы:** `hh_search_criteria.py`, `hh_client.py`, `resume_eval.py`, `tasks.py`, `endpoints.py`, `models.py`, `schemas.py`, `HhSearchPanel.tsx`, `documents_preview.py`

**Данные / конфиг:** новая таблица `hh_shortlist_items` (create_all)

**Git:** незакоммичено

**Следующий шаг:**
- Прогнать поиск на вакансии с заполненным портретом; проверить ★ shortlist.

---

## 2026-07-24 — HH OAuth: диагностика bad_authorization + скрипт авторизации

**Тип:** `fix` / `ops`

**Сделано:**
- Диагностика: `HH_ACCESS_TOKEN` в корневом `.env` невалиден (`bad_authorization`); `HH_REFRESH_TOKEN` жив, но refresh отвечает `token not expired` — в `.env` лежит не та пара access/refresh.
- Скрипт `v2/backend/scripts/hh_oauth.py` — OAuth code flow, проверка `/me` и `/resumes`, вывод строк для `.env`.
- Config: `HH_CLIENT_ID`, `HH_CLIENT_SECRET`, `HH_REFRESH_TOKEN`; дефолтный `HH_USER_AGENT` с реальным email.
- `hh_client.py`: auto-refresh при `token_expired`.

**Файлы:** `v2/backend/scripts/hh_oauth.py`, `app/core/config.py`, `app/services/hh_client.py`

**Данные / конфиг:** нужны валидные `HH_ACCESS_TOKEN` + `HH_USER_AGENT` в корневом `.env`

**Git:** незакоммичено

**Следующий шаг:**
- Запустить `hh_oauth.py`, обновить `.env`, перезапустить API + worker.

---

**Тип:** `feature`

**Сделано:**
- v2: левая панель «Клиент» по умолчанию на всех экранах (`DefaultClientSidebar` в `AppShell`).
- Streamlit: оценка резюме → `ai_comment_sections` (как профиль); UI свёрнут по умолчанию.
- Streamlit: настройка вакансии «Контрольное слово» (чекбокс + фраза); ИИ ищет только в сопроводительном, exact/fuzzy; бейдж в списке и карточке.
- v2: шкала HR-этапа на карточке кандидата (тест «на глаз»); свёрнутый блок комментария ИИ.
- Фото кандидата — отложено (без автовырезания из PDF).

**Файлы:** `v2/frontend/components/AppShell.tsx`, `DefaultClientSidebar.tsx`, `StageProgress.tsx`, `AiCommentBlock.tsx`, `candidates/[id]/page.tsx`, `globals.css`, `labels.ts`; `resume_ai.py`, `eval_ui.py`, `candidate_funnel.py`, `vacancy_prep.py`, `vacancy_store.py`, `models.py`, `hri_full_v1.py`, `yandex_disk_ingest.py`; v2 API `candidate_fields` / `schemas`

**Данные / конфиг:** новые поля вакансии `control_word_enabled`, `control_word`; у кандидата `control_word_*`, `ai_comment_sections` (в JSON вакансий)

**Git:** незакоммичено

**Риски/регрессии:**
- Старые оценки без `ai_comment_sections` показываются как текст «Итог» / plain.
- Fuzzy-поиск контрольного слова зависит от качества ответа ИИ.
- После импорта в v2 новые поля появятся только после повторного import snapshot.

**Следующий шаг:**
- В Streamlit: включить слово на тестовой вакансии и прогнать extract; в v2 глянуть шкалу этапа.

---

## 2026-07-23 — v2: ARQ job расшифровки (SpeechKit)

**Тип:** `feature`

**Сделано:**
- Сервис `transcription.py`: Яндекс.Диск → download → ffmpeg PCM → Object Storage → SpeechKit longRunningRecognize.
- ARQ-задача `transcribe_media` с прогрессом и отменой; текст в `job.payload.transcript`.
- API принимает `payload.source_url`; Settings подхватывает `YANDEX_*` / `FFMPEG_BINARY` из корневого `.env`.
- UI `/jobs`: поле ссылки + кнопка «Расшифровать», просмотр текста.

**Файлы:** `v2/backend/app/services/transcription.py`, `v2/backend/app/workers/tasks.py`, `v2/backend/app/workers/settings.py`, `v2/backend/app/api/v1/endpoints.py`, `v2/backend/app/core/config.py`, `v2/frontend/app/jobs/page.tsx`, `v2/backend/requirements.txt`, `v2/.env.example`, `v2/README.md`

**Данные / конфиг:** ключи SpeechKit из корневого `.env` (не дублировать в git); Redis без изменений

**Git:** незакоммичено

**Риски/регрессии:**
- Worker нужно перезапустить, чтобы подхватить `transcribe_media`.
- Длинные расшифровки пишутся в JSONB payload (для MVP ок).

**Следующий шаг:**
- Прогнать реальную ссылку с `/jobs`; затем generate_documents как ARQ.

---

## 2026-07-23 — v2: ARQ + Redis, страница «Задачи»

**Тип:** `feature`

**Сделано:**
- Redis (порт 6380) + ARQ worker; API `POST /jobs`, `GET /jobs`, cancel.
- Типы: `demo_progress` (прогресс без побочек), `import_legacy` (повторный импорт snapshot).
- UI `/jobs` с опросом статуса каждые 2 с; нав «Задачи» готов.
- Streamlit не затронут.

**Файлы:** `v2/backend/app/workers/**`, `v2/backend/app/services/jobs.py`, `v2/backend/app/api/v1/endpoints.py`, `v2/docker-compose.yml`, `v2/frontend/app/jobs/page.tsx`

**Данные / конфиг:** `REDIS_URL=redis://localhost:6380/0` в `v2/.env`

**Git:** незакоммичено

**Открыто / риски:**
- Генерация документов / SpeechKit ещё не как ARQ-задачи.

**Следующий шаг:**
- Первая «боевая» job: generate_documents или transcribe; либо auth.

---

## 2026-07-23 — v2: карточка кандидата + статистика воронки

**Тип:** `feature`

**Сделано:**
- API `GET /stats/funnel` — сводка по этапам HR, статусам заказчика, клиентам.
- API карточки кандидата обогащён полями из payload + название вакансии/клиента.
- UI: `/candidates/[id]`, клик по имени из списка вакансии.
- UI: `/stats` с фильтрами клиент / только «в работе»; пункт в нав без «скоро».

**Файлы:** `v2/backend/app/api/v1/endpoints.py`, `v2/backend/app/schemas.py`, `v2/backend/app/services/candidate_fields.py`, `v2/frontend/app/stats/page.tsx`, `v2/frontend/app/candidates/[id]/page.tsx`

**Git:** незакоммичено

**Следующий шаг:**
- Auth или write path / ARQ — по приоритету.

---

## 2026-07-23 — v2: единый читаемый формат документов

**Тип:** `fix`

**Сделано:**
- Нормализация документов перед UI: `{raw: pipe-table}` → структура как у JSON-профиля (подразделение, задачи, требования…).
- Опросник из markdown-таблицы → карточки «вопрос / пример ответа».
- Уже структурированные документы (как у «Графический дизайнер») не ломаются.
- JSON-режим по-прежнему показывает исходник.

**Файлы:** `v2/frontend/lib/documentNormalize.ts`, `v2/frontend/components/DocumentBlock.tsx`, `v2/frontend/lib/labels.ts`

**Git:** незакоммичено

**Следующий шаг:**
- Auth или write path / ARQ.

---

## 2026-07-23 — v2 UI: RU-лейблы, сайдбар клиентов, читаемые документы

**Тип:** `feature`

**Сделано:**
- Статусы HR-этапа и оценки заказчика на русском (ключи в БД без изменений).
- Фильтр «Клиент» перенесён в левую боковую панель.
- Документы по умолчанию в читаемом виде; переключатель «JSON» по желанию.
- Колонка кандидатов: «Оценка заказчика» вместо путаницы с «Клиент».

**Файлы:** `v2/frontend/lib/labels.ts`, `v2/frontend/components/**`, `v2/frontend/app/**`

**Git:** незакоммичено

**Следующий шаг:**
- Auth или write path / ARQ — по приоритету.

---

## 2026-07-23 — v2 read-only: история, фильтр клиента, документы

**Тип:** `feature`

**Сделано:**
- Страница «История» на реальных `document_generations` + карточка снимка.
- Фильтр вакансий по клиенту (chips).
- Карточка вакансии: вкладки Кандидаты / Документы (превью).
- API: preview в `/history`, `GET /history/{id}`, `document_keys` в vacancy detail.
- В нав «История» без метки «скоро».

**Файлы:** `v2/frontend/**`, `v2/backend/app/api/v1/endpoints.py`, `v2/backend/app/schemas.py`, `v2/backend/app/services/documents_preview.py`

**Git:** незакоммичено

**Следующий шаг:**
- Auth или write path / ARQ — по приоритету пользователя.

---

## 2026-07-23 — v2 UI: вакансии В работе/Архив + nav-макет

**Тип:** `feature`

**Сделано:**
- Тема UI: кремовый фон, голубые акценты/навигация.
- Список вакансий: вкладки «В работе» / «Архив»; в работе — дата старта + дни; в архиве — период + дни + мягкий исход.
- Мягкий `outcome` в API (`success` / `client_cancelled` / `no_result`) по `close_reason` или наличию hire-этапа — не финальная доменная модель.
- Шапка с пунктами-заглушками: Статистика, Задачи, История, Настройки, Клиентская зона.

**Файлы:** `v2/frontend/**`, `v2/backend/app/api/v1/endpoints.py`, `v2/backend/app/schemas.py`, `v2/backend/app/services/vacancy_outcome.py`

**Git:** незакоммичено

**Следующий шаг:**
- Сверить UX с пользователем; затем auth или write path / ARQ.

---

## 2026-07-23 — MVP v2: каркас рядом со Streamlit

**Тип:** `feature`

**Сделано:**
- Создан изолированный каталог `v2/` (отдельный docker compose, порты 5433/8000/3000).
- PostgreSQL-схема: organizations, clients, vacancies, candidates, document_generations, messaging_channels, vacancy_templates, jobs, import_runs.
- Импортёр `json → PG` (только чтение `data/`): 8 clients, 11 vacancies, 91 candidates, 17 history, 4 templates, 7 channels.
- FastAPI read-only `/api/v1/*` + Next.js read-only UI списка вакансий/кандидатов.
- Cutover-чеклист: `v2/CUTOVER.md`. Корневой Streamlit/bot/compose не менялись.

**Файлы:** `v2/**`, `ARCHITECTURE_TARGET.md`, `ARCHITECTURE.md`

**Данные / конфиг:** импорт читает `data/`; PG volume `hr_v2_pgdata`; `v2/.env` из `.env.example`

**Git:** незакоммичено

**Поведение / регрессии:**
- Текущая рабочая версия не затронута; dual-write нет.

**Открыто / риски:**
- Auth, write API, ARQ, Messaging Gateway — следующие фазы.
- Docker Desktop должен быть запущен для локального PG.

**Следующий шаг:**
- Фаза 1: auth + более полный read UI / сверка полей с Streamlit; либо write path по приоритету.

---

## Шаблон записи (копировать для новых сессий)

```markdown
## YYYY-MM-DD — Краткий заголовок

**Тип:** `feature` | `fix` | `refactor` | `deploy` | `decision` | `incident` | `checkpoint`

**Сделано:**
- …

**Файлы:** `path/to/file.py`, …

**Данные / конфиг:** `data/…`, `.env` ключи, миграции

**Git:** `commit` / тег `…` / ветка `…` / незакоммичено

**Поведение / регрессии:**
- …

**Открыто / риски:**
- …

**Следующий шаг:**
- …
```

---

## 2026-08-06 — Волна A хвост: Q6 Q7 Q9 Q10

**Тип:** `feature` + `fix`

**Сделано:**
- После создания вакансии редирект на `?section=docs` + CTA при пустом профиле.
- Полные `JOB_TYPE_LABELS` на `/jobs`.
- Пауза 0.4 с между HH AI-оценками; job errors через `_safe_err`.
- `loading.tsx` + skeleton CSS на vacancies/candidates/jobs/stats.

**Файлы:** `CreateVacancyForm.tsx`, `DocumentsEditor.tsx`, `jobs/page.tsx`, `tasks.py`, `app/**/loading.tsx`, `globals.css`, `v2/AUDIT.md`

**Git:** не закоммичено

**Следующий шаг:**
- M11 JSONB normalize script → M1 Alembic baseline.

---

## 2026-08-06 — AUDIT.md + Волна A (Q1–Q4, Q8, Q11, Q12)

**Тип:** `docs` + `fix`

**Сделано:**
- Оформлен `v2/AUDIT.md` (findings + волны + Q11/Q12/M11 + оговорки).
- Волна A: AI JSON fail→`ai_error_logs` без HH-бана; SpeechKit deadline; delete candidate/vacancy FK cleanup; Telegram idempotency + offset; sanitize PII; AI input truncate 12k.
- `create_all` при старте API для новых таблиц до Alembic.

**Файлы:** `v2/AUDIT.md`, `models.py`, `ai_errors.py`, `log_sanitize.py`, `ai_json.py`, `resume_eval.py`, `hh_seen.py`, `transcription.py`, `candidate_write.py`, `vacancy_write.py`, `messaging/idempotency.py`, `inbound.py`, `telegram_poller.py`, `tasks.py`, `main.py`

**Данные / конфиг:** новые таблицы `ai_error_logs`, `processed_messaging_updates` (через create_all)

**Git:** не закоммичено

**Следующий шаг:**
- Перезапустить API/worker/poller; smoke delete + HH eval parse-fail; затем Волна A UX (Q6/Q7/Q9/Q10) или B/M11.

---

## 2026-07-27 — Оценка резюме: битый JSON от ИИ

**Тип:** `fix`

**Сделано:**
- Для оценки по резюме включён JSON mode (`response_format=json_object`).
- Усилен `parse_ai_json_response`: пропущенные запятые между полями, сырые переносы в строках, закрытие обрезанного JSON.
- Лимит `resume_eval` max_tokens по умолчанию 2500 (меньше обрезки ответа).

**Файлы:** `ai_helpers.py`, `resume_ai.py`

**Git:** не закоммичено

**Следующий шаг:**
- Повторить «Оценить по резюме» в карточке кандидата.

---

## 2026-07-25 — Бот: сеть восстановлена, фикс падения session.close

**Тип:** `incident` + `fix`

**Сделано:**
- Проверка: Streamlit жив, `api.telegram.org` доступен; бот был мёртв после таймаутов.
- Перезапуск бота — polling для `@hr_yourboxBot` снова активен.
- Исправлено `_close_bot_session`: у AiohttpSession нет `.closed`, из‑за этого бот падал при сетевом retry.

**Файлы:** `bot.py`

**Git:** не закоммичено

**Следующий шаг:**
- В чате «Пульс» снова нажать «Отменить встречу» у Белова.

---

## 2026-07-22 — Настройки: отправка инструкции в Telegram-чат

**Тип:** `feature`

**Сделано:**
- Добавлен текст инструкции для группового чата (`CHAT_INSTRUCTIONS_HTML`): статусы, комментарии, команды, напоминания; отдельно — как открыть резюме и запись по ссылкам в карточке.
- Убрана строка про `/start` в группе (она про личное меню вакансий, не про работу в чате).
- В Настройках → Telegram-бот: выбор чата и кнопка «Отправить инструкцию в чат».

**Файлы:** `telegram_bot_commands.py`, `hri_full_v1.py`

**Git:** не закоммичено

**Следующий шаг:**
- Проверить отправку в реальный чат из Настроек.

---

## 2026-07-16 — Разделение архитектуры: текущая и целевая

**Тип:** `docs` + `decision`

**Сделано:**
- `ARCHITECTURE.md` явно помечен как текущая версия (Streamlit); добавлены ограничения и ссылка на целевой документ.
- Создан `ARCHITECTURE_TARGET.md`: стек v2, мультитенантность, Messaging Gateway, ARQ/jobs, виджет «Задачи», upload/S3, миграция без dual-write.

**Файлы:** `ARCHITECTURE.md`, `ARCHITECTURE_TARGET.md`

**Git:** не закоммичено

**Следующий шаг:**
- При старте реализации v2 — ADR по фазе 0 и SQL-схема.

---

## 2026-07-16 — Архитектура и инструкции в приложении

**Тип:** `docs`

**Сделано:**
- Обновлён `ARCHITECTURE.md`: мастер документов, мульти-источники, доп. материалы, скрипты локального запуска, привязка чатов, env.
- Вкладка «Инструкции»: документы по вакансии, запуск с Mac, expander «Настройка нового Telegram-чата» (8 шагов).
- Настройки: подсказка у «Мои чаты Telegram», актуализирован блок статуса бота.

**Файлы:** `ARCHITECTURE.md`, `hri_full_v1.py`

**Git:** не закоммичено

**Следующий шаг:**
- При необходимости — коммит документации.

---

## 2026-07-16 — Документы вакансии: мастер, мульти-источники, медиа

**Тип:** `feature` + `fix`

**Сделано:**
- Мастер «Создать или обновить документы» в существующей вакансии: материалы, импорт, анкета HR, корректировка, предпросмотр, выбор полей, история.
- Режим «Профиль + дополнения»: письменный профиль + несколько записей/файлов → полный пакет с приоритетами и списком противоречий.
- Сохранение черновика в историю под другой должностью без применения к текущей вакансии.
- Опросник: JSON mode + восстановление битого JSON в `parse_ai_json_response`.
- Лимит загрузки Streamlit 600 МБ; поиск `ffmpeg` через Homebrew при запуске с ярлыка macOS.
- Архивные вакансии: документы можно править с предупреждением.

**Файлы:** `vacancy_prep.py`, `vacancy_tab.py`, `hri_full_v1.py`, `ai_helpers.py`, `resume_ai.py`, `.streamlit/config.toml`, `scripts/start_local.sh`

**Данные / конфиг:** `server.maxUploadSize = 600`; пакет в `data/history/` (gitignore)

**Git:** commit `454277f`, push `origin/main`

**Риски/регрессии:** большие видео — долгая расшифровка; нужен перезапуск Streamlit после обновления.

**Следующий шаг:**
- Сгенерировать полный комплект для «Менеджер по работе с блогерами» (профиль уже в вакансии + запись).

---

## 2026-07-15 — Документы для существующей вакансии

**Тип:** `feature`

**Сделано:**
- В «Документы по вакансии» добавлен мастер создания и обновления документов после регистрации вакансии.
- Источники: аудио/видео, TXT, DOCX, PDF, XLSX, вставленный текст, готовые документы и анкета HR.
- Режим «Профиль + дополнения»: основной профиль, несколько записей и файлов обрабатываются одновременно.
- Приоритеты: указания HR → письменный профиль → дополнительные материалы; противоречия выводятся в предпросмотре.
- Лимит загрузки Streamlit увеличен с 200 до 600 МБ для записей до 393 МБ.
- Локальный launcher добавляет Homebrew в `PATH`; код находит ffmpeg в `/opt/homebrew/bin` и `/usr/local/bin`.
- В предпросмотре пакет можно сохранить в историю под другой должностью без применения к текущей вакансии.
- Ошибочно загруженный профиль сохранён отдельно как пакет «Менеджер по работе с блогерами».
- Для существующего пакета доступны корректирующие указания с дополнительным файлом/записью.
- Перед сохранением показывается предпросмотр и выбор заменяемых документов; прочие поля не затираются.
- Текущий и новый пакеты сохраняются в историю; архивные вакансии также можно обновлять с предупреждением.

**Файлы:** `vacancy_prep.py`, `vacancy_tab.py`, `hri_full_v1.py`, `.streamlit/config.toml`, `scripts/start_local.sh`

**Данные / конфиг:** схема `documents` не менялась; `server.maxUploadSize = 600`; добавлен пакет `data/history/20260715_154109_Менеджер_по_работе_с_блогерами.json`

**Git:** изменения не закоммичены

**Риски/регрессии:** генерация и транскрибация требуют доступных внешних API; сохранение выполняется по `vacancy.id`.

**Следующий шаг:**
- Перезапустить Streamlit и проверить пустую и заполненную вакансию.

---

## 2026-07-15 — Опросник: восстановление невалидного JSON от ИИ

**Тип:** `fix`

**Сделано:**
- Для подсказок и уточнений опросника включён JSON mode модели.
- Парсер восстанавливает типовые ошибки: лишнюю запятую, одинарные кавычки и ключи без кавычек.
- Если провайдер не поддерживает `response_format`, запрос автоматически повторяется без него.
- Проверены `py_compile` и три варианта повреждённого JSON.

**Файлы:** `ai_helpers.py`, `resume_ai.py`

**Данные / конфиг:** не менялись

**Git:** изменения не закоммичены

**Следующий шаг:**
- Повторно сформировать опросник у кандидата вакансии «Программист 1С».

---

## 2026-07-10 — Доп. материалы кандидата в Telegram

**Тип:** `feature`

**Сделано:**
- В карточке: поля «Название» + «Ссылка» и кнопка «Отправить материал в чат» (замена «Отправить в чат задание»).
- Reply на primary-карточку: «Добавлены материалы по кандидату ФИО: [ссылка]».
- Primary-сообщение в чате обновляется блоком «Доп. материалы»; список хранится в `extra_materials`.
- Сброс полей после отправки через revision ключа (без правки session_state у живого виджета).
- Клиентскую веб-зону не трогали.

**Файлы:** `candidate_funnel.py`, `telegram_client.py`, `telegram_notify.py`, `models.py`, `vacancy_store.py`

**Данные / конфиг:** поле кандидата `extra_materials: [{id, title, url, sent_at}]`

**Git:** commit `5433920`, push `origin/main`

**Следующий шаг:**
- Проверить отправку материала при доступном Telegram API.

---

## 2026-07-10 — Бот: один экземпляр, proxy, диагностика

**Тип:** `fix`

**Сделано:**
- `bot.lock` — нельзя запустить два `bot.py` с одним токеном.
- `TELEGRAM_PROXY` в `.env` / `bot.py` / `network_ipv4.py`.
- `scripts/status_local.sh` — статус процессов и доступность `api.telegram.org`.
- `stop_local.sh` гасит лишние `bot.py`.

**Файлы:** `bot.py`, `network_ipv4.py`, `.env.example`, `scripts/stop_local.sh`, `scripts/status_local.sh`

**Git:** commit `5433920`, push `origin/main`

**Следующий шаг:**
- При недоступности API — VPN или бот только на VPS.

---

## 2026-07-06 — Локальный запуск с рабочего стола (macOS)

**Тип:** `feature`

**Сделано:**
- Фоновый запуск Streamlit + бота: `scripts/start_local.sh`, `scripts/stop_local.sh` (`nohup`, PID в `run/`).
- Ярлыки на Desktop через `osacompile` (shell-.app не работали по двойному клику в Finder).
- `install_mac_launcher.sh` пересобирает Start/Stop HR Agent на рабочем столе.

**Файлы:** `scripts/`, `.gitignore` (`run/`), `ARCHITECTURE.md`

**Git:** commit `31b61da`, push `origin/main`

**Следующий шаг:**
- После `git pull` снова `./scripts/install_mac_launcher.sh`; двойной клик Start HR Agent.

---

## 2026-07-06 — ARCHITECTURE.md

**Тип:** `decision`

**Сделано:**
- Добавлен `ARCHITECTURE.md`: стек (Streamlit, aiogram, JSON), структура проекта, схема Telegram → `vacancies_db.json`.

**Файлы:** `ARCHITECTURE.md`

**Следующий шаг:**
- При крупных изменениях архитектуры обновлять документ.

---

## 2026-07-05 — Яндекс.Диск: Шульга — запись и задание

**Тип:** `fix` / `incident`

**Сделано:**
- Диагностика: папка «Тестовое Шульга» не сопоставлялась (первое слово «Тестовое», не фамилия); пути были в `seen_paths`, ссылки в карточке пустые.
- Повторная синхронизация актуальным кодом (`f98da97`): привязаны `video_link` и `task_link` у Шульга Вера Андреевна + записи Сердюк/Сотникова.
- Данные сохранены в `data/vacancies_db.json`.

**Файлы:** `yandex_disk_ingest.py` (фикс уже в `f98da97`), `data/vacancies_db.json`

**Git:** `f98da97` (в `origin/main`)

**Поведение / регрессии:**
- Без перезапуска Streamlit после обновления кода синхронизация идёт старым модулем в памяти.

**Следующий шаг:**
- Перезапустить Streamlit; при необходимости «Синхронизировать с Диском» в «Автозагрузка».

---

## 2026-06-24 — Яндекс.Диск: Кейкуль — Unicode + PDF задания

**Тип:** `fix`

**Сделано:**
- Сопоставление имён: NFC-нормализация (файл `Кейкуль.mp4` с macOS NFD «й» не совпадал с «Кейкуль Алиса» в базе).
- Задания: PDF в папке «Задания» привязываются к карточке (раньше только подпапки).
- `_file_matches_candidate`: фамилия ищется в токенах длинного имени файла (`Тестовое_задание_Алиса_Кейкуль_...`).

**Файлы:** `yandex_disk_ingest.py`

**Git:** этот коммит

**Следующий шаг:**
- Перезапустить Streamlit → «Синхронизировать» (или F5 на карточке Кейкуль).

---

## 2026-06-24 — Опросник: чекбоксы оценок (Хорошо / Удовлетворительно)

**Тип:** `fix`

**Сделано:**
- Оценки в опроснике терялись при rerun: карточка перечитывалась с диска, а клик только менял память.
- Кэш `interview_questionnaire` в `st.session_state` между перерисовками; сброс кэша при перегенерации опросника.
- Кнопки ↑↓ и оценки сохраняются до «Сохранить изменения по кандидатам».

**Файлы:** `questionnaire_grid.py`, `candidate_funnel.py`

**Git:** этот коммит

**Следующий шаг:**
- Перезапустить Streamlit; кликнуть «Хорошо» — должна остаться галочка ☑.

---

## 2026-06-24 — Общий чат: только встречи заказчика (подтверждённые HR)

**Тип:** `fix`

**Сделано:**
- Добавлена проверка `is_client_confirmed_group_meeting` (`meeting_hr_confirmed` + дата/время встречи).
- Напоминание «Через час встреча» в общий чат — только для таких встреч; первичные собеседования HR помечаются `skip_send` без отправки.
- Отмена кандидатом утром в общий чат — только для встреч с заказчиком; первичные HR остаются только в личке.
- Запрос «Подтвердить встречу HR» (mcf) без изменений — только при назначении заказчиком.

**Файлы:** `client_actions.py`, `telegram_reminders.py`, `interview_attendance.py`

**Git:** этот коммит

**Поведение / регрессии:**
- Утреннее «Сегодня собеседование» в личку HR — по-прежнему для всех встреч с датой/временем.

**Следующий шаг:**
- Перезапустить `bot.py`; проверить Кривонос (нет сообщений в группу) и Дулатова (есть).

---

## 2026-06-28 — Merge feature/local-ux-improvements → main

**Тип:** `decision`

**Сделано:**
- Fast-forward merge `3980981..ff07691` (11 коммитов): local UX, Яндекс.Диск, опросник, `/meetings`, стабильность карточек.

**Git:** `main` @ `ff07691`; локально на 11 коммитов впереди `origin/main`

**Следующий шаг:**
- `git push origin main` и перезапуск Streamlit + `bot.py`.

---

## 2026-06-28 — Yandex/карточки: анти-конвульсионные правки (без Platrum)

**Тип:** `fix`

**Сделано:**
- Кнопки «Открыть …» получают ту же ревизию ключей `_rN`, что и поля ссылок — после синхр. с Диском не залипают старые URL.
- `yandex_path_is_valid`, сброс битых `yadisk:`-ссылок, fuzzy-подбор подпапок, починка видео при невалидном пути.
- `get_yandex_download_url` — `None` вместо fallback на корень папки при ошибке.

**Файлы:** `candidate_funnel.py`, `resume_ai.py`, `yandex_disk_ingest.py`

**Git:** незакоммичено (вместе с `/meetings`)

**Следующий шаг:**
- Перезапустить Streamlit; синхронизация с Диском → проверить поля и «Открыть запись».

---

## 2026-06-28 — Откат Platrum + команда /meetings в Telegram

**Тип:** `fix` · `feature`

**Сделано:**
- Откат ветки до последнего push (`4e810fd`) — интеграция Platrum убрана.
- Команда **`/meetings`** в меню группы (первая строка): предстоящие встречи с подтверждением HR.
- Фильтр: дата/время назначены, `meeting_hr_confirmed`, встреча ещё не прошла; сортировка по дате.

**Файлы:** `interview_schedule.py`, `telegram_reminders.py`, `telegram_bot_commands.py`, `telegram_bot_handlers.py`, `deploy/TELEGRAM_CLIENT.md`, `hri_full_v1.py`

**Git:** откат `710924b`; новые правки незакоммичены

**Следующий шаг:**
- Перезапустить `bot.py`; в группе проверить `/meetings` в меню ☰.

---

## 2026-06-26 — Опросник: шаблон вакансии + уточнения по резюме

**Тип:** `feature`

**Сделано:**
- Основные вопросы кандидата = копия шаблона из «Документы по вакансии» (одинаковые для всех).
- ИИ заполняет «В резюме» и поле `уточнения_по_резюме`, не меняя основные вопросы.
- Шаблон нейродизайнера: 10 вопросов → вакансии id 4, 11.
- UI: блок «Уточнения по резюме кандидата», кнопка «Обновить по резюме».

**Файлы:** `resume_ai.py`, `candidate_funnel.py`, `questionnaire_grid.py`, `data/vacancies_db.json`, `data/questionnaire_templates/neurodesigner_interview.json`

**Git:** незакоммичено

**Следующий шаг:**
- На нейродизайнере: «Сформировать опросник» → 10 вопросов + персональные уточнения.

---

## 2026-06-26 — Опросник: не пропадал после «Сохранён»

**Тип:** `fix`

**Сделано:**
- Убрана лишняя проверка `exp_key` — список вопросов рисуется, если опросник есть в данных.
- После «Сформировать опросник» / оценки карточка остаётся раскрытой (`st.session_state[exp_key] = True`).
- Успех выводится баннером над списком кандидатов (`_set_cand_funnel_flash`), а не внутри правой колонки.

**Файлы:** `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить на Кейкуль Алиса: «Сформировать опросник» → вопросы видны слева, баннер сверху.

---

**Тип:** `fix`

**Сделано:**
- Диагностика: «Чупрова Анастасия» только на вакансии «Трутень» (`is_test: true`); поиск с `include_test=False` её не видел.
- Галочка «Искать в тестовых вакансиях» (по умолчанию включена).
- Подсказка, если кандидат найден только на тестовых, а галочка выключена.
- Бейдж «тестовая вакансия» в результатах.

**Файлы:** `candidate_search.py`, `candidate_search_ui.py`

**Данные / конфиг:** без изменений (`data/vacancies_db.json` — id 12 «Трутень»)

**Git:** незакоммичено

**Следующий шаг:**
- Проверить поиск «Чупрова» во вкладке Вакансии → Поиск.

---

## 2026-06-24 — Статистика: вакансии в периоде, тестовые, детализация закрытий

**Тип:** `feature`

**Сделано:**
- Показатель **«Взято в работу вакансий»** (созданы в периоде).
- У **«Закрыто успешно»** — детализация: начатых ранее периода / начатых и закрытых в периоде.
- Чекбокс **«Тестовая вакансия»** при создании; поле `is_test` в вакансии.
- Тестовые вакансии исключены из статистики продуктивности.
- Зачистка `data/vacancies_db.json`: в статистике id 1, 3, 4, 7, 11; остальные `is_test=true`.
- Список вакансий в работе за период — с датами (две «Нейро-дизайнер» видны отдельно).

**Файлы:** `period_productivity.py`, `stats_tab.py`, `vacancy_stats_filter.py`, `vacancy_prep.py`, `hri_full_v1.py`, `productivity_ai.py`, `data/vacancies_db.json`

**Данные / конфиг:** `is_test` у вакансий в `vacancies_db.json`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить июнь 2026 на вкладке «Статистика».

## 2026-06-24 — Поиск кандидатов (фаза 3)

**Тип:** `feature`

**Сделано:**
- Подвкладка **«Поиск»** во вкладке «Вакансии»: ФИО, телефон, фрагмент резюме/комментария.
- Поиск по активным и архивным вакансиям (без тестовых).
- В результате — этап, вакансия, фрагмент резюме, **копирование в активную вакансию**.

**Файлы:** `candidate_search.py`, `candidate_search_ui.py`, `vacancy_tab.py`, `hri_full_v1.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить поиск «Бучнева» / «Кривонос» и копирование в нужную вакансию.

---


**Тип:** `feature`

**Сделано:**
- Убрана верхняя вкладка **«История»**; файлы в `data/history/` сохраняются как раньше.
- Блок **«Прошлые генерации»** в «Документы по вакансии» + подсказка при создании вакансии с похожим названием.
- Подвкладка **«Архив»** во вкладке «Вакансии»: просмотр кандидатов и документов.
- **Копирование карточки** из архива в активную вакансию с обнулением этапов, интервью, задания, оценки ИИ.

**Файлы:** `vacancy_tab.py`, `candidate_copy.py`, `vacancy_history_ui.py`, `candidate_funnel.py`, `vacancy_prep.py`, `hri_full_v1.py`

**Git:** незакоммичено

**Следующий шаг:**
- Фаза 3: глобальный поиск кандидата по ФИО (+ копирование из результатов).

---


**Тип:** `feature`

**Сделано:**
- Под тремя KPI (закрыто / взято в работу / приглашены) — списки вакансий, ФИО кандидатов и привязка к вакансии.
- При успешном закрытии — предупреждение, если кандидат с выходом не найден в данных.

**Файлы:** `period_productivity.py`, `stats_tab.py`, `productivity_ai.py`

**Git:** незакоммичено

---


**Тип:** `feature`

**Сделано:**
- Вкладка «Статистика» переделана: вместо сводки по всем активным — **продуктивность за календарный период** (месяц / квартал / полугодие).
- 7 показателей: отобрано, первичные собеседования, на рассмотрение, одобрено заказчиком, приглашены на работу/стажировку, закрыто успешно, закрыто заказчиком.
- Сравнение с предыдущим периодом и **среднее за доступные календарные месяцы** (до 12).
- Список вакансий в работе за период + их количество.
- ИИ-анализ по кнопке (`productivity_ai.py`) с контекстом воронки, отказов, подразделений.
- Реестр гарантии и детальная статистика по одной вакансии сохранены.

**Файлы:** `period_productivity.py`, `productivity_ai.py`, `stats_tab.py`

**Git:** незакоммичено

**Поведение / регрессии:**
- Показатели по этапам точны только при наличии `hr_stage_history` с датами; старые записи могут занижать цифры.

**Следующий шаг:**
- Проверить вкладку «Статистика» на реальных данных за июнь 2026.

---


**Тип:** `fix`

**Сделано:**
- Опросник рисуется только в **раскрытой** карточке кандидата (свёрнутые не грузят десятки виджетов).
- Правки заметок в опроснике остаются в памяти; на диск — по кнопке «Сохранить изменения по кандидатам».
- Убраны `persist + rerun` на каждое поле опросника; rerun только при ↑↓ и смене оценки HR.
- Стабильные `_qid` для вопросов добавляются при миграции кандидата (`models.migrate_candidate`).

**Файлы:** `candidate_funnel.py`, `questionnaire_grid.py`, `models.py`

**Git:** незакоммичено

**Поведение / регрессии:**
- После правок опросника нужно явно нажать «Сохранить изменения по кандидатам».

**Следующий шаг:**
- Проверить вход в вакансию и раскрытие карточек (Нейро-дизайнер / Кривонос).

---


**Тип:** `fix`

**Сделано:**
- Табличный вид опросника удалён — остался только список.
- Перемещение ↑↓: стабильный `_qid` сохраняется в JSON при первом открытии; сброс виджетов после перестановки.
- Убран `st.rerun()` внутри карточки (мешал сохранению порядка).

**Файлы:** `questionnaire_grid.py`, `resume_ai.py`, `candidate_funnel.py`

**Git:** commit `56e0846`, push `feature/local-ux-improvements`

---

## 2026-06-26 — Опросник: список с оценками и уточнениями для ИИ

**Тип:** `feature`

**Сделано:**
- Список: блок «Уже есть в резюме», стрелки ↑↓ для порядка вопросов, оценки Хорошо/Удовлетворительно/Сомнительно/Нет.
- Оценки по вопросам передаются в «Оценить по интервью»; ИИ может согласиться или оспорить оценку HR.
- Отдельное поле «Уточнения для оценки по интервью» (вместо общего комментария HR в этом процессе).

**Файлы:** `questionnaire_grid.py`, `resume_ai.py`, `candidate_funnel.py`, `hri_full_v1.py`, `ai_helpers.py`, `migrate_data.py`

**Git:** commit `56e0846`

**Следующий шаг:**
- Проверить: расставить оценки → «Оценить по интервью» → вывод ИИ учитывает оценки и уточнения.

---

## 2026-06-26 — Опросник: таблица как в Google Sheets

**Тип:** `feature`

**Сделано:**
- Таблица опросника в карточке кандидата: вопрос, «Что уже есть в резюме», ответ, эталон, оценка (Сомн но ок / Норм / Нет).
- ИИ заполняет колонку «В резюме» при формировании опросника; кнопка «Обновить «В резюме»».
- Переключатель «Таблица / Список» для отката к старому виду.

**Файлы:** `questionnaire_grid.py`, `resume_ai.py`, `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить на кандидате с резюме: «Сформировать опросник» → таблица и колонка «В резюме».

---

## 2026-06-26 — Яндекс.Диск: повторная привязка записей (webm)

**Тип:** `fix`

**Сделано:**
- Файлы в `seen_paths` без ссылки в карточке снова обрабатываются (`Максимова.webm`).
- Видео `.webm` и `media_type: video` распознаются надёжнее.
- Неверная чужая ссылка на видео/задание сбрасывается перед привязкой.

**Файлы:** `yandex_disk_ingest.py`, `resume_ai.py`

---

## 2026-06-26 — Яндекс.Диск: новые резюме не путать с чужими

**Тип:** `fix`

**Сделано:**
- Сопоставление по **фамилии** (файл «Максимова…» больше не привязывается к Антоновой).
- При синхронизации сбрасываются ошибочно привязанные резюме.
- Повторная обработка PDF из `seen_paths`, если карточка ещё не создана.

**Файлы:** `yandex_disk_ingest.py`

**Следующий шаг:**
- Синхронизировать вакансию Трутень — должна появиться Максимова.

---

## 2026-06-26 — Яндекс.Диск: автообновление карточек после синхр.

**Тип:** `fix`

**Сделано:**
- После синхронизации сбрасываются «залипшие» поля Streamlit (новая ревизия ключей виджетов).
- Перезагрузка интерфейса через отложенный `st.rerun()` — без ручного F5.
- Сообщение о результате синхронизации показывается после обновления.

**Файлы:** `candidate_funnel.py`, `vacancy_tab.py`

---

## 2026-06-26 — Яндекс.Диск: ссылки видны в карточках после синхр.

**Тип:** `fix`

**Сделано:**
- Streamlit не показывал ссылки: виджеты хранили пустое значение в session_state — добавлена подстановка из базы.
- `seen_paths` больше не блокирует повторную привязку, если поле в карточке пустое.
- После синхронизации страница всегда перезагружается.

**Файлы:** `yandex_disk_ingest.py`, `candidate_funnel.py`, `vacancy_tab.py`

**Git:** незакоммичено

---

## 2026-06-26 — Яндекс.Диск: задания и записи в карточки

**Тип:** `fix`

**Сделано:**
- Сопоставление по фамилии: папка «Чупрова задание» → кандидат «Чупрова Анастасия».
- Автоподбор подпапки: «Записи» в настройках находит «Записи собеседований» на Диске.
- Ссылки на задание и запись попадают в `task_link` / `video_link` при синхронизации.

**Файлы:** `yandex_disk_ingest.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить Streamlit и нажать «Синхронизировать с Яндекс» для вакансии Трутень.

---

## 2026-06-26 — Яндекс.Диск: кнопка синхронизации в шапке вакансии

**Тип:** `feature`

**Сделано:**
- Кнопка «Синхронизировать с Яндекс» в шапке открытой вакансии (рядом с шаблонами и статистикой).
- При синхронизации сохраняются настройки папки (`root_url`, подпапки, `seen_paths`) в `vacancies_db.json`.
- Убрана автосинхронизация при открытии вкладки — только по кнопке.
- Повторно не создаёт карточки: `seen_paths` + проверка уже привязанной ссылки на резюме.

**Файлы:** `vacancy_tab.py`, `candidate_funnel.py`, `vacancy_store.py`, `yandex_disk_ingest.py`

**Git:** незакоммичено

**Следующий шаг:**
- Один раз задать ссылку в «Автозагрузка», дальше жать кнопку в шапке после новых файлов на Диске.

---

## 2026-06-26 — Яндекс.Диск: просмотр файлов в браузере

**Тип:** `fix`

**Сделано:**
- `yandex_link_for_display` строит URL `/d/HASH/папка/файл` (сегменты пути), а не `?dialog=slider`.
- Ссылки `/i/` и `public_url` из API по-прежнему отдаются как есть.
- Скачивание для PDF/видео остаётся через `get_yandex_download_url` (автозагрузка, Whisper).

**Файлы:** `resume_ai.py`, `candidate_funnel.py`, `telegram_notify.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить Streamlit и проверить «Открыть запись» / PDF в браузере.

---

## 2026-06-26 — Автозагрузка с папки Яндекс.Диска

**Тип:** `feature`

**Сделано:**
- Синхронизация опубликованной папки вакансии: «Резюме» (PDF), «Записи» (видео), «Задания» (папки).
- Сопоставление файлов с кандидатами по имени; новые PDF → новые кандидаты (опционально).
- Вкладка «Автозагрузка»: ссылка на папку, подпапки, автосинхронизация, сброс истории.
- Формат ссылок `yadisk:…` для файлов внутри опубликованной папки.

**Файлы:** `yandex_disk_ingest.py`, `resume_ai.py`, `candidate_funnel.py`, `telegram_notify.py`, `vacancy_store.py`, `hri_full_v1.py`

**Git:** commit + push

**Следующий шаг:**
- Проверить «Открыть запись» / Telegram на файле из подпапки.

---

## 2026-06-26 — Явка: повтор до ответа + гарантия в Настройках

**Тип:** `feature`

**Сделано:**
- Утреннее напоминание в личку: с 09:00 и каждые 30 мин, пока нет ответа по кнопкам (до начала встречи).
- Настройки → «Гарантия»: срок по умолчанию (1–6 мес) для новых блоков гарантии у кандидатов.

**Файлы:** `interview_attendance.py`, `telegram_reminders.py`, `models.py`, `vacancy_store.py`, `app_settings.py`, `warranty.py`, `candidate_funnel.py`, `hri_full_v1.py`

**Данные / конфиг:** `data/app_settings.json` (создаётся при сохранении в UI)

**Git:** commit + push

**Следующий шаг:**
- Перезапустить бота; проверить повтор утреннего напоминания на следующей встрече.

---

## 2026-06-24 — Явка: тексты и правила общего чата

**Тип:** `fix`

**Сделано:**
- Убрана строка «Отметил(а): …» из утренних сообщений в личке.
- В общий чат: только «за час» (с пометкой явки) и сразу «кандидат отменил»; подтверждение и отмена заказчиком — только личка.

**Файлы:** `interview_attendance.py`, `telegram_bot_handlers.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить бота.

---

## 2026-06-24 — Подтверждение явки: утро ЛС + напоминание за час

**Тип:** `feature`

**Сделано:**
- В 09:00 (TELEGRAM_REMINDER_TZ) бот шлёт в личный чат HR напоминание уточнить явку кандидата на собеседование сегодня.
- Три кнопки: «Подтверждаю», «Отмена кандидатом», «Отмена заказчиком».
- За ~1 ч до встречи — сообщение в общий чат с пометкой: подтверждено / без подтверждения; отмена кандидатом — сразу в чат; отмена заказчиком — без сообщения за час.

**Файлы:** `interview_attendance.py`, `telegram_reminders.py`, `telegram_bot_handlers.py`, `interview_schedule.py`, `models.py`, `client_actions.py`, `vacancy_store.py`, `.env.example`

**Данные / конфиг:** `TELEGRAM_HR_USER_ID` — личный chat_id для утренних напоминаний

**Git:** незакоммичено

**Следующий шаг:**
- Добавить `TELEGRAM_HR_USER_ID` в `.env`, перезапустить бота, проверить сценарий на тестовой встрече.

---

## 2026-06-24 — Гарантия: «Выход на работу» и дата из оффера

**Тип:** `feature`

**Сделано:**
- Блок «Гарантия» показывается также при этапе «Выход на работу».
- Для «Оффер» подпись даты: «Дата планируемого выхода на работу (точка отсчета срока гарантии)».
- На «Стажировка» / «Выход на работу» дата из оффера подставляется по умолчанию (для того же кандидата), редактируется; при сохранении пересчитывается срок гарантии.

**Файлы:** `warranty.py`, `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить сценарий: Оффер → дата → Стажировка/Выход на работу с корректировкой даты.

---

## 2026-06-24 — План A: стажировка, гарантия, вкладка Статистика

**Тип:** `feature`

**Сделано:**
- HR-этап «Выход на стажировку» (`internship`) между «Оффер» и «Вышел на работу».
- При этапах «Оффер» / «Стажировка» — дата начала гарантии и срок 1–6 мес (30 дн./мес).
- Реестр «На гарантии» и кнопка «Гарантийный поиск» (связь с архивной вакансией).
- Вкладка «Статистика»: настраиваемая сводка по 9 этапам + детальная воронка.
- В карточке вакансии — только ключевые показатели (кандидаты + дни в работе).

**Файлы:** `models.py`, `warranty.py`, `stats_tab.py`, `candidate_funnel.py`, `vacancy_tab.py`, `hri_full_v1.py`

**Git:** ветка `feature/local-ux-improvements`, незакоммичено

**Следующий шаг:**
- Проверить: зафиксировать «Оффер» с датой → реестр гарантии → архив → гарантийный поиск.

---

## 2026-06-24 — UI: период поиска вместо id вакансии

**Тип:** `feature`

**Сделано:**
- Модуль `vacancy_display.py`: формат «апрель–май 26» или «24.04.–16.05.26» (при коллизиях).
- Статистика, гарантия, списки вакансий, история пакетов — без видимого id.
- id в данных и ключах Streamlit не менялся.

**Файлы:** `vacancy_display.py`, `stats_tab.py`, `vacancy_tab.py`, `vacancy_prep.py`, `hri_full_v1.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить статистику «Графический дизайнер» и закрытие вакансии без найма.

---

## 2026-06-24 — Статистика: офферы, статусы заказчика, закрытие вакансии

**Тип:** `fix`

**Сделано:**
- Исправлен `reached_hr_stage`: отказы больше не считаются как «прошли оффер».
- Конверсия офферов: только реально получавшие оффер / из отправленных заказчику; отдельно «сейчас на оффере».
- Статусы заказчика: «сейчас ждут» vs «всего отправлялись»; только кандидаты на оценке.
- «Одобрены заказчиком» включает и прямой «Оффер» без «Встречи».
- Архив без найма запрещён; кнопка «Вакансия закрыта заказчиком».

**Файлы:** `models.py`, `vacancy_stats.py`, `vacancy_close.py`, `vacancy_tab.py`, `master_stats.py`, `hri_full_v1.py`

**Git:** незакоммичено

**Следующий шаг:**
- Перезапустить Streamlit и проверить вакансию «Графический дизайнер».

---

## 2026-06-24 — Воронка: история этапов, пропали со связи

**Тип:** `fix`

**Сделано:**
- Модуль `funnel_metrics.py`: подсчёт по `hr_stage_history`, не по текущему этапу.
- Первичный контакт — после отсева резюме, кроме «отсев → сразу отказ».
- Новая строка «Не вышли на контакт / пропали со связи».
- Первичное собеседование ≥ список на рассмотрение; задание/тест ≤ список на рассмотрение.

**Файлы:** `funnel_metrics.py`, `stats_tab.py`, `vacancy_stats.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить цифры на «Графический дизайнер».

---

## 2026-06-24 — UI: период поиска вместо id вакансии

**Тип:** `feature`

**Сделано:**
- Карточка кандидата сворачивается после «Отправить в общий чат» (смена этапа на «На оценке у заказчика»).
- В клиентской зоне карточка сворачивается после «Сохранить изменения».
- Порядок вкладок: Вакансии → История → Настройки → Инструкции.
- Инструкции обновлены под локальную работу (бот на Mac, без серверных/Cloudflare формулировок).

**Файлы:** `candidate_funnel.py`, `client_zone.py`, `hri_full_v1.py`

**Git:** ветка `feature/local-ux-improvements`

**Следующий шаг:**
- Проверить в Streamlit: отправка в TG, фиксация этапа, сохранение в клиентской зоне.

---

## 2026-06-24 — Ускорение ИИ-пайплайна (ветка теста)

**Тип:** `feature`

**Сделано:**
- Ветка `feature/ai-pipeline-speedup`: разделены кнопки «Оценить по резюме» и «Сформировать опросник».
- `ai_helpers.py`: лимиты `max_tokens` по задачам, обрезка профиля/промптов, `/no_think`, тайминг в лог.
- `hri_full_v1_config.yaml`: `max_tokens_by_task`, `task_limits`, `disable_thinking: true`.
- Убрана двойная ffmpeg-конвертация в `transcribe_video_from_link`.
- Бенчмарк: оценка резюме ~6 с (было ~33 с), опросник ~17 с (было ~185 с); модель `qwen3.5-plus` без смены.

**Файлы:** `ai_helpers.py`, `resume_ai.py`, `candidate_funnel.py`, `hri_full_v1.py`, `hri_full_v1_config.yaml`

**Git:** merged в `main` (`dde3ee0`..`fc75fee`), push `origin/main`

**Риски/регрессии:**
- Опросник теперь отдельная кнопка — привычный one-click flow изменился.
- `disable_thinking` / `extra_body.reasoning` может не поддерживаться RouterAI (есть fallback).

**Следующий шаг:**
- Мониторить качество оценок и опросников на проде.

---

**Тип:** `checkpoint`

### Стек и запуск

| Компонент | Технология | Точка входа |
|-----------|------------|-------------|
| HR-приложение | Streamlit, Python | `streamlit run hri_full_v1.py` |
| Telegram-бот | aiogram 3 | `python bot.py` |
| ИИ | OpenAI-клиент → RouterAI (`hri_full_v1_config.yaml`, модель `qwen/qwen3.5-plus-20260420`) | `ROUTERAI_API_KEY` |
| Расшифровка | Whisper (локально) / Yandex SpeechKit | `transcribe.py`, `resume_ai.py` |
| Календарь | Google Calendar API | `google_calendar.py`, `data/google_calendar_*.json` |
| Деплой | Docker Compose | `docker-compose.yml`: `hr-app` :8501, `hr-bot` |

**Зависимости:** `requirements.txt` (streamlit, openai, aiogram, whisper, google-api-python-client, …).

### Хранение данных (JSON, `data/`)

| Файл | Назначение |
|------|------------|
| `vacancies_db.json` | Вакансии, кандидаты, документы, `telegram_posts`, статусы |
| `chats_db.json` | Привязка Telegram-чатов к отделам |
| `departments.json` | Подразделения для клиентских зон |
| `vacancy_templates.json` | Шаблоны вакансий (документы + chat_id) |
| `history/` | Архив генераций ИИ (вкладка «История») |

Запись: `vacancy_store.py` (fcntl lock, atomic write). Слияние полей бота при сохранении из UI: `TELEGRAM_MERGE_FIELDS`.

### HR-приложение (`hri_full_v1.py`)

**Вкладки:** Вакансии · Инструкции · История · Настройки.

**Вакансии** (`vacancy_tab.py`):
- В работе: кандидаты, документы, статистика, архив, digest в чат
- Создание: с нуля / из шаблона (`create_vacancy_from_template`)
- Шаблоны: библиотека + полный редактор документов (`vacancy_prep.render_templates_library`)
- Кнопка в меню вакансии: «Добавить вакансию в шаблоны»

**Документы** (`vacancy_prep.py`): профиль, текст вакансии, опросник, ключевые слова; генерация из расшифровки / импорта / анкеты HR; экспорт Word/PDF/JSON.

**Кандидаты** (`candidate_funnel.py`): воронка HR, оценка ИИ (`resume_ai.py`), Telegram-отправка, Google Calendar при назначении собеседования.

**Клиентские зоны (Streamlit pages):** `/client?dept=…` (`pages/client.py`), `/master` (`pages/master.py`).

### Telegram-бот

**Модули:** `bot.py`, `telegram_bot_handlers.py`, `telegram_workflow.py`, `telegram_client.py`, `telegram_candidate_nav.py`, `telegram_reminders.py`.

**Клиентская зона в чате:** кнопки статусов (Встреча / Подумать / Отказ / Оффер), комментарий, назначение встречи, подтверждение HR (`TELEGRAM_HR_CONFIRM_USERNAME`), редактирование карточки на месте.

**Навигация:** `/candidates`, переход к карточке, `/pending`.

**Автонапоминания** (`telegram_reminders.py`, цикл в `bot.py`):
- Просрочка оценки (≥24 ч с отправки карточки, повтор ≥24 ч)
- «Подумать» ≥5 дней
- Встреча за ~60 мин
- Сводки: вт 18:00, пт 15:00 (`TELEGRAM_REMINDER_TZ`)
- **Сб–Вс:** автоматические напоминания не отправляются (`is_reminder_day_off`)
- Reply-напоминания: 👆 на карточку выше; на самой карточке: 👇

**Досылка задания:** отдельное сообщение + обновление primary-карточки (`send_task_completed_to_chat` → `refresh_primary_candidate_card_in_chat`). ФИО в сообщении о задании — ссылка на резюме.

### Шаблоны вакансий

`vacancy_template_store.py`: сохранение/обновление по имени, валидация незаполненных полей, `add_vacancy_to_templates`, редактирование документов во вкладке «Шаблоны».

### Git и откат

| Тег | Коммит | Смысл |
|-----|--------|-------|
| `pre-vacancy-templates` | `46360d5` | Бекап перед шаблонами (полная Telegram-зона) |
| `pre-telegram-full-chat` | `a4c04f6` | До напоминаний, /pending, полного workflow |

**Состояние на 2026-06-06:** `main` ahead of `origin/main` на 2 коммита.  
**Незакоммичено:** шаблоны вакансий, правки напоминаний (выходные, 👆), `vacancy_template_store.py`, правки `ROLLBACK.md`.

---

## 2026-06-17 — Синхронизация календаря, транскрипция (SpeechKit-only), запуск на Mac-сервере

**Тип:** `fix`

**Сделано:**
- Добавлен флажок «Не удалять событие из Google Calendar» при смене этапа кандидата (чтобы не сносить ранее назначенное собеседование).
- Полностью исключён Whisper из проекта: удалены ветки локальной транскрипции, транскрипция аудио/видео оставлена только через Яндекс SpeechKit.
- Убраны «тихие» ошибки SpeechKit: явная проверка `.env` ключей, понятные ошибки для ffmpeg/S3/SpeechKit API.

**Файлы:** `candidate_funnel.py`, `interview_schedule.py`, `vacancy_prep.py`, `hri_full_v1.py`, `requirements.txt`, `requirements-server-mac2012.txt`, `deploy/ROLLBACK.md`

**Данные / конфиг:**
- Требуются ключи: `YANDEX_API_KEY`, `YANDEX_BUCKET_NAME`, `YANDEX_ACCESS_KEY_ID`, `YANDEX_SECRET_ACCESS_KEY`

**Поведение / регрессии:**
- Локальная транскрипция (Whisper) больше недоступна — только SpeechKit.

---

## 2026-06-17 — Удаление вакансии (двухступенчатое подтверждение)

**Тип:** `feature`

**Сделано:**
- Добавлено удаление вакансии с подтверждением в 2 шага (вкладка «Вакансии» и список в «Настройки»).
- Добавлены функции удаления вакансии в `vacancy_store.py` (по `id` и по `title`).

**Файлы:** `vacancy_tab.py`, `hri_full_v1.py`, `vacancy_store.py`

**Поведение / регрессии:**
- Удаление необратимо: вакансия и кандидаты удаляются из `data/vacancies_db.json`.

---

## 2026-06-17 — Бот: устойчивость к сетевым сбоям

**Тип:** `fix`

**Сделано:**
- `delete_webhook`, `get_me` и регистрация команд — с повторами при таймаутах.
- Polling перезапускается автоматически после `TelegramNetworkError` (без падения процесса).
- `delete_webhook` при неудаче не блокирует запуск; сессия закрывается перед переподключением.

**Файлы:** `bot.py`

**Данные / конфиг:** опционально `.env`: `TELEGRAM_NETWORK_RETRY_ATTEMPTS`, `TELEGRAM_POLL_RESTART_DELAY_SEC`

**Следующий шаг:**
- Скопировать `bot.py` на сервер и перезапустить бота; убедиться, что локальный бот остановлен.

---

## 2026-06-17 — Вакансии: повторное название для новой итерации

**Тип:** `fix`

**Сделано:**
- При создании вакансии проверяется только наличие **активной** вакансии с тем же названием.
- После архивации можно создать новую итерацию с тем же `title` (другой `id`, свои кандидаты).

**Файлы:** `hri_full_v1.py`

**Следующий шаг:**
- Реализация варианта A (lazy-import + раздельные requirements) для минимального VPS.

---

## 2026-06-17 — Инструкции: актуализация и гайд по Telegram

**Тип:** `docs`

**Сделано:**
- Обновлена вкладка «Инструкции» в приложении: шаблоны, архив/итерации вакансий, удаление, SpeechKit, календарь.
- Добавлен раздел «Работа в Telegram-чате» простым языком, без эмодзи.
- Обновлён текст справки бота (`/help`, `HELP_TEXT_HTML`).

**Файлы:** `hri_full_v1.py`, `telegram_bot_commands.py`

Инструкции отката: `deploy/ROLLBACK.md`. Деплой VPS: `deploy/ИНСТРУКЦИЯ.md`, `deploy/sync-to-server.sh`.

### Известные ограничения (из кода)

- `create_vacancy`: запрет только **двух активных** вакансий с одним `title`; архивные итерации с тем же названием разрешены.
- `process_interview_reminders` в `interview_schedule.py`: **отключены** (пустой return).
- Напоминание «за час до встречи» не уходит в Сб–Вс; для встреч в выходные окно может быть пропущено без догонки.
- `telegram_posts`: нет автоочистки при ручном удалении сообщений в Telegram (есть `prune_stale_telegram_posts`, привязка через действия на карточке).
- Гибридная архитектура (HR на ноутбуке + бот в облаке) **не реализована** — один shared `data/` на машине/сервере.

### Ближайшие цели (вывод из состояния репозитория)

- Закоммитить незавершённую работу: шаблоны + напоминания.
- Продакшен: Docker на VPS по `deploy/ИНСТРУКЦИЯ.md`.
- Операционная устойчивость бота 24/7 (отдельно от HR) — обсуждалось, в коде нет sync-слоя.

---

## 2026-06-17 — Напоминания: понедельник 10:00 вместо ночи

**Тип:** `fix`

**Сделано:**
- Накопленные за сб–вс автонапоминания не отправляются в понедельник до 10:00 МСК (`MONDAY_CATCHUP_HOUR`).
- Напоминание о встрече: отдельное правило — не раньше 08:00 и не в сб–вс; в пн с 08:00 (не ждёт 10:00).
- Обновлены тексты справки в приложении и боте.

**Файлы:** `telegram_reminders.py`, `telegram_bot_commands.py`, `hri_full_v1.py`

**Git:** незакоммичено

**Риски/регрессии:**
- Напоминание «за час до встречи» в сб–вс не уходит; в будни — не раньше 08:00 (встречи с 09:00). В пн 08:00–10:00 уходит только о встрече, не просрочки оценки.

**Следующий шаг:**
- Перезапустить `bot.py` на сервере после выкладки.

---

## 2026-06-17 — Портфолио в карточке кандидата

**Тип:** `feature`

**Сделано:**
- Настройка вакансии `show_portfolio_field`: чекбокс при создании и в «Настройки карточки кандидата» у существующей вакансии.
- Поле `portfolio_link` у кандидата (в UI — только если настройка включена).
- Ссылка «Портфолио кандидата» в Telegram-сообщении при заполнении.

**Файлы:** `vacancy_store.py`, `vacancy_prep.py`, `candidate_funnel.py`, `hri_full_v1.py`, `models.py`, `telegram_notify.py`, `telegram_client.py`, `telegram_bot_handlers.py`, `telegram_workflow.py`

**Git:** commit `53a8ffb` (бэкап до фичи), портфолио — незакоммичено

**Следующий шаг:**
- Проверить отправку карточки с портфолио в тестовом чате.

---

## 2026-06-17 — История: применение пакета к вакансии

**Тип:** `fix`

**Сделано:**
- Корневая причина: две вакансии «Нейро-дизайнер» (id 4 архив, id 11 активная); сохранение по `title` попадало в первую в списке.
- Сохранение из истории — по `vacancy_id` (`update_vacancy_docs_by_id`, полная замена documents).
- В списке применения при дублях названий показываются id и дата создания.
- Добавлены spinner, превью содержимого пакета, сообщения о загрузке/успехе/ошибке; автовыбор связанной вакансии.
- Вкладка вынесена в `render_history_tab` (`vacancy_prep.py`).

**Файлы:** `vacancy_prep.py`, `hri_full_v1.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить сценарий «Загрузить → Нейро-дизайнер → Применить» в UI.

---

## 2026-06-17 — Инструкция деплоя Timeweb 4 ГБ

**Тип:** `docs`

**Сделано:**
- Добавлена пошаговая инструкция: регистрация Timeweb, VPS 4 ГБ, SSH, sync, Docker, `.env`, firewall 8501, проверка, обновления, бэкап, troubleshooting.
- В `ИНСТРУКЦИЯ.md` — ссылка на новый гайд; убраны устаревшие упоминания Whisper.

**Файлы:** `deploy/TIMEWEB_4GB.md`, `deploy/ИНСТРУКЦИЯ.md`

**Git:** незакоммичено

**Следующий шаг:**
- Создать VPS по чеклисту и пройти шаги 1–8.

---

## 2026-06-18 — Деплой на Timeweb Cloud (Reasonable Lacerta)

**Тип:** `deploy`

**Сделано:**
- VPS Cloud MSK 50 (2 vCPU, 4 ГБ, 50 ГБ), Ubuntu 22.04, IP `85.239.40.180`.
- SSH, sync проекта, Docker, `.env`, `docker compose up -d --build`.
- Firewall Timeweb: входящий TCP 8501; `http://85.239.40.180:8501/master` открывается.

**Файлы:** на сервере `/opt/hr_ai_agent`

**Данные / конфиг:** `.env` и `data/` на сервере (не в git)

**Git:** без коммита деплоя

**Следующий шаг:**
- Убедиться, что бот не запущен локально на Mac; проверить Telegram-бот на сервере.

---

## 2026-06-18 — Telegram: принудительный IPv4 на VPS

**Тип:** `fix`

**Сделано:**
- Диагностика Timeweb: `google: 301`, DNS ок, `telegram-ipv4: 302`, `telegram-ipv6: 000`.
- Добавлен `network_ipv4.py` (requests через IPv4); aiogram `AiohttpSession` с `family=AF_INET`.
- В `TIMEWEB_4GB.md` — troubleshooting IPv6/Telegram.

**Файлы:** `network_ipv4.py`, `telegram_notify.py`, `bot.py`, `deploy/TIMEWEB_4GB.md`

**Git:** незакоммичено

**Следующий шаг:**
- `sync-to-server.sh` + `docker compose down` + `up -d --build` (network_mode: host).

---

## 2026-06-18 — Docker: network_mode host для Telegram

**Тип:** `fix`

**Сделано:**
- С хоста `telegram-ipv4: 302`, из контейнера `container: 000` — bridge Docker на Timeweb не выходит к Telegram.
- `docker-compose.yml`: `network_mode: host` для `hr-app` и `hr-bot` (убраны ports/extra_hosts/sysctls).

**Файлы:** `docker-compose.yml`, `deploy/TIMEWEB_4GB.md`

**Git:** незакоммичено

**Следующий шаг:**
- Пересоздать контейнеры на сервере и проверить Telegram в UI.

---

## 2026-06-18 — Временный откат на локальный Mac

**Тип:** `decision`

**Сделано:**
- Telegram API с Timeweb РФ недоступен (блокировка); WireGuard отложен.
- Решение: HR-приложение + бот снова на Mac (VPN); сервер — позже, с синхронизацией `data/`.

**Файлы:** без изменений кода

**Следующий шаг:**
- Остановить контейнеры на сервере; запустить Streamlit + bot.py на Mac.

---

## 2026-06-18 — Диагностика: Павлова, календарь, ИИ

**Тип:** `incident`

**Сделано:**
- Павлова Мария (вакансия 3): `ai_score=null`, `calendar_event_id=""` — данные не сохранились после действий в UI.
- RouterAI: API отвечает, оценка резюме Павловой в тесте — score 3 (~2 мин).
- Google Calendar: токен `invalid_grant` (файл есть, но авторизация протухла).
- `get_calendar_status()` теперь проверяет реальный доступ, не только наличие token.json.

**Файлы:** `google_calendar.py`

**Git:** незакоммичено

**Следующий шаг:**
- Переподключить Google Calendar в Настройках; повторить оценку и «Зафиксировать этап» для Павловой.

---

## 2026-06-18 — Баннер несохранённых изменений: Сохранить вместо Rerun

**Тип:** `fix`

**Сделано:**
- Текст плашки: «Есть несохранённые изменения по кандидатам — нажмите Сохранить».
- Кнопка «💾 Сохранить» вместо «Rerun»; по клику вызывается `_persist_vacancy_candidates`.
- После сохранения плашка скрывается, показывается сообщение об успехе.

**Файлы:** `corporate_ui.py`, `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить в UI: изменить поле кандидата → плашка → «Сохранить».

---

## 2026-06-18 — Правило: понимание задачи перед кодом

**Тип:** `decision`

**Сделано:**
- Добавлено правило `understand-before-code.mdc`: перед нетривиальными правками — бриф из 4 блоков и одобрение через AskQuestion.
- Исключения: тривиальные фиксы, явное «делай», read-only запросы.

**Файлы:** `.cursor/rules/understand-before-code.mdc`

**Git:** незакоммичено

**Следующий шаг:**
- Применять правило на следующих фичах/рефакторингах.

---

## 2026-06-18 — Fix: белый экран после «Сохранить» в плашке

**Тип:** `fix`

**Сделано:**
- Сохранение из плашки вынесено из `pending_banner.container()` — вызов `empty()` внутри контейнера ломал отрисовку Streamlit.
- Кнопки плашки и «Сохранить изменения» используют общий блок persist + `st.rerun()`.

**Файлы:** `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить: правка поля → плашка → «Сохранить» без белого экрана.

---

## 2026-06-18 — Fix: белый экран при «Зафиксировать этап»

**Тип:** `fix`

**Сделано:**
- `st.rerun()` внутри цикла карточек кандидатов обрывал отрисовку страницы — перенесён в `_request_candidates_rerun()` + `_flush_candidates_rerun()` в конце вкладки.
- Сообщения календаря и сохранения — через отложенный flash (`_set_cand_funnel_flash`), не `st.success` перед rerun.

**Файлы:** `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить «Зафиксировать этап» у Ипполитовой и сохранение из плашки.

---

## 2026-06-22 — Карточки кандидатов свёрнуты по умолчанию

**Тип:** `fix`

**Сделано:**
- При входе в раздел «Кандидаты» все карточки открывались: `expanded=expander_rev == 0` давал `expanded=True` при первом рендере.
- Заменено на `expanded=False`; механизм `expander_rev` после «Зафиксировать этап» сохранён (смена `key` принудительно сворачивает карточку).

**Файлы:** `candidate_funnel.py`

**Git:** незакоммичено

**Следующий шаг:**
- Проверить вход в «Кандидаты» и сворачивание после смены этапа.

---

## 2026-06-18 — Сворачивание карточки после фиксации этапа

**Тип:** `fix`

**Сделано:**
- Streamlit запоминал состояние expander — после «Зафиксировать этап» карточка оставалась открытой.
- При фиксации увеличивается `expander_rev` и меняется `key` expander → карточка принудительно сворачивается.

**Файлы:** `candidate_funnel.py`

**Git:** незакоммичено

---

## 2026-06-18 — Checkpoint: UI кандидатов, деплой Timeweb, календарь

**Тип:** `checkpoint`

**Сделано:**
- Плашка несохранённых изменений: кнопка «Сохранить» вместо Rerun; fix белого экрана (отложенный rerun + flash).
- «Зафиксировать этап»: отложенный rerun, сворачивание карточки через `expander_rev`.
- Google Calendar: проверка токена, console OAuth, порт 8765.
- Деплой Timeweb: `deploy/TIMEWEB_4GB.md`, `network_mode: host`, `network_ipv4.py`, `TELEGRAM_FORCE_IPV4`.
- Правило Cursor: `understand-before-code.mdc`.

**Файлы:** `candidate_funnel.py`, `corporate_ui.py`, `google_calendar.py`, `google_calendar_auth.py`, `bot.py`, `network_ipv4.py`, `docker-compose.yml`, `Dockerfile`, `deploy/`, `.cursor/`

**Данные / конфиг:** `.env.example` — `TELEGRAM_FORCE_IPV4`

**Git:** commit `da428f7`, push `main`

**Открыто / риски:**
- Telegram с Timeweb VPS (РФ) недоступен — бот локально с VPN; WireGuard отложен.
- Google Calendar token у части пользователей протух — нужна переавторизация.

**Следующий шаг:**
- Локально: Streamlit + bot.py; при необходимости — новый проект в отдельной папке Cursor.
