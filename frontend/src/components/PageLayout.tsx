import { AppShell, Burger, Group, NavLink, Text, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  Activity,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  FolderKanban,
  Layers3,
  type LucideIcon,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { getSessionQueryOptions } from "../api/queries";
import styles from "./PageLayout.module.css";

const links: { label: string; href: string; icon: LucideIcon }[] = [
  { label: "基金研究", href: "/funds", icon: ChartNoAxesCombined },
  { label: "分类复核", href: "/classification-reviews", icon: Layers3 },
  { label: "候选池", href: "/universes", icon: FolderKanban },
  { label: "组合决策", href: "/portfolios", icon: BriefcaseBusiness },
  { label: "回测分析", href: "/backtests", icon: Activity },
];

export const PageLayout = ({ children }: { children: ReactNode }) => {
  const [opened, { toggle, close }] = useDisclosure();
  const [collapsed, setCollapsed] = useDisclosure(false);
  const location = useLocation();
  const session = useQuery(getSessionQueryOptions());
  const isDevelopment = import.meta.env.DEV;
  const userLabel =
    session.data?.user_id ?? (session.isError ? "身份不可用" : "身份读取中");
  const roleLabel = session.data?.roles?.length
    ? session.data.roles.join("、")
    : session.isError
      ? "权限未知"
      : "权限读取中";

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: collapsed ? 64 : 224,
        breakpoint: "sm",
        collapsed: { mobile: !opened },
      }}
      padding={0}
      classNames={{ main: styles.main }}
    >
      <a href="#main-content" className={styles.skipLink}>
        跳至主要内容
      </a>
      <AppShell.Header className={styles.header}>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              aria-label={opened ? "关闭导航" : "打开导航"}
            />
            <Burger
              opened={!collapsed}
              onClick={() => setCollapsed.toggle()}
              visibleFrom="sm"
              size="sm"
              aria-label={collapsed ? "展开侧栏" : "折叠侧栏"}
            />
            <Text fw={650} size="sm" className={styles.brand}>
              基金投研工作台
            </Text>
          </Group>
          <Group gap="md" wrap="nowrap" className={styles.session}>
            <Text size="xs" c="dimmed" className={styles.environment}>
              {isDevelopment ? "开发环境" : "生产环境"}
            </Text>
            <Tooltip label={`${userLabel} · ${roleLabel}`}>
              <Text size="sm" truncate maw={240} aria-label="当前身份">
                {userLabel} · {roleLabel}
              </Text>
            </Tooltip>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs" className={styles.navbar}>
        <nav aria-label="主导航">
          {links.map(({ label, href, icon: Icon }) => {
            const active =
              location.pathname === href ||
              location.pathname.startsWith(`${href}/`);
            const item = (
              <NavLink
                key={href}
                component={Link}
                to={href}
                label={collapsed ? undefined : label}
                aria-label={label}
                leftSection={<Icon size={18} aria-hidden="true" />}
                active={active}
                onClick={close}
                className={styles.navItem}
              />
            );
            return collapsed ? (
              <Tooltip key={href} label={label} position="right">
                {item}
              </Tooltip>
            ) : (
              item
            );
          })}
        </nav>
      </AppShell.Navbar>
      <AppShell.Main>
        <div id="main-content" className={styles.content}>
          {children}
        </div>
      </AppShell.Main>
    </AppShell>
  );
};
