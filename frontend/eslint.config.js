const path = require("path");
const { FlatCompat } = require("@eslint/eslintrc");

const compat = new FlatCompat({ baseDirectory: path.resolve() });

module.exports = [
  { ignores: ["node_modules/**", "dist/**", ".expo/**"] },
  ...compat.extends("expo"),
];
