import type { ReactNode } from "react";
export const PageLayout = ({
  title,
  navigation,
  children,
}: {
  title?: string;
  navigation?: ReactNode;
  children: ReactNode;
}) => (
  <>
    <header>{navigation}</header>
    <main>
      {title && <h1>{title}</h1>}
      {children}
    </main>
  </>
);
