import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import {
  getLatestIngestionQueryOptions,
  ingestionKeys,
  invalidateIngestionFundData,
} from "../../api/queries";

// Lives in the workspace shell so completing a job refreshes fund data even
// after the user has left the data center or closed its task detail.
export const IngestionCompletionWatcher = ({
  enabled,
}: {
  enabled: boolean;
}) => {
  const client = useQueryClient();
  const latest = useQuery({ ...getLatestIngestionQueryOptions(), enabled });
  const observed = useRef<string>();
  const task = latest.data?.items[0];
  useEffect(() => {
    if (!enabled || !task || task.status === "RUNNING" || !task.finished_at)
      return;
    const version = `${task.operation_id}:${task.finished_at}:${task.status}`;
    if (observed.current === version) return;
    observed.current = version;
    void Promise.all([
      invalidateIngestionFundData(client),
      client.invalidateQueries({ queryKey: ingestionKeys.history }),
      client.invalidateQueries({ queryKey: ["api", "ingestion-items"] }),
      client.invalidateQueries({ queryKey: ["api", "ingestion-tasks"] }),
    ]);
  }, [client, enabled, task]);
  return null;
};
