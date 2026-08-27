import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

const repoRoot = path.resolve(__dirname, "../..");
loadEnvConfig(repoRoot);

function mirrorEnv(source: string, target: string): void {
  if (!process.env[target]?.trim() && process.env[source]?.trim()) {
    process.env[target] = process.env[source];
  }
}

mirrorEnv("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL");
mirrorEnv("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_DEV_ACCESS_TOKEN: process.env.NEXT_PUBLIC_DEV_ACCESS_TOKEN,
  },
};

export default nextConfig;
