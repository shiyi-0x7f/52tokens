import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { useComparisons, useComparisonVisibility, useDeleteComparison } from "../api/queries";
import type { ModelComparison } from "../api/types";
import { WEB_ORIGIN } from "../lib/env";
import { formatDateTime, fromNow } from "../lib/format";
import { useErrorNotice } from "../lib/useErrorNotice";
import { ComparisonFormModal } from "./ComparisonFormModal";

const vsUrl = (c: ModelComparison) => `${WEB_ORIGIN}/models/${c.model_a.slug}-vs-${c.model_b.slug}`;

export function ComparisonsPage() {
  const [params, setParams] = useSearchParams();
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

  const comparisons = useComparisons({ q, page, page_size: pageSize });
  const visibility = useComparisonVisibility();
  const remove = useDeleteComparison();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();
  const [editing, setEditing] = useState<ModelComparison | null | undefined>(undefined);

  const toggle = (c: ModelComparison) => {
    const visible = c.status !== "active";
    visibility.mutate(
      { id: c.id, visible },
      {
        onSuccess: () =>
          message.success(visible ? "已恢复收录" : "已隐藏，页面改为不让搜索引擎收录"),
        onError: (err) => notifyError("操作失败", err),
      },
    );
  };

  const columns: ColumnsType<ModelComparison> = [
    {
      title: "对比",
      key: "pair",
      render: (_, c) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>
            {c.model_a.name} vs {c.model_b.name}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {c.model_a.slug}-vs-{c.model_b.slug}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: "导语",
      dataIndex: "intro",
      ellipsis: true,
      render: (v: string) => v || <Typography.Text type="secondary">—</Typography.Text>,
    },
    { title: "排序", dataIndex: "sort_order", width: 70 },
    {
      title: "更新",
      dataIndex: "updated_at",
      width: 110,
      render: (v: string) => <Tooltip title={formatDateTime(v)}>{fromNow(v)}</Tooltip>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (s: ModelComparison["status"]) =>
        s === "active" ? <Tag color="green">收录中</Tag> : <Tag>已隐藏</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 240,
      render: (_, c) => (
        <Space size={4}>
          <Button size="small" onClick={() => setEditing(c)}>
            编辑
          </Button>
          <Button size="small" onClick={() => toggle(c)}>
            {c.status === "active" ? "隐藏" : "恢复"}
          </Button>
          <Popconfirm
            title="删除这组对比？"
            description="页面仍能打开，但不再被搜索引擎收录。"
            onConfirm={() =>
              remove.mutate(c.id, {
                onSuccess: () => message.success("已删除"),
                onError: (err) => notifyError("删除失败", err),
              })
            }
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
          <Button size="small" type="link" href={vsUrl(c)} target="_blank" rel="noopener">
            查看
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="精选对比"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing(null)}>
          收录对比
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        收录的组合会生成可被搜索引擎收录的 /models/A-vs-B 页面并进
        sitemap；未收录的组合页面也能打开，但不让收录。
      </Typography.Paragraph>
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="搜索模型名或 slug"
          defaultValue={q}
          style={{ width: 240 }}
          onSearch={(value) => update({ q: value.trim() })}
        />
      </Space>
      {comparisons.isError ? (
        <Alert
          type="error"
          showIcon
          title="对比列表加载失败"
          description={comparisons.error.message}
          action={<Button onClick={() => void comparisons.refetch()}>重试</Button>}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={comparisons.data?.items ?? []}
          loading={comparisons.isFetching}
          scroll={{ x: 900 }}
          pagination={{
            current: page,
            pageSize,
            total: comparisons.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 组`,
            onChange: (p, size) => update({ page: String(p), size: String(size) }),
          }}
        />
      )}
      <ComparisonFormModal
        open={editing !== undefined}
        comparison={editing ?? null}
        onClose={() => setEditing(undefined)}
      />
    </Card>
  );
}
