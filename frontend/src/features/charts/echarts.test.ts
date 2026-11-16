import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { describe, expect, it, vi } from "vitest";

import "./echarts";

echarts.use([SVGRenderer]);

describe("ECharts chart registrations", () => {
  it("registers the bar series used for excess returns", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      measureText: () => ({ width: 10 }),
    } as unknown as CanvasRenderingContext2D);
    const chart = echarts.init(null, undefined, {
      renderer: "svg",
      ssr: true,
      width: 200,
      height: 100,
    });
    chart.setOption({
      xAxis: { type: "category", data: ["2026-01-01"] },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: [1] }],
    });

    const model = (
      chart as unknown as {
        getModel: () => { getSeriesByIndex: (index: number) => unknown };
      }
    ).getModel();
    expect(model.getSeriesByIndex(0)).toBeDefined();
    chart.dispose();
  });
});
