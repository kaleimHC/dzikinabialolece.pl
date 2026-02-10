module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  settings: { react: { version: "detect" } },
  extends: [
    "eslint:recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
  ],
  plugins: ["react", "react-hooks"],
  rules: {
    // Modern React (Vite JSX runtime) - no need to import React in scope.
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    // Style-level findings are warnings (do not fail CI); real bugs stay errors.
    "no-unused-vars": "warn",
    "react/no-unescaped-entities": "off",
  },
};
