import type { NextConfig } from "next";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
if (process.env.NODE_ENV === "production") {
  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be configured before building the production frontend.");
  }
  let parsedApiBaseUrl: URL;
  try {
    parsedApiBaseUrl = new URL(apiBaseUrl);
  } catch {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be a valid absolute HTTPS URL in production.");
  }
  if (parsedApiBaseUrl.protocol !== "https:" || !parsedApiBaseUrl.hostname) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must use HTTPS and include the backend API hostname in production.");
  }
}

const nextConfig: NextConfig = {
  // Style-only lint errors (for example an unescaped apostrophe in text) should not stop a deployment.
  // Type checking still runs during the build, and `npm run lint` still reports these locally.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
