"use client";

import { useEffect, useState } from "react";
import { InfoTip } from "@/components/InfoTip";
import { apiFetch } from "@/lib/api";

export type DiskStatus = {
  connected: boolean;
  message: string;
  login?: string | null;
  root?: string;
  inbox_path?: string;
  authorize_url?: string | null;
  create_app_url?: string;
  client_id?: string;
  token_path?: string;
};

const YANDEX_CREATE_APP_URL = "https://oauth.yandex.ru/client/new";
/** Official Yandex page that shows the token after authorize (implicit flow). */
export const YANDEX_REDIRECT_URI = "https://oauth.yandex.ru/verification_code";

export function buildAuthorizeUrl(clientId: string): string {
  const id = clientId.trim();
  const params = new URLSearchParams({
    response_type: "token",
    client_id: id,
    redirect_uri: YANDEX_REDIRECT_URI,
    scope: "cloud_api:disk.app_folder cloud_api:disk.read cloud_api:disk.write",
  });
  return `https://oauth.yandex.ru/authorize?${params.toString()}`;
}

type Props = {
  /** When false, panel is not rendered (caller gates by intake flags). */
  active?: boolean;
  onConnectedChange?: (connected: boolean) => void;
};

/** OAuth + root/inbox folder paths — shared by disk sync and inbox channels. */
export function YandexDiskConnectPanel({ active = true, onConnectedChange }: Props) {
  const [status, setStatus] = useState<DiskStatus | null>(null);
  const [clientId, setClientId] = useState("");
  const [token, setToken] = useState("");
  const [root, setRoot] = useState("/HR_AI_Agent");
  const [inbox, setInbox] = useState("_inbox");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadStatus = async () => {
    const res = await apiFetch(`/api/v1/integrations/yandex-disk/status`, {
      cache: "no-store",
    });
    const data = await res.json();
    setStatus(data);
    onConnectedChange?.(Boolean(data.connected));
    if (data.root) setRoot(data.root);
    if (typeof data.client_id === "string" && data.client_id.trim()) {
      setClientId(data.client_id.trim());
    }
  };

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    (async () => {
      try {
        await loadStatus();
        const res = await apiFetch(`/api/v1/settings/app`, { cache: "no-store" });
        const d = await res.json();
        if (cancelled) return;
        if (d.yandex_disk_root) setRoot(d.yandex_disk_root);
        if (d.yandex_disk_inbox) setInbox(d.yandex_disk_inbox);
        if (typeof d.yandex_disk_client_id === "string" && d.yandex_disk_client_id.trim()) {
          setClientId(d.yandex_disk_client_id.trim());
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка загрузки Диска");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active]);

  if (!active) return null;

  const saveClientId = async (value: string) => {
    const res = await apiFetch(`/api/v1/settings/app`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yandex_disk_client_id: value.trim() }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    }
  };

  const onGetAccessKeyClick = () => {
    const id = clientId.trim();
    if (!id) {
      setErr("Сначала вставьте Client ID");
      return;
    }
    setErr(null);
    setMsg(null);
    const url = buildAuthorizeUrl(id);
    const win = window.open(url, "_blank", "noopener,noreferrer");
    void (async () => {
      setBusy(true);
      try {
        await saveClientId(id);
        if (!win) {
          setMsg(null);
          setErr(
            "Браузер заблокировал новое окно. Разрешите всплывающие окна для этого сайта или откройте ссылку вручную (она под кнопкой).",
          );
        } else {
          setMsg(
            "Открылась страница Яндекса. Разрешите доступ — откроется страница с кодом/токеном. Скопируйте токен (y0_…) и вставьте ниже.",
          );
        }
        await loadStatus();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Ошибка сохранения Client ID");
      } finally {
        setBusy(false);
      }
    })();
  };

  const saveToken = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      if (clientId.trim()) {
        await saveClientId(clientId.trim());
      }
      const res = await apiFetch(`/api/v1/integrations/yandex-disk/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setStatus(data);
      setToken("");
      onConnectedChange?.(Boolean(data.connected));
      setMsg(data.warning ? `Токен сохранён, но: ${data.warning}` : "Токен сохранён");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const savePaths = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const rootNorm = root.trim().startsWith("/") ? root.trim() : `/${root.trim()}`;
      const inboxNorm = inbox.trim().replace(/^\/+|\/+$/g, "") || "_inbox";
      if (!rootNorm || rootNorm === "/") {
        throw new Error("Укажите корневую папку вида /HR_AI_Agent (не корень всего Диска)");
      }
      if (inboxNorm.includes("/")) {
        throw new Error("Имя inbox — только имя папки внутри корня, без слэшей (например _inbox)");
      }
      const res = await apiFetch(`/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yandex_disk_root: rootNorm, yandex_disk_inbox: inboxNorm }),
      });
      if (!res.ok) throw new Error("Не удалось сохранить пути");
      setRoot(rootNorm);
      setInbox(inboxNorm);
      const ensure = await apiFetch(`/api/v1/integrations/yandex-disk/ensure-root`, {
        method: "POST",
      });
      const ensureData = await ensure.json().catch(() => ({}));
      if (!ensure.ok) {
        throw new Error(
          typeof ensureData.detail === "string" ? ensureData.detail : "Не удалось создать папки на Диске",
        );
      }
      await loadStatus();
      setMsg("Пути сохранены, папки на Диске проверены/созданы");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const disconnectDisk = async () => {
    const ok = window.confirm(
      "Отвязать Яндекс Диск?\n\nБудут сброшены локально: токен, Client ID и пути папок (на значения по умолчанию).\nПапки и файлы на самом Яндекс Диске не удаляются.",
    );
    if (!ok) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/integrations/yandex-disk/disconnect`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setStatus(data);
      setClientId("");
      setToken("");
      setRoot(data.root || "/HR_AI_Agent");
      setInbox("_inbox");
      onConnectedChange?.(Boolean(data.connected));
      setMsg(data.message || "Диск отвязан. Можно настроить заново.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="card-edit" id="yandex-disk-connect">
        <h2>
          Подключение Яндекс Диска{" "}
          <InfoTip text="OAuth один раз; корневая папка — куда складываются папки вакансий и inbox." />
        </h2>
        {err ? <p className="warn">{err}</p> : null}
        {msg ? <p className="ok">{msg}</p> : null}
        {status ? (
          <p className={status.connected ? "ok" : "warn"}>
            {status.connected
              ? `Подключено${status.login ? `: ${status.login}` : ""}`
              : status.message}
          </p>
        ) : (
          <p className="muted">Загрузка…</p>
        )}

        <ol className="yd-steps muted">
          <li>
            Нажмите <strong>«Создать приложение на Яндексе»</strong>. На плашке «Какое
            приложение хотите создать?» выберите{" "}
            <strong>«Для авторизации пользователей»</strong> (не «Для доступа к API или
            отладки») → «Перейти к созданию».
          </li>
          <li>
            <strong>Шаг 1 из 4</strong> — название, иконка, почта. Блока доступов здесь нет.
            Укажите название (например HR-помогатор) и почту → <strong>«Продолжить»</strong>.
          </li>
          <li>
            <strong>Шаг 2 из 4 — платформы.</strong> Оставьте галочку{" "}
            <strong>«Веб-сервисы»</strong>. В поле <strong>Redirect URI</strong> вставьте ровно:
            <br />
            <code>{YANDEX_REDIRECT_URI}</code>
            <br />
            В «Подставить Hostname» можно указать <code>localhost</code> (для локальной работы)
            или хост вашего сайта. Не нажимайте «+» справа — это добавляет ещё одну пустую
            строку, она не нужна. Без заполненного Redirect URI «Продолжить» не сработает →{" "}
            <strong>«Продолжить»</strong>.
          </li>
          <li>
            <strong>Шаг 3 из 4 — права доступа.</strong> Блок «Основные» (дата рождения, почта,
            имя и т.п.) <strong>не отмечайте</strong> — для Диска это не нужно. В блоке{" "}
            <strong>«Дополнительные»</strong> в поле «Название доступа» по очереди введите и
            выберите из списка три пункта:
            <ul>
              <li>
                <strong>Доступ к папке приложения на Диске</strong>
              </li>
              <li>
                <strong>Чтение всего Диска</strong>
              </li>
              <li>
                <strong>Запись в любом месте на Диске</strong>
              </li>
            </ul>
            Можно начать печатать «Диск» или «Чтение» / «Запись» — нужные строки появятся в
            подсказках. Остальное (Директ и т.п.) не добавляйте → <strong>«Продолжить»</strong>.
          </li>
          <li>
            <strong>Шаг 4</strong> — проверьте данные и сохраните приложение. Скопируйте{" "}
            <strong>Client ID</strong> (идентификатор) в поле ниже.
          </li>
          <li>
            Нажмите <strong>«Получить ключ доступа»</strong>, разрешите доступ в Яндексе. На
            странице проверки кода / в адресной строке будет токен{" "}
            <code>access_token=y0_…</code> (или поле с кодом). Скопируйте значение, начинающееся с{" "}
            <code>y0_</code>, вставьте в «OAuth access_token» и нажмите «Сохранить токен».
          </li>
        </ol>

        <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginBottom: "0.75rem" }}>
          <a
            className="chip chip-active"
            href={status?.create_app_url || YANDEX_CREATE_APP_URL}
            target="_blank"
            rel="noreferrer"
          >
            Создать приложение на Яндексе
          </a>
        </div>

        <label className="hh-field">
          <span className="hh-label">
            Client ID (Идентификатор приложения){" "}
            <InfoTip text="Скопируйте его из настроек вашего приложения на oauth.yandex.ru" />
          </span>
          <input
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            disabled={busy}
            placeholder="Например: c47d92863c954b…"
            autoComplete="off"
          />
        </label>

        <div
          className="hh-row-actions"
          style={{ justifyContent: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}
        >
          <button
            type="button"
            className="chip chip-active"
            disabled={busy || !clientId.trim()}
            onClick={onGetAccessKeyClick}
          >
            🔑 Получить ключ доступа
          </button>
          {clientId.trim() ? (
            <a
              className="chip"
              href={buildAuthorizeUrl(clientId)}
              target="_blank"
              rel="noreferrer"
              onClick={() => {
                void saveClientId(clientId.trim()).catch((e) =>
                  setErr(e instanceof Error ? e.message : "Ошибка сохранения Client ID"),
                );
              }}
            >
              Открыть ссылку авторизации вручную
            </a>
          ) : null}
        </div>
        {clientId.trim() ? (
          <p className="muted hh-micro" style={{ wordBreak: "break-all", marginTop: "0.35rem" }}>
            Если кнопка «ничего не делает» — скопируйте ссылку:{" "}
            <a href={buildAuthorizeUrl(clientId)} target="_blank" rel="noreferrer">
              {buildAuthorizeUrl(clientId)}
            </a>
          </p>
        ) : null}

        <label className="hh-field" style={{ marginTop: "0.85rem" }}>
          <span className="hh-label">OAuth access_token</span>
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            disabled={busy}
            placeholder="y0_…"
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !token.trim()}
          onClick={() => void saveToken()}
        >
          Сохранить токен
        </button>

        <div className="yd-disconnect">
          <p className="muted hh-micro" style={{ marginBottom: "0.45rem" }}>
            Чтобы начать настройку с нуля: сбросятся токен, Client ID и пути папок в программе.
            Файлы на Яндекс Диске останутся на месте.
          </p>
          <button
            type="button"
            className="chip chip-danger"
            disabled={busy}
            onClick={() => void disconnectDisk()}
          >
            Отвязать Диск
          </button>
        </div>
      </section>

      <section className="card-edit">
        <h2>Папки на Диске</h2>
        <p className="muted hh-micro">
          По умолчанию: корень <code>/HR_AI_Agent</code>, inbox <code>_inbox</code> (полный путь{" "}
          <code>/HR_AI_Agent/_inbox</code>).
        </p>
        <ol className="yd-steps muted">
          <li>
            <strong>Корневая папка</strong> — абсолютный путь на Диске, начинается с{" "}
            <code>/</code>. Пример: <code>/HR_AI_Agent</code>. Не указывайте просто{" "}
            <code>/</code>.
          </li>
          <li>
            <strong>Имя inbox</strong> — только имя одной папки <em>внутри</em> корня, без слэшей.
            Пример: <code>_inbox</code>.
          </li>
          <li>
            После смены путей нажмите <strong>«Сохранить и создать папки»</strong> — программа
            создаст корень, inbox и служебную <code>_unsorted</code>.
          </li>
        </ol>
        <label className="hh-field">
          <span className="hh-label">Корневая папка</span>
          <input
            value={root}
            disabled={busy}
            onChange={(e) => setRoot(e.target.value)}
            placeholder="/HR_AI_Agent"
          />
        </label>
        <label className="hh-field">
          <span className="hh-label">Имя inbox</span>
          <input
            value={inbox}
            disabled={busy}
            onChange={(e) => setInbox(e.target.value)}
            placeholder="_inbox"
          />
        </label>
        <p className="muted hh-micro">
          Сейчас inbox:{" "}
          <code>{`${root.replace(/\/$/, "")}/${inbox.replace(/^\/+|\/+$/g, "") || "_inbox"}`}</code>
        </p>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy}
          onClick={() => void savePaths()}
        >
          Сохранить и создать папки
        </button>
      </section>
    </>
  );
}
