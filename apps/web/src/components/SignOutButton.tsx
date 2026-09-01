"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { clearPipelineContext } from "@/lib/pipelineContext";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export function SignOutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleSignOut() {
    const client = getSupabaseBrowserClient();
    if (!client) {
      clearPipelineContext();
      router.replace("/login");
      return;
    }

    setBusy(true);
    await client.auth.signOut();
    clearPipelineContext();
    router.replace("/login");
  }

  return (
    <button
      type="button"
      className="site-nav-signout"
      disabled={busy}
      onClick={() => void handleSignOut()}
    >
      {busy ? "Signing out…" : "Sign out"}
    </button>
  );
}
