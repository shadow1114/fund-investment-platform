import { Alert, Paper, Stack, Table, Text, Title } from "@mantine/core";

export const RebalancingPanel = ({ portfolioId }: { portfolioId: string }) => (
  <Paper withBorder radius="sm" p="md" aria-label="动态再平衡与调仓评估">
    <Stack gap="md">
      <div>
        <Title order={2} size="h3">
          再平衡评估
        </Title>
        <Text size="sm" c="dimmed">
          组合 {portfolioId} · 评估结果、触发原因与交易清单。
        </Text>
      </div>
      <Alert color="red" title="再平衡服务未接入真实数据">
        当前端点基于进程内固定持仓，并由浏览器传入价格和预期改善值；这些假设无法证明市场价格、当前实际仓位或成本来源，历史记录也只保存在进程内。为避免生成误导性交易建议，本页面不发起评估请求。
      </Alert>
      <Table withTableBorder withColumnBorders>
        <caption>再平衡能力状态</caption>
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">能力</Table.Th>
            <Table.Th scope="col">当前结果</Table.Th>
            <Table.Th scope="col">缺失来源</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          <Table.Tr>
            <Table.Th scope="row">触发原因与重算范围</Table.Th>
            <Table.Td>不可用</Table.Td>
            <Table.Td>持久化实际仓位、真实估值日期、已应用规则版本</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Th scope="row">成本收益与过滤原因</Table.Th>
            <Table.Td>不可用</Table.Td>
            <Table.Td>版本化交易成本和预期改善估计</Table.Td>
          </Table.Tr>
          <Table.Tr>
            <Table.Th scope="row">历史事件与交易详情</Table.Th>
            <Table.Td>不可用</Table.Td>
            <Table.Td>数据库事件/交易记录及跨重启查询端点</Table.Td>
          </Table.Tr>
        </Table.Tbody>
      </Table>
      <Alert color="blue" variant="light">
        补齐持久化和真实数据契约后，再启用带版本化输入、理由明细和历史详情的评估操作。当前不提供“执行调仓”或自动下单入口。
      </Alert>
    </Stack>
  </Paper>
);
