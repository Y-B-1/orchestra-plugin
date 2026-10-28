import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { emptyTradeFilters } from "../../api";
import { isFiltered, TradeFilters } from "./TradeFilters";

describe("TradeFilters", () => {
  it("reports a changed side and asset class", () => {
    const onChange = vi.fn();
    render(<TradeFilters value={emptyTradeFilters} onChange={onChange} onReset={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Sell" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...emptyTradeFilters, side: "sell" });
    fireEvent.change(screen.getByLabelText("Asset class"), { target: { value: "bond" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...emptyTradeFilters, assetClass: "bond" });
  });

  it("warns about an inverted date range and knows when it is filtered", () => {
    render(
      <TradeFilters
        value={{ ...emptyTradeFilters, from: "2026-10-20", to: "2026-10-10" }}
        onChange={() => undefined}
        onReset={() => undefined}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("The start date must be on or before the end date.");
    expect(screen.getByLabelText("To")).toHaveAttribute("aria-invalid", "true");
    expect(isFiltered(emptyTradeFilters)).toBe(false);
    expect(isFiltered({ ...emptyTradeFilters, symbol: " " })).toBe(false);
    expect(isFiltered({ ...emptyTradeFilters, to: "2026-10-27" })).toBe(true);
  });
});
