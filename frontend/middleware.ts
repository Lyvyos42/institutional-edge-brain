import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that require authentication
const PROTECTED = ["/dashboard", "/account", "/backtest", "/alerts"];
// Routes only for unauthenticated users (redirect to dashboard if logged in)
const AUTH_ONLY = ["/login", "/register", "/forgot-password"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isLoggedIn = request.cookies.has("ieb_auth");

  // Protect private routes
  if (PROTECTED.some((p) => pathname.startsWith(p))) {
    if (!isLoggedIn) {
      const url = request.nextUrl.clone();
      url.pathname = "/login";
      return NextResponse.redirect(url);
    }
  }

  // Redirect logged-in users away from auth pages
  if (AUTH_ONLY.some((p) => pathname.startsWith(p))) {
    if (isLoggedIn) {
      const url = request.nextUrl.clone();
      url.pathname = "/dashboard";
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public/).*)"],
};
