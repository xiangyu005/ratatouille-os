/**
 * Server state lives in TanStack Query, never in the UI store
 * (`docs/22-01` §5.1). CORE is authoritative; this module only caches.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { core, unwrap } from "./client";
import type { components } from "./schema";

export type CommandRequest = components["schemas"]["CommandRequest"];
export type CommandResponse = components["schemas"]["CommandResponse"];
export type MetaResponse = {
  request_id: string;
  service: string;
  version: string;
  schema_version: number;
  algorithms: Array<{ name: string; label: string; assignable: boolean }>;
  policies: string[];
  default_policy: string;
};
export type ResourceResponse = components["schemas"]["ResourceResponse"];
export type SnapshotResponse = components["schemas"]["SnapshotResponse"];
export type TaskListResponse = components["schemas"]["TaskListResponse"];

async function getSnapshot(): Promise<SnapshotResponse> {
  return unwrap<SnapshotResponse>(await core.GET("/api/v1/snapshot"));
}

async function getTasks(): Promise<TaskListResponse> {
  return unwrap<TaskListResponse>(await core.GET("/api/v1/tasks"));
}

async function getResources(): Promise<ResourceResponse> {
  return unwrap<ResourceResponse>(await core.GET("/api/v1/resources"));
}

async function getMeta(): Promise<MetaResponse> {
  return unwrap<MetaResponse>(await core.GET("/api/v1/meta"));
}

export function useSnapshot() {
  return useQuery({ queryKey: ["snapshot"], queryFn: getSnapshot });
}

export function useTasks() {
  return useQuery({ queryKey: ["tasks"], queryFn: getTasks });
}

export function useResources() {
  return useQuery({ queryKey: ["resources"], queryFn: getResources });
}

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: getMeta, staleTime: 60_000 });
}

export function useSendCommand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<CommandRequest, "client">) =>
      unwrap<CommandResponse>(
        await core.POST("/api/v1/commands", { body: { ...body, client: "fe" } }),
      ),
    // No optimistic update: the world changes when CORE says so (`docs/22-01` §5.2).
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["snapshot"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
