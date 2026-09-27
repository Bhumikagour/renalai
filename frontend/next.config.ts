import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every route here is a client component, so Next emits plain static files
  // into ./out — deployed as a Render Static Site (free, no cold starts, CDN).
  //
  // Consequence: NEXT_PUBLIC_API_URL is baked into the bundle at BUILD time.
  // Pointing the app at a different backend requires a rebuild, not a restart.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
