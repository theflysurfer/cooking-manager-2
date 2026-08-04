// Gate de compatibilité iOS 12.5.8 (iPad mini 2) pour le front statique.
//
// Deux garde-fous complémentaires — aucun ne couvre l'autre :
//
//   1. ecmaVersion: 2019 → le gate SYNTAXE, gratuit et sans plugin. C'est
//      exactement ce que le moteur d'iOS 12.5 sait parser. Fait échouer sur
//      `?.` et `??` (13.4), `||=` (14), les séparateurs numériques (13) et
//      surtout les CHAMPS DE CLASSE PUBLICS — iOS 16, le piège le plus vicieux
//      parce qu'il ressemble à du JS parfaitement banal.
//
//   2. eslint-plugin-compat → le gate API (ResizeObserver, structuredClone…).
//      Il ne voit QUE les API, jamais la syntaxe : sans le point 1, un `?.`
//      passerait sans un mot.
//
// ⚠️ devDependency uniquement. Le front déployé reste des fichiers statiques
//    servis par FastAPI — il n'y a pas de build, et il ne faut pas en ajouter.

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
      // Couvre aussi les built-ins ES (replaceAll, allSettled, BigInt…),
      // pas seulement les API navigateur.
      lintAllEsApis: true,
      browsers: ["ios_saf 12.2-12.5"],
    },
    rules: {
      "compat/compat": "error",
    },
  },
];
