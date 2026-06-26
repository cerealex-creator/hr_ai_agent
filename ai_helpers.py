"""Общие хелперы для вызовов ИИ: лимиты токенов, обрезка промптов, тайминг."""

import json
import logging
import re
import time

logger = logging.getLogger(__name__)

NO_THINK_DIRECTIVE = (
    "\n\n/no_think\n"
    "Отвечай сразу валидным JSON без рассуждений, без markdown и без тегов thinking."
)

_PROFILE_SECTION_MARKERS = (
    "hard skills",
    "hard_skills",
    "soft skills",
    "стоп",
    "стоп-фактор",
    "обязательные",
    "желательные",
    "психологическ",
    "личные качества",
    "опыт",
    "образование",
    "цкп",
    "обязанност",
)

_DEFAULT_TASK_MAX_TOKENS = {
    "extract": 500,
    "resume_eval": 1500,
    "questionnaire": 2000,
    "interview_eval": 2000,
}

_DEFAULT_CHAR_LIMITS = {
    "profile": 5000,
    "resume": 8000,
    "transcript": 10000,
    "questionnaire": 4000,
    "hr_comment": 2000,
    "interview_eval_notes": 2000,
    "eval_comment": 1500,
}


def get_task_max_tokens(config, task, default=None):
    model_cfg = config.get("model", {})
    by_task = model_cfg.get("max_tokens_by_task") or {}
    if task in by_task:
        return int(by_task[task])
    if default is not None:
        return int(default)
    if task in _DEFAULT_TASK_MAX_TOKENS:
        return int(_DEFAULT_TASK_MAX_TOKENS[task])
    return int(model_cfg.get("max_tokens", 4000))


def get_char_limit(config, key, default=None):
    limits = (config.get("model") or {}).get("task_limits") or {}
    if key in limits:
        return int(limits[key])
    if default is not None:
        return int(default)
    return int(_DEFAULT_CHAR_LIMITS.get(key, 8000))


def trim_text(text, limit):
    text = (text or "").strip()
    if limit and len(text) > limit:
        return text[:limit]
    return text


def trim_profile_for_eval(profile_text, limit=5000):
    text = (profile_text or "").strip()
    if not text:
        return "Профиль не задан"
    if len(text) <= limit:
        return text

    priority = []
    other = []
    for line in text.splitlines():
        low = line.lower()
        if any(marker in low for marker in _PROFILE_SECTION_MARKERS):
            priority.append(line)
        else:
            other.append(line)

    compact = "\n".join(priority + other).strip() or text[:limit]
    return compact[:limit]


def with_no_think(system_content, config):
    if not (config.get("model") or {}).get("disable_thinking", True):
        return system_content
    if "/no_think" in system_content:
        return system_content
    return f"{system_content}{NO_THINK_DIRECTIVE}"


def parse_ai_json_response(content):
    content = str(content or "").strip()
    content = re.sub(
        r"<(?:think|thinking|redacted_thinking)>.*?</(?:think|thinking|redacted_thinking)>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    content = content.strip()
    if not content.startswith("{") and not content.startswith("["):
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)
    return json.loads(content.strip())


def create_chat_completion(client, config, task, messages, *, temperature=None, max_tokens=None, **kwargs):
    """Единая точка вызова chat.completions с лимитами, no_think и логом времени."""
    model_cfg = config.get("model", {})
    resolved_max_tokens = max_tokens if max_tokens is not None else get_task_max_tokens(config, task)
    resolved_temperature = (
        model_cfg.get("temperature", 0.3) if temperature is None else temperature
    )

    prepared_messages = []
    for msg in messages:
        item = dict(msg)
        if item.get("role") == "system" and "content" in item:
            item["content"] = with_no_think(item["content"], config)
        prepared_messages.append(item)

    create_kwargs = {
        "model": model_cfg["name"],
        "messages": prepared_messages,
        "max_tokens": resolved_max_tokens,
        "temperature": resolved_temperature,
    }
    create_kwargs.update(kwargs)

    disable_thinking = model_cfg.get("disable_thinking", True)
    if disable_thinking and "extra_body" not in create_kwargs:
        create_kwargs["extra_body"] = {"reasoning": {"enabled": False}}

    started = time.time()
    try:
        response = client.chat.completions.create(**create_kwargs)
    except Exception as exc:
        if disable_thinking and "extra_body" in create_kwargs:
            err = str(exc).lower()
            if "reasoning" in err or "extra" in err or "unknown" in err:
                create_kwargs.pop("extra_body", None)
                response = client.chat.completions.create(**create_kwargs)
            else:
                raise
        else:
            raise

    elapsed = time.time() - started
    usage = getattr(response, "usage", None)
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    logger.info(
        "AI %s: %.1fs prompt_tokens=%s completion_tokens=%s max_tokens=%s",
        task,
        elapsed,
        prompt_tokens,
        completion_tokens,
        resolved_max_tokens,
    )
    return response
