import { createTheme, type MantineColorsTuple } from "@mantine/core";

const teal: MantineColorsTuple = [
  "#E8F5F5",
  "#D3EBED",
  "#ADDBDF",
  "#82C8CE",
  "#55AFB9",
  "#2C98A4",
  "#087F8C",
  "#076B77",
  "#075761",
  "#06434A",
];

export const workbenchColors = {
  background: "#F3F6FB",
  sidebar: "#101827",
  highlight: "#14B8A6",
  secondary: "#3B82F6",
  surface: "#FFFFFF",
  text: "#17243A",
  mutedText: "#596572",
  border: "#DFE6EF",
  accent: "#087F8C",
  accentHover: "#076B77",
  success: "#237A50",
  warning: "#9A6700",
  danger: "#B42318",
} as const;

export const chartPalette = {
  primary: workbenchColors.accent,
  benchmark: "#3267A8",
  equalWeight: "#687684",
  drawdown: workbenchColors.danger,
} as const;

export const theme = createTheme({
  primaryColor: "workbenchTeal",
  primaryShade: 6,
  colors: { workbenchTeal: teal },
  fontFamily:
    'Inter, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  headings: {
    fontFamily:
      'Inter, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
    fontWeight: "600",
    sizes: { h1: { fontSize: "1.375rem", lineHeight: "1.4" } },
  },
  fontSizes: {
    xs: "0.75rem",
    sm: "0.875rem",
    md: "0.875rem",
    lg: "1rem",
    xl: "1.375rem",
  },
  spacing: {
    xs: "0.25rem",
    sm: "0.5rem",
    md: "0.75rem",
    lg: "1rem",
    xl: "1.5rem",
  },
  radius: { xs: "0.25rem", sm: "0.25rem", md: "0.375rem", lg: "0.5rem" },
  defaultRadius: "sm",
  components: {
    Button: { defaultProps: { size: "sm" } },
    TextInput: { defaultProps: { size: "sm" } },
    NumberInput: { defaultProps: { size: "sm" } },
    Select: { defaultProps: { size: "sm" } },
    MultiSelect: { defaultProps: { size: "sm" } },
  },
});
