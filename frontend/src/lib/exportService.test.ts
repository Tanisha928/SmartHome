import { describe, expect, it } from "vitest";
import { toCsv } from "./exportService";
describe("exportService", () => { it("escapes CSV cells and neutralizes formulas", () => { expect(toCsv([{ value: "=SUM(A1)", note: "hello, world" }], ["value", "note"])).toBe("value,note\r\n'=SUM(A1),\"hello, world\""); }); });
