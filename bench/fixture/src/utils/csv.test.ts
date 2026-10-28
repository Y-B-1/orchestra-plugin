import { describe, expect, it } from "vitest";
import { toCsv } from "./csv";

describe("toCsv", () => {
  const columns = [
    { header: "Name", value: (row: { name: string; qty: number }) => row.name },
    { header: "Qty", value: (row: { name: string; qty: number }) => row.qty },
  ];

  it("writes a header and quotes cells with commas or quotes", () => {
    expect(toCsv([{ name: "AAPL", qty: 100 }], columns)).toBe("Name,Qty\r\nAAPL,100");
    expect(toCsv([{ name: 'Apple, "Inc."', qty: 1 }], columns)).toBe('Name,Qty\r\n"Apple, ""Inc.""",1');
  });
});
