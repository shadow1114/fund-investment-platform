import { Alert, Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";
import { emptyFundFilters } from "./FundFilters";

const storageKey = "fip:fund-views:v1";
type View = { name: string; filters: string };
const allowedKeys = new Set(Object.keys(emptyFundFilters()));

// Keep filter fields and reset pagination; unrelated URL parameters and results are excluded.
const cleanFilters = (raw: string) => {
  const source = new URLSearchParams(raw);
  const result = new URLSearchParams();
  for (const key of allowedKeys) {
    const value = source.get(key);
    if (value) result.set(key, value);
  }
  result.set("page", "1");
  return result.toString();
};

const readViews = (): View[] => {
  try {
    const parsed: unknown = JSON.parse(
      localStorage.getItem(storageKey) ?? "null",
    );
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !("version" in parsed) ||
      parsed.version !== 1 ||
      !("views" in parsed) ||
      !Array.isArray(parsed.views)
    )
      return [];
    return parsed.views.flatMap((view: unknown) => {
      if (
        !view ||
        typeof view !== "object" ||
        !("name" in view) ||
        !("filters" in view) ||
        typeof view.name !== "string" ||
        !view.name.trim() ||
        typeof view.filters !== "string"
      )
        return [];
      return [{ name: view.name, filters: cleanFilters(view.filters) }];
    });
  } catch {
    return [];
  }
};

export const SavedFundViews = ({
  filters,
  onApply,
}: {
  filters: string;
  onApply: (filters: string) => void;
}) => {
  const [views, setViews] = useState(readViews);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const saveViews = (next: View[]) => {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ version: 1, views: next }),
      );
      setViews(next);
      setError("");
      return true;
    } catch {
      setError("无法保存视图，请检查浏览器存储设置。");
      return false;
    }
  };
  const save = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("请填写视图名称。");
      return;
    }
    if (views.some((view) => view.name === trimmed)) {
      setError("视图名称已存在。");
      return;
    }
    if (
      saveViews([...views, { name: trimmed, filters: cleanFilters(filters) }])
    )
      setName("");
  };
  return (
    <section aria-label="保存的筛选视图">
      <Stack gap="xs">
        <Text fw={600}>筛选视图</Text>
        <Text size="sm" c="dimmed">
          保存当前已应用的筛选条件到此浏览器。
        </Text>
        <Group align="end" wrap="wrap">
          <TextInput
            label="视图名称"
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={80}
          />
          <Button variant="default" onClick={save}>
            保存当前视图
          </Button>
        </Group>
        {error && (
          <Alert color="red" role="alert">
            {error}
          </Alert>
        )}
        {views.map((view) => (
          <Group key={view.name} gap="xs">
            <Text size="sm">{view.name}</Text>
            <Button
              size="compact-xs"
              variant="light"
              aria-label={`应用视图 ${view.name}`}
              onClick={() => onApply(view.filters)}
            >
              应用
            </Button>
            <Button
              size="compact-xs"
              variant="subtle"
              aria-label={`删除视图 ${view.name}`}
              onClick={() =>
                saveViews(views.filter((item) => item.name !== view.name))
              }
            >
              删除
            </Button>
          </Group>
        ))}
      </Stack>
    </section>
  );
};
