"""Fictional demo org for «Посмотреть демо без регистрации»."""

from __future__ import annotations

import base64
import logging
import secrets
import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.auth import ROLE_HR_RECRUITER, hash_password
from app.core.demo import DEMO_ORG_NAME, DEMO_ORG_SLUG, DEMO_USER_EMAIL, DEMO_USER_NAME
from app.db import models
from app.services.candidate_write import apply_hr_stage
from app.services.clients_write import CHAT_MODE_DEPARTMENTS, KIND_COMPANY, KIND_DEPARTMENT, _next_client_id, _slugify
from app.services.users import create_organization
from app.services.vacancy_write import empty_vacancy_documents, next_vacancy_id

logger = logging.getLogger("hr_api.demo_showcase")

_ZONE_TOKEN = "demo-avrora-zone"
DEMO_CONTENT_VERSION = 6
DEMO_PHONE = "+7 000 000 00 00"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _days_ago(days: int, hour: int = 10) -> datetime:
    return _now().replace(hour=hour, minute=0, second=0) - timedelta(days=days)


def _q(
    question: str,
    in_resume: str,
    answer: str,
    rating: str,
    note: str,
) -> dict[str, Any]:
    return {
        "вопрос": question,
        "уточняющие_вопросы": [],
        "уточнения_по_резюме": [],
        "проверяет_требование": "",
        "категория": "",
        "пример_ответа": "",
        "в_резюме": in_resume,
        "ответ": "",
        "ответ_кандидата": answer,
        "оценка_ии": rating,
        "пояснение_ии": note,
        "оценка_hr": "",
    }


def _digest(summary: str, qa: list[tuple[str, str]], communication: str) -> dict[str, Any]:
    return {
        "summary": summary,
        "qa": [{"q": q, "a": a} for q, a in qa],
        "communication": communication,
        "created_at": _iso(_now()),
    }


def _ai(
    score: int,
    summary: str,
    match: str,
    experience: list[str],
    risks: list[str],
    interview: list[str],
) -> dict[str, Any]:
    return {
        "ai_score": score,
        "ai_comment": summary,
        "ai_comment_sections": {
            "соответствие": match,
            "опыт_и_навыки": experience,
            "риски": risks,
            "проверить_на_интервью": interview,
            "итог": summary,
        },
    }


