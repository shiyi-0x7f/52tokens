import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Input,
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

import { usePlatforms, usePriceVisibility, usePrices } from "../api/queries";
import type { Price } from "../api/types";
import { formatDateTime, formatPrice, fromNow } from "../lib/format";
import { useErrorNotice } from "../lib/useErrorNotice";
import { PriceFormDrawer } from "./PriceFormDrawer";

export function PricesPage() {
  const [params, setParams] = useSearchParams();
  const platformId = params.get("platform") ? Number(params.get("platform")) : undefined;
  const q = params.get("q") ?? undefined;
  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("size") ?? 20);

  const update = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === undefined || value === "") next.delete(key);
      else next.set(key, value);
    }
    if (!("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };

  const prices = usePrices({ platform_id: platformId, q, page, page_size: pageSize });
  const platforms = usePlatforms();
  const visibility = usePriceVisibility();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();
  const [editing, setEditing] = useState<Price | null | undefined>(undefined);

  const toggle = (p: Price) => {
    const visible = p.status !== "active";
    visibility.mutate(
      { id: p.id, visible },
      {
        onSuccess: () => message.success(`${visible ? "已恢复" : "已隐藏"}：${p.model.name}`),
        onError: (err) => notifyError("操作失败", err),
      },
    );
  };

  const columns: ColumnsType<Price> = [
    {
      title: "模型",
      key: "model",
      render: (_, p) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>{p.model.name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {p.model.slug}
          </Typography.Text>
        </Space>
      ),
    },
    { title: "平台", key: "platform", width: 150, render: (_, p) => p.platform.name },
    {
      title: "输入 / 输出（每百万）",
      key: "price",
      width: 190,
      render: (_, p) =>
        p.is_free && p.output_price === null ? (
          <Tag color="green">免费</Tag>
        ) : (
          <Typography.Text style={{ fontFamily: "monospace" }}>
            {formatPrice(p.input_price, p.currency)} / {formatPrice(p.output_price, p.currency)}
            {p.is_free && (
              <Tag color="green" style={{ marginLeft: 6 }}>
                有免费版
              </Tag>
            )}
          </Typography.Text>
        ),
    },
    {
      title: "核实",
      dataIndex: "confirmed_at",
      width: 120,
      render: (v: string | null) => <Tooltip title={formatDateTime(v)}>{fromNow(v)}</Tooltip>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (s: Price["status"]) =>
        s === "active" ? <Tag color="green">展示中</Tag> : <Tag>已隐藏</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 200,
      render: (_, p) => (
        <Space size={4}>
          <Button size="small" onClick={() => setEditing(p)}>
            更新
          </Button>
          <Button size="small" onClick={() => toggle(p)}>
            {p.status === "active" ? "隐藏" : "恢复"}
          </Button>
          <Button size="small" type="link" href={p.source_url} target="_blank" rel="noopener">
            出处
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="价格录入"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing(null)}>
          录入价格
        </Button>
      }
    >
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="全部平台"
          style={{ width: 200 }}
          value={platformId}
          loading={platforms.isPending}
          options={(platforms.data ?? []).map((p) => ({ value: p.id, label: p.name }))}
          onChange={(value?: number) => update({ platform: value ? String(value) : undefined })}
        />
        <Input.Search
          allowClear
          placeholder="搜索模型名或 slug"
          defaultValue={q}
          style={{ width: 240 }}
          onSearch={(value) => update({ q: value.trim() })}
        />
      </Space>
      {prices.isError ? (
        <Alert
          type="error"
          showIcon
          title="价格列表加载失败"
          description={prices.error.message}
          action={<Button onClick={() => void prices.refetch()}>重试</Button>}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={prices.data?.items ?? []}
          loading={prices.isFetching}
          scroll={{ x: 900 }}
          pagination={{
            current: page,
            pageSize,
            total: prices.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (p, size) => update({ page: String(p), size: String(size) }),
          }}
        />
      )}
      <PriceFormDrawer
        open={editing !== undefined}
        price={editing ?? null}
        onClose={() => setEditing(undefined)}
      />
    </Card>
  );
}
