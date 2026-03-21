"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

const C = { bg: "#06060f", accent: "#2563ff", muted: "#64748b" };

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    const handleCallback = async () => {
      // PKCE flow: Supabase redirects with ?code= query param
      const code = new URLSearchParams(window.location.search).get("code");
      if (code) {
        const { data, error } = await supabase.auth.exchangeCodeForSession(code);
        if (data.session?.access_token) {
          localStorage.setItem("ieb_token", data.session.access_token);
          document.cookie = "ieb_auth=1; path=/; max-age=2592000; SameSite=Lax";
          router.replace("/dashboard");
          return;
        }
        if (error) console.error("PKCE exchange failed:", error.message);
      }

      // Fallback: implicit flow (hash fragment)
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        localStorage.setItem("ieb_token", session.access_token);
        document.cookie = "ieb_auth=1; path=/; max-age=2592000; SameSite=Lax";
        router.replace("/dashboard");
      } else {
        router.replace("/login");
      }
    };

    handleCallback();
  }, [router]);

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ color: C.muted, fontSize: 12, fontFamily: "monospace", letterSpacing: 1 }}>
        SIGNING IN...
      </div>
    </div>
  );
}
