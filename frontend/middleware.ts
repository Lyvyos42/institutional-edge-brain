import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * IEB app is currently paused.
 * All requests redirect to the product page on the marketing site.
 */
export function middleware(_request: NextRequest) {
  return NextResponse.redirect(
    "https://quantneuraledge.com/products/institutional-edge",
    { status: 302 }
  );
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public/).*)"],
};
