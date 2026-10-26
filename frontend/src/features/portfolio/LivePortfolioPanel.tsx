import { Alert, Button, Paper, Stack, Table, Text, Title } from "@mantine/core";

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
        <Table withTableBorder withColumnBorders>
          <caption>组合三态持仓数据状态</caption>
          <Table.Thead>
            <Table.Tr>
              <Table.Th scope="col">状态</Table.Th>
              <Table.Th scope="col">数据来源</Table.Th>
              <Table.Th scope="col">可用性</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            <Table.Tr>
              <Table.Th scope="row">Target 目标仓位</Table.Th>
              <Table.Td>未连接已审查的优化/决策资源</Table.Td>
              <Table.Td>不可用</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Th scope="row">Pending 在途仓位</Table.Th>
              <Table.Td>未接入持久化委托与成交回报</Table.Td>
              <Table.Td>不可用</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Th scope="row">Actual 实际仓位</Table.Th>
              <Table.Td>无经核验的账户持仓来源</Table.Td>
              <Table.Td>不可用</Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
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
