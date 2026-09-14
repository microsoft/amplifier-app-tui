import { test, expect } from "bun:test";
import { safe, wrap, color, palette } from "./model";
test("Unicode wrapping retains source", () => {
  const s = "界e\u0301🦀abcdef";
  expect(wrap(s, 4).join("")).toBe(s);
});
test("untrusted content cannot issue terminal controls", () =>
  expect(safe("a\x1b[31m\x07b")).toBe("a[31mb"));
test("failure retains error role", () =>
  expect(color("failed")).toBe(palette.red));
