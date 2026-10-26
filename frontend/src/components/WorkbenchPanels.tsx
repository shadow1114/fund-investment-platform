import { Group } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import type { ReactNode } from "react";

import styles from "./Workbench.module.css";

type LayoutKey = "portfolio" | "backtest";
type Props = {
  layoutKey: LayoutKey;
  primary: ReactNode;
  secondary: ReactNode;
  primaryLabel: string;
  secondaryLabel: string;
};

const VERSION = 1;
const validLayout = (value: unknown): value is [number, number] =>
  Array.isArray(value) &&
  value.length === 2 &&
  value.every((size) => typeof size === "number" && Number.isFinite(size)) &&
  Math.abs(value[0] + value[1] - 100) < 0.1 &&
  value[0] >= 30 &&
  value[1] >= 40;

const readLayout = (key: string): [number, number] => {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "null");
    if (
      typeof value === "object" &&
      value !== null &&
      "version" in value &&
      value.version === VERSION &&
      "layout" in value &&
      validLayout(value.layout)
    ) {
      return value.layout;
    }
  } catch {
    // Layout is a preference; invalid or blocked storage falls back safely.
  }
  return [35, 65];
};

export const WorkbenchPanels = ({
  layoutKey,
  primary,
  secondary,
  primaryLabel,
  secondaryLabel,
}: Props) => {
  const desktop = useMediaQuery("(min-width: 1280px)", false);
  const key = `fip:panels:${layoutKey}:v${VERSION}`;
  const layout = readLayout(key);

  if (!desktop) {
    return (
      <Group className={styles.panels} align="stretch" gap={0}>
        <section className={styles.panel} aria-label={primaryLabel}>
          {primary}
        </section>
        <section className={styles.panel} aria-label={secondaryLabel}>
          {secondary}
        </section>
      </Group>
    );
  }

  return (
    <PanelGroup
      direction="horizontal"
      className={styles.panels}
      onLayout={(sizes) => {
        if (!validLayout(sizes)) return;
        try {
          localStorage.setItem(
            key,
            JSON.stringify({ version: VERSION, layout: sizes }),
          );
        } catch {
          // Resizing remains available if storage is unavailable.
        }
      }}
    >
      <Panel
        order={1}
        defaultSize={layout[0]}
        minSize={30}
        className={styles.panel}
        aria-label={primaryLabel}
      >
        {primary}
      </Panel>
      <PanelResizeHandle
        className={styles.panelDivider}
        aria-label={`调整分栏：${primaryLabel}与${secondaryLabel}`}
      />
      <Panel
        order={2}
        defaultSize={layout[1]}
        minSize={40}
        className={styles.panel}
        aria-label={secondaryLabel}
      >
        {secondary}
      </Panel>
    </PanelGroup>
  );
};