def _png_rgb(width: int, height: int, rgb: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


def _aurora_logo_data_url() -> str:
    """Simple geometric mark (navy + gold stripe) — not copied from another org."""
    width, height = 240, 72
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            if x < 14:
                pixels.extend(b"\xd4\xa0\x3a")  # gold
            elif 28 <= x <= 58 and 16 <= y <= 56:
                pixels.extend(b"\xf4\xf1\xe8")  # letter-block
            else:
                pixels.extend(b"\x1b\x3a\x4a")  # navy
    raw = _png_rgb(width, height, bytes(pixels))
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _demo_docs(*, profile: str, vacancy_text: str, questions: str) -> dict[str, Any]:
    return {
        "profile": profile,
        "vacancy_text": vacancy_text,
        "questions": questions,
        "keywords": "",
        "notes": "",
    }


def _reset_demo_funnel(db: Session, org_id: uuid.UUID) -> None:
    client_ids = list(
        db.scalars(select(models.Client.id).where(models.Client.organization_id == org_id))
    )
    if not client_ids:
        return
    vac_ids = list(
        db.scalars(select(models.Vacancy.id).where(models.Vacancy.client_id.in_(client_ids)))
    )
    cand_ids = (
        list(db.scalars(select(models.Candidate.id).where(models.Candidate.vacancy_id.in_(vac_ids))))
        if vac_ids
        else []
    )
    if cand_ids:
        post_ids = list(
            db.scalars(
                select(models.MessagingPost.id).where(models.MessagingPost.candidate_id.in_(cand_ids))
            )
        )
        if post_ids:
            db.execute(delete(models.MessagingAction).where(models.MessagingAction.post_id.in_(post_ids)))
            db.execute(delete(models.MessagingPost).where(models.MessagingPost.id.in_(post_ids)))
        db.execute(delete(models.Candidate).where(models.Candidate.id.in_(cand_ids)))
    if vac_ids:
        db.execute(delete(models.HhShortlistItem).where(models.HhShortlistItem.vacancy_id.in_(vac_ids)))
        db.execute(delete(models.HhSeenResume).where(models.HhSeenResume.vacancy_id.in_(vac_ids)))
        db.execute(
            update(models.InboxItem)
            .where(models.InboxItem.vacancy_id.in_(vac_ids))
            .values(vacancy_id=None)
        )
        db.execute(
            update(models.DocumentGeneration)
            .where(models.DocumentGeneration.vacancy_id.in_(vac_ids))
            .values(vacancy_id=None)
        )
        db.execute(
            update(models.Job).where(models.Job.vacancy_id.in_(vac_ids)).values(vacancy_id=None)
        )
        db.execute(delete(models.Vacancy).where(models.Vacancy.id.in_(vac_ids)))
    db.execute(
        update(models.VacancyTemplate)
        .where(models.VacancyTemplate.client_id.in_(client_ids))
        .values(client_id=None)
    )
    db.execute(
        update(models.DocumentGeneration)
        .where(models.DocumentGeneration.client_id.in_(client_ids))
        .values(client_id=None)
    )
    db.execute(update(models.Job).where(models.Job.client_id.in_(client_ids)).values(client_id=None))
    db.execute(
        delete(models.MessagingChannel).where(models.MessagingChannel.client_id.in_(client_ids))
    )
    db.execute(
        delete(models.Client).where(
            models.Client.organization_id == org_id, models.Client.parent_id.is_not(None)
        )
    )
    db.execute(delete(models.Client).where(models.Client.organization_id == org_id))
    db.flush()


def org_is_demo(org: models.Organization | None) -> bool:
    return bool(org and (org.slug or "") == DEMO_ORG_SLUG)


def client_org_is_demo(db: Session, client: models.Client | None) -> bool:
    if not client:
        return False
    org = db.get(models.Organization, client.organization_id)
    return org_is_demo(org)


def _unique_client_slug(db: Session, name: str) -> str:
    base = _slugify(name) or "client"
    slug = base
    n = 1
    while db.scalar(select(models.Client.id).where(models.Client.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


def _add_client(
    db: Session,
    *,
    org_id: uuid.UUID,
    name: str,
    kind: str,
    parent_id: int | None = None,
    chat_mode: str = "company",
    zone_token: str | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> models.Client:
    existing = db.scalar(
        select(models.Client).where(
            models.Client.organization_id == org_id,
            models.Client.name == name,
            models.Client.parent_id == parent_id,
        )
    )
    if existing:
        if extra_payload:
            payload = dict(existing.payload or {})
            payload.update(extra_payload)
            existing.payload = payload
            flag_modified(existing, "payload")
        return existing
    row = models.Client(
        id=_next_client_id(db),
        organization_id=org_id,
        name=name,
        slug=_unique_client_slug(db, name),
        payload=dict(extra_payload or {}),
        parent_id=parent_id,
        chat_mode=chat_mode,
        kind=kind,
        client_zone_token=zone_token,
    )
    db.add(row)
    db.flush()
    return row


def _add_vacancy(
    db: Session,
    *,
    client_id: int,
    title: str,
    summary: str,
    active: bool = True,
    closed_days_ago: int | None = None,
    close_reason: str | None = None,
    created_days_ago: int = 40,
    documents: dict[str, Any] | None = None,
) -> models.Vacancy:
    existing = db.scalar(
        select(models.Vacancy).where(
            models.Vacancy.client_id == client_id,
            models.Vacancy.title == title,
        )
    )
    if existing:
        return existing
    created = _days_ago(created_days_ago)
    payload: dict[str, Any] = {
        "close_reason": close_reason,
        "is_test": False,
        "vacancy_summary": summary,
        "show_portfolio_field": False,
    }
    docs = dict(documents or empty_vacancy_documents())
    if not str(docs.get("profile") or "").strip():
        docs["profile"] = summary
    if not str(docs.get("vacancy_text") or "").strip():
        docs["vacancy_text"] = summary
    vac = models.Vacancy(
        id=next_vacancy_id(db),
        title=title,
        client_id=client_id,
        chat_id=None,
        active=active,
        created_at=_iso(created),
        closed_at=_iso(_days_ago(closed_days_ago)) if closed_days_ago is not None else None,
        documents=docs,
        version=1,
        payload=payload,
    )
    db.add(vac)
    db.flush()
    return vac


def _add_candidate(
    db: Session,
    *,
    vacancy: models.Vacancy,
    name: str,
    stage: str,
    client_status: str,
    created_days_ago: int,
    gender: str,
    city: str,
    phone: str,
    extra: dict[str, Any],
) -> models.Candidate:
    existing = db.scalar(
        select(models.Candidate).where(
            models.Candidate.vacancy_id == vacancy.id,
            models.Candidate.name == name,
        )
    )
    if existing:
        return existing
    created = _days_ago(created_days_ago)
    payload: dict[str, Any] = {
        "phone": phone,
        "email": "",
        "age": extra.pop("age", "29"),
        "city": city,
        "metro": "",
        "salary_expected": extra.pop("salary", "180 000 ₽"),
        "resume_link": extra.pop("resume_link", "https://example.com/demo-resume"),
        "hh_resume_link": "",
        "portfolio_link": extra.pop("portfolio_link", ""),
        "video_link": extra.pop("video_link", ""),
        "task_link": extra.pop("task_link", ""),
        "hr_comment": extra.pop("hr_comment", ""),
        "transcript": extra.pop("transcript", ""),
        "client_comment": extra.pop("client_comment", ""),
        "photo_url": "",
        "gender": gender,
        "source": "demo",
        "viewed": True,
        "office_interview_date": extra.pop("office_interview_date", ""),
        "office_interview_time": extra.pop("office_interview_time", ""),
        "remote_interview": extra.pop("remote_interview", False),
        "office_interview": extra.pop("office_interview", False),
        "meeting_hr_confirmed": extra.pop("meeting_hr_confirmed", False),
        "hr_stage_history": [],
        "interview_questionnaire": extra.pop("interview_questionnaire", []),
        "interview_digest": extra.pop("interview_digest", None),
    }
    payload.update(extra)
    cand = models.Candidate(
        id=uuid.uuid4(),
        vacancy_id=vacancy.id,
        name=name,
        hr_stage="resume_screening",
        client_status="wait",
        created_at=_iso(created),
        status_updated_at=_iso(created),
        payload=payload,
    )
    db.add(cand)
    db.flush()
    apply_hr_stage(cand, stage, note="демо-посев")
    cand.client_status = client_status
    cand.status_updated_at = _iso(_days_ago(max(0, created_days_ago // 3)))
    flag_modified(cand, "payload")
    db.flush()
    return cand


def _seed_content(db: Session, org_id: uuid.UUID) -> None:
    today = _now().date().isoformat()
    company = _add_client(
        db,
        org_id=org_id,
        name="Аврора Ритейл",
        kind=KIND_COMPANY,
        chat_mode=CHAT_MODE_DEPARTMENTS,
        extra_payload={
            "demo_content_version": DEMO_CONTENT_VERSION,
            "office_address": "Москва, ул. Лесная, д. 5",
            "offer_manager_name": "Иванова Марина Сергеевна",
            "default_work_schedule": (
                "Пятидневка, 10:00–19:00, офис у метро Белорусская. "
                "Раз в неделю — инвентаризация кабинетов маркетплейсов совместно с закупкой."
            ),
            "offer_logo_data_url": _aurora_logo_data_url(),
        },
    )
    mp = _add_client(db, org_id=org_id, name="Маркетплейсы", kind=KIND_DEPARTMENT, parent_id=company.id)
    mk = _add_client(db, org_id=org_id, name="Маркетинг", kind=KIND_DEPARTMENT, parent_id=company.id)
    fn = _add_client(db, org_id=org_id, name="Финансы", kind=KIND_DEPARTMENT, parent_id=company.id)
    if (company.client_zone_token or "") == _ZONE_TOKEN:
        company.client_zone_token = None
    if not mp.client_zone_token:
        mp.client_zone_token = _ZONE_TOKEN

    docs_mp = _demo_docs(
        profile=(
            "Ведение кабинета маркетплейса: карточки, акции, аналитика оборачиваемости, "
            "работа с контентом и возвратами. Два бренда одежды, отчёт собственнику раз в неделю."
        ),
        vacancy_text=(
            "Аврора Ритейл ищет менеджера маркетплейсов в команду закупки. "
            "Кабинет WB + второй канал, календарь акций, Excel, общение с контентом и складом. "
            "Офис у Белорусской, гибрид 4/1."
        ),
        questions=(
            "Опыт самостоятельного кабинета WB или Ozon?\n"
            "Как считаете оборачиваемость и неликвиды?\n"
            "Готовность вести два бренда сразу?"
        ),
    )
    docs_ds = _demo_docs(
        profile=(
            "Карточки товаров, баннеры акций, гайдлайн бренда. Figma, фото, базовая ретушь. "
            "Стиль спокойный, ритейл, не агентский арт."
        ),
        vacancy_text=(
            "Графический дизайнер в маркетинг Авроры: инфографика карточек, баннеры выходного дня, "
            "поддержка гайдлайна. Figma обязательна, Photoshop плюс."
        ),
        questions=(
            "Как собираете карточку товара под продажи?\n"
            "Срок баннера, если бриф утром?\n"
            "Есть серия «до/после» в портфолио?"
        ),
    )
    docs_an = _demo_docs(
        profile=(
            "План-факт, юнит-экономика SKU, еженедельный отчёт собственнику. "
            "Excel уверенно, Power BI плюс, 1С не обязательна."
        ),
        vacancy_text=(
            "Финансовый аналитик: связка SKU — закупка — маржа. "
            "Раз в неделю короткий отчёт для собственника, без воды."
        ),
        questions=(
            "Как собираете юнит-экономику SKU?\n"
            "Какой формат отчёта собственнику используете?\n"
            "Опыт Power BI или аналога?"
        ),
    )
    q_mp = [
        _q(
            "Опыт с кабинетом маркетплейса",
            "3 года Wildberries, год кабинет как совместительство.",
            "Самостоятельно вела 2 бренда на WB, второй кабинет — карточки и акции по ТЗ агентства.",
            "good",
            "Есть живой опыт кабинета, второй канал слабее WB — уточнить глубину аналитики.",
        ),
        _q(
            "Как считает оборачиваемость",
            "В резюме «работа с отчётами», без методики.",
            "Смотрит остатки vs продажи за 14 дней, режет неликвиды вручную в Excel.",
            "satisfactory",
            "Логика понятная, автоматизации нет — для пилота достаточно.",
        ),
        _q(
            "Конфликт с контент-командой",
            "Нет данных в резюме.",
            "Был спор из-за сроков инфографики: настояла на дедлайне акции, договорились на шаблон.",
            "good",
            "Умеет держать срок, не эскалирует в конфликт.",
        ),
    ]
    q_ds = [
        _q(
            "Как собираете карточку товара",
            "В портфолио серии «до/после».",
            "Сначала оффер и 3 выгоды, потом фото, потом доверие (состав, размерная сетка).",
            "good",
            "Мыслит оффером, не только картинкой.",
        )
    ]
    q_an = [
        _q(
            "Юнит-экономика SKU",
            "В резюме Power BI и план-факт, без методики.",
            "Считает маржу после логистики и возвратов, режет SKU с оборачиваемостью ниже 14 дней.",
            "good",
            "Формат отчёта понятный собственнику, 1С не использует — для пилота достаточно Excel.",
        ),
        _q(
            "Отчёт собственнику",
            "«Еженедельная сводка» в резюме.",
            "Одна страница: план-факт, топ-10 SKU, красные остатки. Без презентации на 20 слайдов.",
            "good",
            "Стиль сухой — совпадает с ожиданиями Авроры.",
        ),
    ]

    vac_mp = _add_vacancy(
        db,
        client_id=mp.id,
        title="Менеджер маркетплейсов",
        summary="Ведение кабинета маркетплейса: карточки, акции, аналитика оборачиваемости, работа с контентом и возвратами.",
        created_days_ago=28,
        documents=docs_mp,
    )
    vac_ds = _add_vacancy(
        db,
        client_id=mk.id,
        title="Графический дизайнер",
        summary="Карточки товаров, баннеры акций, гайдлайн бренда. Figma, фото, базовая ретушь.",
        created_days_ago=21,
        documents=docs_ds,
    )
    vac_an = _add_vacancy(
        db,
        client_id=fn.id,
        title="Финансовый аналитик",
        summary="План-факт, юнит-экономика SKU, отчёт для собственника раз в неделю.",
        created_days_ago=18,
        documents=docs_an,
    )
    vac_wh = _add_vacancy(
        db,
        client_id=mp.id,
        title="Кладовщик",
        summary="Приёмка, сборка, инвентаризация. Смена 2/2.",
        active=False,
        closed_days_ago=5,
        close_reason="success",
        created_days_ago=55,
        documents={
            "profile": "Склад готовой продукции: приёмка, сборка заказов, инвентаризация, работа с ТСД. График 2/2.",
            "vacancy_text": "Ищем кладовщика на склад у МКАД. Опыт ТСД приветствуется, обучение на месте.",
            "questions": "Опыт ТСД?\nГотовность к графику 2/2?\nТяжёлые короба до 15 кг?",
            "keywords": "",
            "notes": "",
        },
    )

    digest_mp = _digest(
        "Говорили про кабинет маркетплейса, акции и работу с контентом. Кандидат уверенно ведёт WB, второй кабинет знает на уровне карточек и календаря акций.",
        [
            ("Почему уходите с текущего места?", "Команда выросла, кабинет отдали агентству — хочет снова вести сама."),
            ("Как запускаете акцию?", "Сначала остатки и маржа, потом баннер, потом цена. Без этого не включает скидку."),
            ("Что было самым сложным?", "Возвраты и претензии по размерам — завёла таблицу причин."),
        ],
        "Говорит коротко, без воды, иногда уточняет вопрос. С заказчиком общаться будет легко.",
    )

    _add_candidate(
        db,
        vacancy=vac_mp,
        name="Соколова Анна Игоревна",
        stage="client_review",
        client_status="wait",
        created_days_ago=12,
        gender="f",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "age": "31",
            "salary": "170 000 ₽",
            **_ai(
                3,
                "Сильный операционный менеджер WB, второй кабинет — смежный опыт. Рекомендую заказчику.",
                "Закрывает 80% профиля: кабинет, акции, Excel. Слабее глубокая аналитика второго канала.",
                ["3 года WB", "запуск акций", "работа с возвратами"],
                ["второй кабинет не основной", "нет SQL"],
                ["Спросить про отчёт для собственника", "Готовность к 2 брендам сразу"],
            ),
            "hr_comment": "Живая, структурная. Заказчику отправлена 4 дня назад.",
            "interview_questionnaire": q_mp,
            "interview_digest": digest_mp,
            "video_link": "https://example.com/demo-video",
        },
    )
    _add_candidate(
        db,
        vacancy=vac_mp,
        name="Орлов Дмитрий Сергеевич",
        stage="client_pause",
        client_status="think",
        created_days_ago=16,
        gender="m",
        city="Санкт-Петербург",
        phone=DEMO_PHONE,
        extra={
            "age": "34",
            "salary": "200 000 ₽",
            **_ai(
                2,
                "Сильный по Ozon, мало ecom-ритейла одежды. Заказчик думает.",
                "Кабинет есть, категория не одежда.",
                ["Ozon 4 года", "реклама в кабинете"],
                ["Нет опыта одежды", "ожидания по деньгам выше вилки"],
                ["Готовность к вилке 160–180", "опыт с возвратами одежды"],
            ),
            "hr_comment": "Сильный, но дорогой. Заказчик взял паузу.",
            "client_comment": "[12.08.2026, Директор] к статусу «Подумать»: хотим сравнить с Соколовой по кабинету.",
            "interview_questionnaire": q_mp,
            "interview_digest": _digest(
                "Опыт глубокий, но в электронике. Одежду не вёл.",
                [("Категория?", "Электроника и DIY на Ozon."), ("Второй кабинет?", "Смотрел интерфейс, не вёл.")],
                "Говорит уверенно, чуть продаёт себя. Нужно держать рамку вопросов.",
            ),
        },
    )
    _add_candidate(
        db,
        vacancy=vac_mp,
        name="Лебедева Мария Павловна",
        stage="client_meeting",
        client_status="ready",
        created_days_ago=9,
        gender="f",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "age": "27",
            "salary": "160 000 ₽",
            "office_interview_date": today,
            "office_interview_time": "14:00",
            "office_interview": True,
            "meeting_hr_confirmed": True,
            **_ai(
                3,
                "Моложе, быстро учится, уже вела кабинет маркетплейса 8 месяцев в агентстве.",
                "Прямой опыт кабинета, меньше самостоятельности в закупке.",
                ["кабинет 8 мес.", "инфографика", "календарь акций"],
                ["Мало опыта как in-house"],
                ["Как ведёт спор с закупкой"],
            ),
            "hr_comment": "Встреча с заказчиком сегодня в 14:00, офис.",
            "interview_questionnaire": q_mp,
            "interview_digest": digest_mp,
            "video_link": "https://example.com/demo-video-2",
        },
    )
    _add_candidate(
        db,
        vacancy=vac_mp,
        name="Козлов Илья Андреевич",
        stage="rejected_client",
        client_status="reject",
        created_days_ago=20,
        gender="m",
        city="Казань",
        phone=DEMO_PHONE,
        extra={
            **_ai(
                1,
                "Мало опыта кабинета, больше контент. Заказчик отказал.",
                "Не закрывает операционку кабинета.",
                ["инфографика", "Wildberries как контентщик"],
                ["Нет самостоятельной аналитики"],
                [],
            ),
            "hr_comment": "Отказ заказчика: мало операционки.",
            "client_comment": "[05.08.2026, Руководитель подразделения] к статусу «Отказ»: нужен человек, который сам включает акции, а не только картинки.",
        },
    )

    _add_candidate(
        db,
        vacancy=vac_ds,
        name="Морозова Елена Викторовна",
        stage="interview_done",
        client_status="wait",
        created_days_ago=8,
        gender="f",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "age": "26",
            "salary": "140 000 ₽",
            "portfolio_link": "https://example.com/demo-portfolio",
            **_ai(
                3,
                "Сильное портфолио карточек WB, вкус спокойный. Можно к заказчику после правки тестового.",
                "Стиль совпадает с гайдлайном Авроры.",
                ["Figma", "инфографика WB", "баннеры"],
                ["Мало motion"],
                ["Срок баннера к акции"],
            ),
            "hr_comment": "Портфолио сильное. Тестовое — баннер выходного дня.",
            "interview_questionnaire": q_ds,
            "interview_digest": _digest(
                "Разбирали карточки и баннеры. Кандидат объясняет решения через продажи, не через «красоту».",
                [("Почему уходите?", "Агентство, мало влияния на метрики."), ("Срок баннера?", "Вечер, если бриф утром.")],
                "Спокойная речь, показывает работы с экрана, не перебивает.",
            ),
        },
    )
    _add_candidate(
        db,
        vacancy=vac_ds,
        name="Новиков Артём Олегович",
        stage="test_task",
        client_status="wait",
        created_days_ago=6,
        gender="m",
        city="Екатеринбург",
        phone=DEMO_PHONE,
        extra={
            "portfolio_link": "https://example.com/demo-portfolio-2",
            **_ai(
                2,
                "Яркий стиль, ритейлу может быть шумно. Тестовое покажет, слушает ли бриф.",
                "Навык есть, попадание в бренд под вопросом.",
                ["Photoshop", "нейросети для фото"],
                ["Мало ecom-карточек"],
                ["Готовность к шаблону, не арт-дирекшен"],
            ),
            "hr_comment": "Ждём тестовое до пятницы.",
            "task_link": "https://example.com/demo-task",
        },
    )
    _add_candidate(
        db,
        vacancy=vac_ds,
        name="Васильева Ирина Николаевна",
        stage="primary_contact",
        client_status="wait",
        created_days_ago=2,
        gender="f",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            **_ai(
                2,
                "Резюме ок, портфолио ссылка битая — запросила файл.",
                "Опыт агентства 2 года.",
                ["баннеры", "соцсети"],
                ["Нет файла портфолио"],
                ["Прислать 5 карточек"],
            ),
            "hr_comment": "Написала в Telegram, ждём портфолио файлом.",
            "ai_score": 2,
        },
    )

    _add_candidate(
        db,
        vacancy=vac_an,
        name="Громов Павел Алексеевич",
        stage="interview_scheduled",
        client_status="wait",
        created_days_ago=5,
        gender="m",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "age": "33",
            "salary": "220 000 ₽",
            "office_interview_date": (_now() + timedelta(days=1)).date().isoformat(),
            "office_interview_time": "11:30",
            "remote_interview": True,
            "meeting_hr_confirmed": False,
            **_ai(
                3,
                "Excel + Power BI, юнит-экономика SKU. Собеседование завтра, HR ещё не подтвердил слот.",
                "Профиль почти совпадает.",
                ["Power BI", "план-факт", "SKU"],
                ["Мало 1С"],
                ["Как собирает отчёт собственнику"],
            ),
            "hr_comment": "Слот завтра 11:30 удалённо — подтвердить в календаре.",
        },
    )
    _add_candidate(
        db,
        vacancy=vac_an,
        name="Белова Светлана Юрьевна",
        stage="resume_screening",
        client_status="wait",
        created_days_ago=1,
        gender="f",
        city="Новосибирск",
        phone="",
        extra={
            "age": "29",
            **_ai(
                2,
                "Бухгалтерский бэкграунд, аналитика слабее. Можно на скрининг, телефона нет.",
                "Частичное совпадение.",
                ["1С", "зарплата", "акт сверки"],
                ["Нет BI", "нет телефона в резюме"],
                ["Запросить телефон"],
            ),
            "hr_comment": "Резюме без телефона — не звонить, пока не ответит на HH.",
        },
    )
    _add_candidate(
        db,
        vacancy=vac_an,
        name="Кузнецов Олег Витальевич",
        stage="offer",
        client_status="offer",
        created_days_ago=25,
        gender="m",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "age": "36",
            "salary": "210 000 ₽",
            **_ai(
                4,
                "Лучший из воронки. Оффер на согласовании у собственника.",
                "Полное совпадение по отчётам и SKU.",
                ["юнит-экономика", "Python базово", "еженедельный отчёт"],
                ["Долго думает над оффером"],
                [],
            ),
            "hr_comment": "Оффер отправлен, ждём ответ до среды.",
            "interview_questionnaire": q_an,
            "interview_digest": _digest(
                "Глубокий разбор юнит-экономики. Кандидат сам предложил формат отчёта для собственника.",
                [("Почему Аврора?", "Хочет видеть связь SKU и закупки, не только P&L холдинга.")],
                "Точный, сухой стиль — собственнику такой отчёт понравится.",
            ),
            "offer": {
                "greeting": "Уважаемый",
                "name_patronymic": "Олег Витальевич",
                "full_name": "Кузнецов Олег Витальевич",
                "company": "Аврора Ритейл",
                "position": "Финансовый аналитик",
                "office_address": "Москва, ул. Лесная, д. 5",
                "work_schedule": (
                    "Пятидневка, 10:00–19:00, офис у метро Белорусская. "
                    "В пятницу — сверка отчёта с закупкой и складом."
                ),
                "start_date": "01.09.2026",
                "probation_months": "3 месяца",
                "salary_probation_base": "190 000 ₽ на руки",
                "salary_probation_bonus": "квартальная премия до 15% при выполнении плана-факта",
                "salary_probation_line": "190 000 ₽ на руки + квартальная премия до 15% при выполнении плана-факта",
                "salary_after_base": "210 000 ₽ на руки",
                "salary_after_bonus": "квартальная премия до 20% + годовой бонус по EBITDA направления",
                "salary_after_line": "210 000 ₽ на руки + квартальная премия до 20% и годовой бонус",
                "duties": (
                    "• Сбор и сверка данных из 1С и кабинетов маркетплейсов\n"
                    "• Еженедельный отчёт план-факт для собственника\n"
                    "• Юнит-экономика SKU: маржа, оборачиваемость, неликвиды\n"
                    "• Прогноз закупки на 4–6 недель\n"
                    "• Разбор отклонений вместе с руководителем продаж\n"
                    "• Подготовка цифр к планёрке по акциям"
                ),
                "manager_name": "Иванова Марина Сергеевна",
            },
        },
    )

    smirnov = _add_candidate(
        db,
        vacancy=vac_wh,
        name="Смирнов Алексей Петрович",
        stage="started_work",
        client_status="started",
        created_days_ago=40,
        gender="m",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "age": "24",
            "salary": "95 000 ₽",
            **_ai(3, "Вышел на смену 2/2. Вакансия закрыта успешно.", "Совпал по графику и опыту склада.", ["приёмка", "ТСД"], [], []),
            "hr_comment": "Вышел, гарантия 3 месяца.",
        },
    )
    from app.services.warranty import apply_warranty_to_vacancy

    apply_warranty_to_vacancy(
        vac_wh,
        smirnov,
        start_date=_days_ago(14).date(),
        months=3,
        start_kind="started_work",
    )
    db.flush()
    _add_candidate(
        db,
        vacancy=vac_wh,
        name="Фёдоров Никита Ильич",
        stage="rejected_hr",
        client_status="wait",
        created_days_ago=38,
        gender="m",
        city="Москва",
        phone=DEMO_PHONE,
        extra={
            "hr_comment": "Отказ в связи с закрытием вакансии",
            "ai_score": 2,
            "ai_comment": "Резерв. Вакансия закрыта наймом Смирнова.",
        },
    )


