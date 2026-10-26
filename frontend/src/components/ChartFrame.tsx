import { Paper, Stack, Text, Title } from "@mantine/core";
import { useResizeObserver } from "@mantine/hooks";
import { useEffect, type ReactNode, type RefObject } from "react";

import styles from "./Workbench.module.css";

export const ChartFrame = ({
  title,
  description,
  chart,
  table,
  onResize,
}: {
  title: string;
  description: string;
  chart: ReactNode;
  table?: ReactNode;
  onResize?: () => void;
}) => {
  const [ref, rect] = useResizeObserver<HTMLDivElement>();
  useEffect(() => {
    if (rect.width > 0 && rect.height > 0) onResize?.();
  }, [onResize, rect.height, rect.width]);

  return (
    <Paper withBorder radius="sm" p="md" aria-label={title}>
      <Stack gap="sm">
        <div>
          <Title order={3} size="h4">
            {title}
          </Title>
          <Text size="sm" c="dimmed">
            {description}
          </Text>
        </div>
        <div
          ref={ref as RefObject<HTMLDivElement>}
          className={styles.chartContainer}
        >
          {chart}
        </div>
        {table && (
          <details>
            <summary>查看图表数值</summary>
            {table}
          </details>
        )}
      </Stack>
    </Paper>
  );
};
