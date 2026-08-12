import { NextResponse, type NextRequest } from "next/server";

/** Страницы без входа: хаб модулей, вход, клиентские ссылки, превью дизайна. */
const PUBLIC_PATHS = new Set(["/", "/login"]);
const PUBLIC_PREFIXES = ["/login/", "/c/", "/i/", "/design-preview"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

/**
 * Без cookie сессии страница уходит на /login до серверного рендера.
 * Иначе server component получает 401 на каждый запрос к API и страница зависает.
 */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (isPublic(pathname)) return NextResponse.next();

  const hasSession = req.cookies.has("hr_access") || req.cookies.has("hr_refresh");
  if (hasSession) return NextResponse.next();

  const host = req.headers.get("host") || req.nextUrl.host;
  const proto = req.headers.get("x-forwarded-proto") || req.nextUrl.protocol.replace(":", "");
  return NextResponse.redirect(new URL(`${proto}://${host}/login`));
}

export const config = {
  matcher: ["/((?!api/|_next/|favicon|.*\\.png$|.*\\.svg$|.*\\.ico$).*)"],
};
