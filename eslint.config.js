import compat from "eslint-plugin-compat";

export default [
  {
    files: ["web/**/*.js"],
    plugins: { compat },
    languageOptions: {
      ecmaVersion: 2019,
      sourceType: "script",
      globals: {
        window: "readonly",
        document: "readonly",
        fetch: "readonly",
        console: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        FormData: "readonly",
        URLSearchParams: "readonly",
        EventSource: "readonly",
        localStorage: "readonly",
        location: "readonly",
        history: "readonly",
      },
    },
    settings: {
      lintAllEsApis: true,
      browsers: ["ios_saf 12.2-12.5"],
    },
    rules: {
      "compat/compat": "error",
    },
  },
];
