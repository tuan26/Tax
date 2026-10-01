import assert from "node:assert/strict";
import { test } from "node:test";
import { parseAmount } from "./amount.mjs";

test("số tiền gõ tắt", () => {
  const cases = { "2tr5": 2_500_000, "12tr5": 12_500_000, "1tr250": 1_250_000, "2,35tr": 2_350_000, "1t2": 1_200_000,
    "950k": 950_000, "1k5": 1_500, "2.350.000": 2_350_000, "2.350.000đ": 2_350_000, "2350000": 2_350_000,
    "2 tr 5": 2_500_000 };
  for (const [input, want] of Object.entries(cases)) assert.equal(parseAmount(input), want, input);
});

test("không đoán khi không chắc", () => {
  for (const input of ["", "abc", "2.35.0", "1.5tr2", "-5", "0"]) assert.equal(parseAmount(input), null, input);
});
