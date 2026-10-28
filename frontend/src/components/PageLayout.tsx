import {
  AppShell,
  TextInput,
  Burger,
  Button,
  Drawer,
  Group,
  NavLink,
  Text,
} from "@mantine/core";
import { useDebouncedValue, useDisclosure } from "@mantine/hooks";
import {
  Activity,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  Database,
  FolderKanban,
  House,
  Layers3,
  type LucideIcon,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState, type ReactNode } from "react";
import { getSessionQueryOptions, listFundsQueryOptions } from "../api/queries";
import styles from "./PageLayout.module.css";
import { IngestionCompletionWatcher } from "../features/ingestion/IngestionCompletionWatcher";

const links: {
  label: string;
  href: string;
  icon: LucideIcon;
  capability?: "can_manage_data_ingestion" | "can_review_classifications";
}[] = [
  { label: "工作台", href: "/home", icon: House },
  { label: "基金研究", href: "/funds", icon: ChartNoAxesCombined },
  { label: "候选池", href: "/universes", icon: FolderKanban },
  { label: "组合管理", href: "/portfolios", icon: BriefcaseBusiness },
  { label: "策略回测", href: "/backtests", icon: Activity },
  {
    label: "数据抓取",
    href: "/data-ingestion",
    icon: Database,
    capability: "can_manage_data_ingestion",
  },
  {
    label: "分类复核",
    href: "/classification-reviews",
    icon: Layers3,
    capability: "can_review_classifications",
  },
];

export const PageLayout = ({ children }: { children: ReactNode }) => {
  const [opened, { toggle, close }] = useDisclosure();
  const [collapsed, { toggle: toggleCollapsed }] = useDisclosure(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search.trim(), 250);
  const location = useLocation();
  const navigate = useNavigate();
  const session = useQuery(getSessionQueryOptions());
  const funds = useQuery({
    ...listFundsQueryOptions({ fund_name: debouncedSearch, page_size: 5 }),
    enabled: Boolean(debouncedSearch),
  });
  const userLabel = session.isError
    ? "身份不可用"
    : session.isSuccess
      ? session.data.user_id
      : "身份读取中";
  const navigation = (compact = false) => (
    <nav aria-label="主导航">
      {links
        .filter(
          (link) =>
            !link.capability ||
            (session.isSuccess &&
              session.data.capabilities[link.capability] === true),
        )
        .map(({ label, href, icon: Icon }) => {
          const active =
            location.pathname === href ||
            location.pathname.startsWith(`${href}/`);
          return (
            <NavLink
              key={href}
              component={Link}
              to={href}
              label={compact ? undefined : label}
              aria-label={label}
              title={compact ? label : undefined}
              aria-current={active ? "page" : undefined}
              leftSection={<Icon size={19} aria-hidden="true" />}
              active={active}
              onClick={close}
              className={styles.navItem}
            />
          );
        })}
    </nav>
  );
  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{
        width: collapsed ? 68 : 240,
        breakpoint: "sm",
        collapsed: { mobile: true },
      }}
      padding={0}
      classNames={{ main: styles.main }}
    >
      <IngestionCompletionWatcher
        enabled={
          session.isSuccess &&
          session.data.capabilities.can_manage_data_ingestion === true
        }
      />
      <a href="#main-content" className={styles.skipLink}>
        跳至主要内容
      </a>
      <AppShell.Header className={styles.header}>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap" gap="sm">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              aria-label={opened ? "关闭导航" : "打开导航"}
              aria-expanded={opened}
              aria-controls="mobile-navigation"
            />
            <Burger
              opened={!collapsed}
              onClick={toggleCollapsed}
              visibleFrom="sm"
              size="sm"
              aria-label={collapsed ? "展开侧栏" : "折叠侧栏"}
              aria-expanded={!collapsed}
            />
            <Text fw={700} size="sm" className={styles.brand}>
              基金投研工作台
            </Text>
          </Group>
          <form
            aria-label="基金快速定位"
            className={styles.search}
            onSubmit={(event) => {
              event.preventDefault();
              if (search.trim())
                navigate(
                  `/funds?fund_name=${encodeURIComponent(search.trim())}`,
                );
            }}
          >
            <TextInput
              aria-label="基金快速定位"
              placeholder="搜索基金名称"
              value={search}
              onChange={(event) => setSearch(event.currentTarget.value)}
              list="workspace-fund-suggestions"
            />
            <datalist id="workspace-fund-suggestions">
              {[
                ...new Set((funds.data ?? []).map((fund) => fund.fund_name)),
              ].map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </datalist>
            <Button type="submit" variant="light" disabled={!search.trim()}>
              查找
            </Button>
            {funds.isError && (
              <Text size="xs" role="status" className={styles.searchStatus}>
                搜索暂不可用，可提交到基金研究重试
              </Text>
            )}
          </form>
          <Text
            size="xs"
            className={styles.session}
            title={
              session.isSuccess
                ? `${session.data.user_id} · ${session.data.roles.join("、")}`
                : userLabel
            }
            aria-label="当前身份"
            role="status"
          >
            {userLabel}
          </Text>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" className={styles.navbar}>
        <Text
          className={styles.workspaceLabel}
          size="xs"
          mb="lg"
          mt="md"
          aria-hidden="true"
        >
          {collapsed ? "投研" : "客户投资工作区"}
        </Text>
        {navigation(collapsed)}
      </AppShell.Navbar>
      <Drawer
        opened={opened}
        onClose={close}
        title="客户投资工作区"
        size={280}
        id="mobile-navigation"
        classNames={{
          content: styles.drawer,
          header: styles.drawer,
          title: styles.drawerTitle,
          close: styles.drawerClose,
        }}
      >
        {navigation()}
      </Drawer>
      <AppShell.Main component="div">
        <main id="main-content" tabIndex={-1} className={styles.content}>
          {children}
        </main>
      </AppShell.Main>
    </AppShell>
  );
};