def ensure_demo_showcase(db: Session) -> tuple[models.Organization, models.User, bool]:
    """Create demo org + recruiter + fictional funnel if missing."""
    org = create_organization(db, name=DEMO_ORG_NAME, slug=DEMO_ORG_SLUG)
    db.flush()

    user = db.scalar(select(models.User).where(models.User.email == DEMO_USER_EMAIL))
    created_user = False
    if user is None:
        user = models.User(
            email=DEMO_USER_EMAIL,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=DEMO_USER_NAME,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(
            models.OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=ROLE_HR_RECRUITER,
            )
        )
        created_user = True
    else:
        mem = db.scalar(
            select(models.OrganizationMember).where(models.OrganizationMember.user_id == user.id)
        )
        if mem is None:
            db.add(
                models.OrganizationMember(
                    organization_id=org.id,
                    user_id=user.id,
                    role=ROLE_HR_RECRUITER,
                )
            )

    version = None
    company = db.scalar(
        select(models.Client).where(
            models.Client.organization_id == org.id,
            models.Client.parent_id.is_(None),
            models.Client.name == "Аврора Ритейл",
        )
    )
    if company is not None:
        version = (company.payload or {}).get("demo_content_version")
    if version != DEMO_CONTENT_VERSION:
        _reset_demo_funnel(db, org.id)
        _seed_content(db, org.id)
        created_user = True

    integrations = dict(org.integrations or {})
    features = dict(integrations.get("features") or {})
    if not features.get("management_system"):
        features["management_system"] = True
        integrations["features"] = features
        org.integrations = integrations
        flag_modified(org, "integrations")

    db.commit()
    db.refresh(org)
    db.refresh(user)
    logger.info("demo showcase ready org=%s user=%s", org.slug, user.email)
    return org, user, created_user
