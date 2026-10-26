import { Anchor, Breadcrumbs, Group, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export type PageHeaderProps = {
  title: string;
  breadcrumbs: { label: string; href?: string }[];
  actions?: ReactNode;
  context?: ReactNode;
};

export const PageHeader = ({
  title,
  breadcrumbs,
  actions,
  context,
}: PageHeaderProps) => (
  <Stack gap="sm" mb="lg">
    {breadcrumbs.length > 0 && (
      <Breadcrumbs aria-label="面包屑">
        {breadcrumbs.map((item, index) =>
          item.href && index < breadcrumbs.length - 1 ? (
            <Anchor
              key={`${item.href}-${item.label}`}
              component={Link}
              to={item.href}
              size="sm"
            >
              {item.label}
            </Anchor>
          ) : (
            <Text key={item.label} size="sm" c="dimmed">
              {item.label}
            </Text>
          ),
        )}
      </Breadcrumbs>
    )}
    <Group justify="space-between" align="flex-start" wrap="wrap">
      <Stack gap={4}>
        <Title order={1} size="h1">
          {title}
        </Title>
        {context}
      </Stack>
      {actions}
    </Group>
  </Stack>
);
