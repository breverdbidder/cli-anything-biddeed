import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import agencyConfig from "./agency.config.json" with { type: "json" };

export default defineConfig({
  output: "static",
  site: `https://${agencyConfig.domain.default}`,
  vite: {
    plugins: [tailwindcss()],
  },
});
