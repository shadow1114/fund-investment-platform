import { defineConfig } from "orval";

export default defineConfig({
  m17: {
    input: "./openapi/m17.yaml",
    output: {
      target: "./src/api/generated/m17.ts",
      mode: "split",
      client: "fetch",
      clean: true,
      prettier: true,
      override: {
        fetch: {
          explode: false,
        },
        mutator: {
          path: "./src/api/client.ts",
          name: "apiFetch",
        },
      },
    },
  },
});
