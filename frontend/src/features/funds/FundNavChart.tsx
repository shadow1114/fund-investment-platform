import ReactEChartsCore from "echarts-for-react/lib/core";
import { useCallback, useRef } from "react";

import type { NavPoint } from "../../api/generated/m17.schemas";
import { ChartFrame } from "../../components/ChartFrame";
import { MetricValue } from "../../components/MetricValue";
import { echarts } from "../charts/echarts";

export const FundNavChart = ({ points }: { points: NavPoint[] }) => {
  const chart = useRef<ReactEChartsCore | null>(null);
  const resizeChart = useCallback(() => {
    chart.current?.getEchartsInstance().resize();
  }, []);
  const availablePoints = points.filter(
    (point): point is NavPoint & { nav: number } =>
      point.nav_status === "VALID" && point.nav !== null,
  );
  const option = {
    aria: { enabled: true, description: "基金净值时间序列" },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: availablePoints.map((point) => point.date),
    },
    yAxis: { type: "value", scale: true },
    series: [
      {
        name: "净值",
        type: "line",
        showSymbol: false,
        data: points.map((point) => [
          point.date,
          point.nav_status === "VALID" ? point.nav : null,
        ]),
      },
    ],
  };

  return (
    <section aria-label="净值序列">
      {points.length === 0 ? (
        <p>暂无净值数据</p>
      ) : (
        <ChartFrame
          title="净值序列"
          description={`显示 ${availablePoints.length} 个有效点 / ${points.length} 个返回点。净值按估值日展示，缺失值不会绘制为零。`}
          onResize={resizeChart}
          chart={
            availablePoints.length > 0 ? (
              <ReactEChartsCore
                echarts={echarts}
                ref={chart}
                option={option}
                autoResize
                style={{ height: "100%", minHeight: 320, width: "100%" }}
              />
            ) : (
              <p>暂无可绘制的净值数据；下表保留每个点的不可用原因。</p>
            )
          }
          table={
            <div
              className="table-scroll"
              role="region"
              aria-label="净值数值表"
              tabIndex={0}
            >
              <table>
                <thead>
                  <tr>
                    <th scope="col">估值日</th>
                    <th scope="col">净值</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((point) => (
                    <tr key={point.date}>
                      <th scope="row">{point.date}</th>
                      <td>
                        <MetricValue
                          value={point.nav}
                          status={point.nav_status}
                          reason={point.nav_reason ?? point.reason_code}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
        />
      )}
    </section>
  );
};
