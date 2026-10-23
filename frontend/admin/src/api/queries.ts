import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  CheckReport,
  Deal,
  DealInput,
  DealStatus,
  Me,
  Page,
  Platform,
  Price,
  PriceInput,
  Source,
  SourceInput,
} from "./types";

export interface DealQuery {
  status?: DealStatus | undefined;
  platform_id?: number | undefined;
  q?: string | undefined;
  page: number;
  page_size: number;
}

export interface PriceQuery {
  platform_id?: number | undefined;
  q?: string | undefined;
  page: number;
  page_size: number;
}

export const useMe = () =>
  useQuery({ queryKey: ["me"], queryFn: () => api<Me>("GET", "/me"), retry: false });

export const usePlatforms = () =>
  useQuery({
    queryKey: ["platforms"],
    queryFn: () => api<Platform[]>("GET", "/platforms"),
    staleTime: 5 * 60_000,
  });

export const useDeals = (query: DealQuery) =>
  useQuery({
    queryKey: ["deals", query],
    queryFn: () => api<Page<Deal>>("GET", "/deals", { params: { ...query } }),
    placeholderData: keepPreviousData, // 翻页 / 切筛选时保留旧数据，不闪空白
  });

export const usePrices = (query: PriceQuery) =>
  useQuery({
    queryKey: ["prices", query],
    queryFn: () => api<Page<Price>>("GET", "/prices", { params: { ...query } }),
    placeholderData: keepPreviousData,
  });

export function useSaveDeal() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id?: number | undefined; input: DealInput }) =>
      id === undefined
        ? api<Deal>("POST", "/deals", { body: input })
        : api<Deal>("PUT", `/deals/${id}`, { body: input }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["deals"] }),
  });
}

export type DealAction = "publish" | "expire" | "reconfirm" | "reject";

const OPTIMISTIC_STATUS: Partial<Record<DealAction, DealStatus>> = {
  publish: "active",
  expire: "expired",
  reject: "rejected",
};

/** 审核操作：先在列表里乐观更新状态，失败时回滚，最后以服务端结果为准 */
export function useDealAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, reason }: { id: number; action: DealAction; reason?: string }) =>
      api<Deal>("POST", `/deals/${id}/${action}`, action === "reject" ? { body: { reason } } : {}),
    onMutate: async ({ id, action }) => {
      await client.cancelQueries({ queryKey: ["deals"] });
      const snapshot = client.getQueriesData<Page<Deal>>({ queryKey: ["deals"] });
      const status = OPTIMISTIC_STATUS[action];
      if (status) {
        client.setQueriesData<Page<Deal>>({ queryKey: ["deals"] }, (page) =>
          page
            ? { ...page, items: page.items.map((d) => (d.id === id ? { ...d, status } : d)) }
            : page,
        );
      }
      return { snapshot };
    },
    onError: (_err, _vars, context) => {
      for (const [key, data] of context?.snapshot ?? []) client.setQueryData(key, data);
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["deals"] }),
  });
}

export function useSavePrice() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: PriceInput) => api<Price>("POST", "/prices", { body: input }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["prices"] }),
  });
}

export interface SourceQuery {
  platform_id?: number | undefined;
  page: number;
  page_size: number;
}

export const useSources = (query: SourceQuery) =>
  useQuery({
    queryKey: ["sources", query],
    queryFn: () => api<Page<Source>>("GET", "/sources", { params: { ...query } }),
    placeholderData: keepPreviousData,
  });

export function useSaveSource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id?: number | undefined; input: SourceInput }) =>
      id === undefined
        ? api<Source>("POST", "/sources", { body: input })
        : api<Source>("PUT", `/sources/${id}`, { body: input }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function useDeleteSource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>("DELETE", `/sources/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["sources"] }),
  });
}

/** 立即检查：可能新增待审核活动，活动列表一并刷新 */
export function useCheckSource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<CheckReport>("POST", `/sources/${id}/check`),
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["sources"] }),
        client.invalidateQueries({ queryKey: ["deals"] }),
      ]),
  });
}

export function usePriceVisibility() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, visible }: { id: number; visible: boolean }) =>
      api<Price>("POST", `/prices/${id}/${visible ? "show" : "hide"}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["prices"] }),
  });
}
