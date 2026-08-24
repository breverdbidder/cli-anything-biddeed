import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  output: "static",
  site: "https://protectionpartners.pages.dev",
  vite: {
    plugins: [tailwindcss()],
  },
});
