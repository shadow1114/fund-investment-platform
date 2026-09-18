import ReactECharts from "echarts-for-react";

import type { NavPoint } from "../../api/generated/m17.schemas";
import { MetricValue } from "../../components/MetricValue";

export const FundNavChart = ({ points }: { points: NavPoint[] }) => {
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
        data: availablePoints.map((point) => [point.date, point.nav]),
      },
    ],
  };

  return (
    <section aria-label="净值序列">
      {availablePoints.length > 0 ? (
        <ReactECharts option={option} style={{ height: 360 }} />
      ) : (
        <p>暂无可绘制的净值数据</p>
      )}
      {points.length === 0 ? (
        <p>暂无净值数据</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">日期</th>
              <th scope="col">净值</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.date}>
                <td>{point.date}</td>
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
      )}
    </section>
  );
};
