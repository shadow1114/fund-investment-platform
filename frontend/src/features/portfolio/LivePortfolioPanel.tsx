import { ResearchDataTable } from "../../components/ResearchDataTable";
import { Alert, Button, Paper, Stack, Text, Title } from "@mantine/core";

export const LivePortfolioPanel = ({
  portfolioId,
}: {
  portfolioId: string;
}) => (
  <Paper withBorder radius="sm" p="md" aria-label="实盘持仓与三态监控">
    <Stack gap="md">
      <div>
        <Title order={2} size="h3">
          实盘持仓
        </Title>
        <Text size="sm" c="dimmed">
          组合 {portfolioId} · Target、Pending 与 Actual 分开展示。
        </Text>
      </div>
      <Alert color="red" title="实盘数据源不可交付">
        当前后端首次读取时创建固定演示持仓，并把状态保存在 API
        进程内存；重启会丢失，也没有账户连接或持久化成交账本。本页面不把这些值展示为真实持仓。
      </Alert>
      <div
        role="region"
        aria-label="Target、Pending、Actual 持仓数据状态"
        tabIndex={0}
        className="table-scroll"
      >
        <ResearchDataTable
          caption="组合三态持仓数据状态"
          layoutKey="live-status"
          rowData={[
            {
              column0: "Target 目标仓位",
              column1: "未连接已审查的优化/决策资源",
              column2: "不可用",
            },
            {
              column0: "Pending 在途仓位",
              column1: "未接入持久化委托与成交回报",
              column2: "不可用",
            },
            {
              column0: "Actual 实际仓位",
              column1: "无经核验的账户持仓来源",
              column2: "不可用",
            },
          ]}
          getRowId={({ data }) => data.column0}
          columnDefs={[
            {
              field: "column0",
              headerName: "状态",
              wrapText: true,
              autoHeight: true,
            },
            {
              field: "column1",
              headerName: "数据来源",
              wrapText: true,
              autoHeight: true,
            },
            {
              field: "column2",
              headerName: "可用性",
              wrapText: true,
              autoHeight: true,
            },
          ]}
        />
      </div>
      <Alert color="yellow" variant="light">
        提交成交回报已停用：当前接口会修改进程内演示状态，不能形成可追溯的实际记账。上线前需要持久化持仓、现金、成交去重和授权检查。
      </Alert>
      <Button type="button" disabled aria-disabled="true">
        成交回报暂不可提交
      </Button>
    </Stack>
  </Paper>
);
