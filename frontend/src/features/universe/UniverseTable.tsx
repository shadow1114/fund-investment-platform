import type { UniverseMember } from "../../api/generated/m17.schemas";
import { MetricValue } from "../../components/MetricValue";
import { ConditionList } from "./ConditionList";

type Props = {
  members: UniverseMember[];
  label: string;
};

export const UniverseTable = ({ members, label }: Props) => {
  if (members.length === 0) return <p>{label}：无</p>;

  return (
    <div role="region" aria-label={label} tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th scope="col">基金代码</th>
            <th scope="col">选择状态</th>
            <th scope="col">投资资格</th>
            <th scope="col">总分</th>
            <th scope="col">排名</th>
            <th scope="col">百分位</th>
            <th scope="col">层级</th>
            <th scope="col">条件明细</th>
          </tr>
        </thead>
        <tbody>
          {members.map((member) => (
            <tr key={`${member.selection_status}-${member.fund_id}`}>
              <th scope="row">{member.fund_id}</th>
              <td>{member.selection_status}</td>
              <td>{member.investment_eligibility ?? "未提供"}</td>
              <td>
                <MetricValue
                  value={member.total_score}
                  status={member.total_score_status}
                  reason={member.total_score_reason}
                />
              </td>
              <td>
                <MetricValue
                  value={member.rank}
                  status={member.rank_status}
                  reason={member.rank_reason}
                />
              </td>
              <td>
                <MetricValue
                  value={member.percentile}
                  status={member.percentile_status}
                  reason={member.percentile_reason}
                />
              </td>
              <td>{member.fund_tier ?? "不可用"}</td>
              <td>
                <ConditionList
                  fundId={member.fund_id}
                  kind="passed"
                  conditions={member.passed_conditions}
                />
                <ConditionList
                  fundId={member.fund_id}
                  kind="failed"
                  conditions={member.failed_conditions}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
