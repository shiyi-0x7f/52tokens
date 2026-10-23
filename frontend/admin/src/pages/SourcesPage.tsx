import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Popconfirm,
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

import { useCheckSource, useDeleteSource, usePlatforms, useSources } from "../api/queries";
import type { CheckReport, Source } from "../api/types";
import { formatDateTime, fromNow } from "../lib/format";
import { useErrorNotice } from "../lib/useErrorNotice";
import { BatchCheckBar } from "./BatchCheckBar";
import { SourceFormModal } from "./SourceFormModal";

function reportText(report: CheckReport): string {
  if (report.status === "unchanged") return "页面没有变化";
  if (report.status === "failed") return `检查失败：${report.error}`;
  return `抽取完成：新增 ${report.created} 条待审核，刷新核实 ${report.reconfirmed} 条`;
}

function StatusCell({ source }: { source: Source }) {
  if (!source.checked_at) return <Tag>未检查</Tag>;
  if (source.last_error) {
    return (
      <Tooltip title={source.last_error}>
        <Tag color="red">失败 {source.fail_count} 次</Tag>
      </Tooltip>
    );
  }
  return <Tag color="green">正常</Tag>;
}

export function SourcesPage() {
  const [params, setParams] = useSearchParams();
  const platformId = params.get("platform") ? Number(params.get("platform")) : undefined;
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

  const sources = useSources({ platform_id: platformId, page, page_size: pageSize });
  const platforms = usePlatforms();
  const check = useCheckSource();
  const remove = useDeleteSource();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();

  const [editing, setEditing] = useState<Source | null | undefined>(undefined);
  const [checkingId, setCheckingId] = useState<number | null>(null);

  const runCheck = (source: Source) => {
    setCheckingId(source.id);
    check.mutate(source.id, {
      onSuccess: (report) => {
        const text = reportText(report);
        if (report.status === "failed") message.warning(text);
        else message.success(text);
      },
      onError: (err) => notifyError(`检查失败：${source.url}`, err),
      onSettled: () => setCheckingId(null),
    });
  };

  const columns: ColumnsType<Source> = [
    {
      title: "页面",
      key: "url",
      render: (_, s) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link href={s.url} target="_blank" rel="noopener" ellipsis>
            {s.url}
          </Typography.Link>
          {s.label && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {s.label}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    { title: "平台", key: "platform", width: 140, render: (_, s) => s.platform.name },
    {
      title: "定时检查",
      dataIndex: "enabled",
      width: 90,
      render: (v: boolean) => (v ? <Tag color="blue">开</Tag> : <Tag>关</Tag>),
    },
    { title: "状态", key: "status", width: 110, render: (_, s) => <StatusCell source={s} /> },
    {
      title: "上次检查",
      dataIndex: "checked_at",
      width: 110,
      render: (v: string | null) => <Tooltip title={formatDateTime(v)}>{fromNow(v)}</Tooltip>,
    },
    {
      title: "上次变化",
      dataIndex: "changed_at",
      width: 110,
      render: (v: string | null) => <Tooltip title={formatDateTime(v)}>{fromNow(v)}</Tooltip>,
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 220,
      render: (_, s) => (
        <Space size={4}>
          <Button
            size="small"
            type="primary"
            loading={checkingId === s.id}
            disabled={checkingId !== null && checkingId !== s.id}
            onClick={() => runCheck(s)}
          >
            立即检查
          </Button>
          <Button size="small" onClick={() => setEditing(s)}>
            编辑
          </Button>
          <Popconfirm
            title="删除这个监测来源？"
            description="已采集到的活动会保留。"
            onConfirm={() =>
              remove.mutate(s.id, {
                onSuccess: () => message.success("已删除"),
                onError: (err) => notifyError("删除失败", err),
              })
            }
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="监测来源"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing(null)}>
          添加来源
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        每 6 小时抓取一次启用的页面，正文有变化才交给 LLM
        抽取活动；新活动进「活动审核」的待审核列表。
      </Typography.Paragraph>
      <BatchCheckBar />
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="全部平台"
          style={{ width: 180 }}
          value={platformId}
          loading={platforms.isPending}
          options={(platforms.data ?? []).map((p) => ({ value: p.id, label: p.name }))}
          onChange={(value?: number) => update({ platform: value ? String(value) : undefined })}
        />
      </Space>

      {sources.isError ? (
        <Alert
          type="error"
          showIcon
          title="监测来源加载失败"
          description={sources.error.message}
          action={<Button onClick={() => void sources.refetch()}>重试</Button>}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={sources.data?.items ?? []}
          loading={sources.isFetching}
          scroll={{ x: 1000 }}
          locale={{ emptyText: "还没有监测来源，点右上角添加" }}
          pagination={{
            current: page,
            pageSize,
            total: sources.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (p, size) => update({ page: String(p), size: String(size) }),
          }}
        />
      )}

      <SourceFormModal
        open={editing !== undefined}
        source={editing ?? null}
        onClose={() => setEditing(undefined)}
      />
    </Card>
  );
}
