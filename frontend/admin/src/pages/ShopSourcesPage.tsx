import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { SHOP_KIND_LABELS } from "../api/labels";
import { type ShopSourceQuery, useShopSources, useSyncShopSource } from "../api/queries";
import type { ShopCollectorKind, ShopSource, ShopSyncReport } from "../api/types";
import { WEB_ORIGIN } from "../lib/env";
import { formatDateTime, fromNow } from "../lib/format";
import { useErrorNotice } from "../lib/useErrorNotice";
import { ShopSourceModal } from "./ShopSourceModal";

type StateFilter = NonNullable<ShopSourceQuery["state"]> | "all";

const STATE_OPTIONS: { value: StateFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "ok", label: "正常" },
  { value: "failed", label: "失败" },
  { value: "unchecked", label: "未采集" },
];
const KIND_OPTIONS = (Object.keys(SHOP_KIND_LABELS) as ShopCollectorKind[]).map((value) => ({
  value,
  label: SHOP_KIND_LABELS[value],
}));

function reportText(r: ShopSyncReport): string {
  if (r.status === "failed") return `采集失败：${r.error}`;
  return `采集完成：${r.offers} 条报价，新增 ${r.created} 条，${r.gone} 条下架`;
}

function StatusCell({ source }: { source: ShopSource }) {
  if (!source.enabled) return <Tag>已停用</Tag>;
  if (!source.checked_at) return <Tag>未采集</Tag>;
  if (source.last_error) {
    return (
      <Tooltip title={source.last_error}>
        <Tag color="red">失败 {source.fail_count} 次</Tag>
      </Tooltip>
    );
  }
  return <Tag color="green">正常</Tag>;
}

export function ShopSourcesPage() {
  const [params, setParams] = useSearchParams();
  const state = (params.get("state") ?? "all") as StateFilter;
  const kind = (params.get("kind") ?? undefined) as ShopCollectorKind | undefined;
  const q = params.get("q") ?? undefined;
  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("size") ?? 20);

  const update = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === undefined || value === "" || value === "all") next.delete(key);
      else next.set(key, value);
    }
    if (!("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };

  const sources = useShopSources({
    state: state === "all" ? undefined : state,
    collector_kind: kind,
    q,
    page,
    page_size: pageSize,
  });
  const sync = useSyncShopSource();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();
  const [editing, setEditing] = useState<ShopSource | null | undefined>(undefined);
  const [syncingId, setSyncingId] = useState<number | null>(null);

  const runSync = (source: ShopSource) => {
    setSyncingId(source.id);
    sync.mutate(source.id, {
      onSuccess: (r) => {
        if (r.status === "failed") message.warning(reportText(r));
        else message.success(reportText(r));
      },
      onError: (err) => notifyError(`采集失败：${source.entry_url}`, err),
      onSettled: () => setSyncingId(null),
    });
  };

  const columns: ColumnsType<ShopSource> = [
    {
      title: "店铺",
      key: "shop",
      render: (_, s) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link href={s.entry_url} target="_blank" rel="noopener noreferrer" ellipsis>
            {s.entry_url}
          </Typography.Link>
          {s.name && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {s.name}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: "店铺系统",
      dataIndex: "collector_kind",
      width: 150,
      render: (k: ShopCollectorKind) => SHOP_KIND_LABELS[k],
    },
    { title: "状态", key: "status", width: 110, render: (_, s) => <StatusCell source={s} /> },
    { title: "报价", dataIndex: "offer_count", width: 80, align: "right" },
    {
      title: "上次采集",
      dataIndex: "checked_at",
      width: 110,
      render: (v: string | null) => <Tooltip title={formatDateTime(v)}>{fromNow(v)}</Tooltip>,
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 180,
      render: (_, s) => (
        <Space size={4}>
          <Button
            size="small"
            type="primary"
            loading={syncingId === s.id}
            disabled={syncingId !== null && syncingId !== s.id}
            onClick={() => runSync(s)}
          >
            立即采集
          </Button>
          <Button size="small" onClick={() => setEditing(s)}>
            编辑
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="卡网店铺"
      extra={
        <Space>
          <Button href={`${WEB_ORIGIN}/products`} target="_blank" rel="noopener">
            看公开页
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing(null)}>
            添加店铺
          </Button>
        </Space>
      }
    >
      <Typography.Paragraph type="secondary">
        每 3
        小时采集一次启用店铺的公开商品列表，按标题自动归到标准商品。采集失败只记在店铺上，不影响已有报价；
        多商户平台（ShopApi）要填具体商户的店铺地址才能采集。
      </Typography.Paragraph>
      <Space wrap style={{ marginBottom: 16 }}>
        <Segmented value={state} options={STATE_OPTIONS} onChange={(v) => update({ state: v })} />
        <Select
          allowClear
          placeholder="全部店铺系统"
          style={{ width: 180 }}
          value={kind}
          options={KIND_OPTIONS}
          onChange={(v?: ShopCollectorKind) => update({ kind: v })}
        />
        <Input.Search
          allowClear
          placeholder="搜索域名或备注"
          defaultValue={q}
          style={{ width: 220 }}
          onSearch={(v) => update({ q: v.trim() })}
        />
      </Space>

      {sources.isError ? (
        <Alert
          type="error"
          showIcon
          title="店铺列表加载失败"
          description={sources.error.message}
          action={<Button onClick={() => void sources.refetch()}>重试</Button>}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={sources.data?.items ?? []}
          loading={sources.isFetching}
          scroll={{ x: 900 }}
          locale={{ emptyText: "没有符合条件的店铺" }}
          pagination={{
            current: page,
            pageSize,
            total: sources.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 家`,
            onChange: (p, size) => update({ page: String(p), size: String(size) }),
          }}
        />
      )}

      <ShopSourceModal
        open={editing !== undefined}
        source={editing ?? null}
        onClose={() => setEditing(undefined)}
      />
    </Card>
  );
}
