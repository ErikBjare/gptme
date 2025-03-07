/** @type {import("eslint").Linter.Config} */
const config = {
  env: {
    es2021: true,
  },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:import/typescript",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 12,
    project: true,
    sourceType: "module",
  },
  plugins: ["@typescript-eslint"],
  rules: {
    "@typescript-eslint/array-type": "off",
    "@typescript-eslint/consistent-type-definitions": "off",
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-misused-promises": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    curly: ["warn", "all"],
    // Temporarily disabling import rules to focus on 'any' type issues
    "import/no-cycle": "off",
    "import/no-default-export": "off",
    "import/no-unresolved": "off",
    "no-console": "error",
    "no-eval": "error",
    "no-implied-eval": "error",
    "no-param-reassign": "error",
    "no-unneeded-ternary": "error",
  },
};
module.exports = config;
