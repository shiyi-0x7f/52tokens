import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  Modal,
  Popconfirm,
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

import { DEAL_STATUS, DEAL_TYPE_LABELS } from "../api/labels";
import { type DealAction, useDealAction, useDeals, usePlatforms } from "../api/queries";
import type { Deal, DealStatus } from "../api/types";
import { WEB_ORIGIN } from "../lib/env";
import { formatDateTime, fromNow } from "../lib/format";
import { useErrorNotice } from "../lib/useErrorNotice";
import { DealFormDrawer } from "./DealFormDrawer";

type StatusFilter = DealStatus | "all";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  ...(Object.keys(DEAL_STATUS) as DealStatus[]).map((value) => ({
    value,
    label: DEAL_STATUS[value].label,
  })),
  { value: "all", label: "全部" },
];

const ACTION_DONE: Record<DealAction, string> = {
  publish: "已发布",
  expire: "已标记结束",
  reconfirm: "已更新核实时间",
  reject: "已驳回",
};

export function DealsPage() {
  // 筛选和分页放在网址里：刷新、分享都能保持
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") ?? "pending") as StatusFilter;
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
    if (!("page" in patch)) next.delete("page"); // 改筛选回到第一页
    setParams(next, { replace: true });
  };

  const deals = useDeals({
    status: status === "all" ? undefined : status,
    platform_id: platformId,
    q,
    page,
    page_size: pageSize,
  });
  const platforms = usePlatforms();
  const action = useDealAction();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();

  const [editing, setEditing] = useState<Deal | null | undefined>(undefined);
  const [rejecting, setRejecting] = useState<Deal | null>(null);
  const [reason, setReason] = useState("");

  const run = (deal: Deal, act: DealAction, extra: { reason?: string } = {}) => {
    action.mutate(
      { id: deal.id, action: act, ...extra },
      {
        onSuccess: () => {
          message.success(`${ACTION_DONE[act]}：${deal.title}`);
          setRejecting(null);
        },
        onError: (err) => notifyError(`操作失败：${deal.title}`, err),
      },
    );
  };

  const columns: ColumnsType<Deal> = [
    {
      title: "活动",
      key: "title",
      render: (_, d) => (
        <Space orientation="vertical" size={0}>
          <Space size={4}>
            <Typography.Text strong>{d.title}</Typography.Text>
            {d.origin === "collector" && (
              <Tooltip title={d.extract_note ? `原文：${d.extract_note}` : "自动采集"}>
                <Tag color="purple">
                  采集
                  {d.extract_confidence !== null &&
                    ` ${Math.round(Number(d.extract_confidence) * 100)}%`}
                </Tag>
              </Tooltip>
            )}
          </Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {d.reward_text} · {d.slug}
          </Typography.Text>
        </Space>
      ),
    },
    { title: "平台", key: "platform", width: 140, render: (_, d) => d.platform.name },
    {
      title: "类型",
      dataIndex: "deal_type",
      width: 90,
      render: (t: Deal["deal_type"]) => <Tag>{DEAL_TYPE_LABELS[t]}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (s: DealStatus, d) => {
        const tag = <Tag color={DEAL_STATUS[s].color}>{DEAL_STATUS[s].label}</Tag>;
        if (s === "rejected" && d.reject_reason) {
          return <Tooltip title={`驳回原因：${d.reject_reason}`}>{tag}</Tooltip>;
        }
        if (s === "expired" && d.liveness_issue) {
          return <Tooltip title={`自动标记结束：${d.liveness_issue}`}>{tag}</Tooltip>;
        }
        if (s === "active" && d.liveness_issue) {
          // 存活检查发现下线信号，连续 3 次会自动结束；人工「重新核实」可清除
          return (
            <Space size={2} wrap>
              {tag}
              <Tooltip
                title={`${d.liveness_issue}；连续 3 次会自动标记结束，确认还在就点「重新核实」`}
              >
                <Tag color="orange">疑似下线 {d.liveness_fail_count}/3</Tag>
              </Tooltip>
            </Space>
          );
        }
        return tag;
      },
    },
    {
      title: "核实",
      dataIndex: "confirmed_at",
      width: 120,
      render: (v: string | null) => <Tooltip title={formatDateTime(v)}>{fromNow(v)}</Tooltip>,
    },
    {
      title: "截止",
      dataIndex: "ends_at",
      width: 150,
      render: (v: string | null) => formatDateTime(v),
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 260,
      render: (_, d) => (
        <Space size={4} wrap>
          <Button size="small" onClick={() => setEditing(d)}>
            编辑
          </Button>
          {(d.status === "pending" || d.status === "rejected") && (
            <Button size="small" type="primary" onClick={() => run(d, "publish")}>
              核实并发布
            </Button>
          )}
          {d.status === "pending" && (
            <Button
              size="small"
              danger
              onClick={() => {
                setReason("");
                setRejecting(d);
              }}
            >
              驳回
            </Button>
          )}
          {d.status === "active" && (
            <>
              <Button size="small" onClick={() => run(d, "reconfirm")}>
                重新核实
              </Button>
              <Popconfirm
                title="标记为已结束？"
                description="页面会保留，并下沉到「已结束」。"
                onConfirm={() => run(d, "expire")}
              >
                <Button size="small">标记结束</Button>
              </Popconfirm>
            </>
          )}
          <Button size="small" type="link" href={d.source_url} target="_blank" rel="noopener">
            原文
          </Button>
          {(d.status === "active" || d.status === "expired") && (
            <Button
              size="small"
              type="link"
              href={`${WEB_ORIGIN}/deals/${d.slug}`}
              target="_blank"
              rel="noopener"
            >
              页面
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="活动审核"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing(null)}>
          新建活动
        </Button>
      }
    >
      <Space wrap style={{ marginBottom: 16 }}>
        <Segmented
          value={status}
          options={STATUS_OPTIONS}
          onChange={(value) => update({ status: value })}
        />
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
        <Input.Search
          allowClear
          placeholder="搜索标题或 slug"
          defaultValue={q}
          style={{ width: 240 }}
          onSearch={(value) => update({ q: value.trim() })}
        />
      </Space>

      {deals.isError ? (
        <Alert
          type="error"
          showIcon
          title="活动列表加载失败"
          description={deals.error.message}
          action={<Button onClick={() => void deals.refetch()}>重试</Button>}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={deals.data?.items ?? []}
          loading={deals.isFetching}
          scroll={{ x: 1100 }}
          locale={{ emptyText: status === "pending" ? "没有待审核的活动" : "没有活动" }}
          pagination={{
            current: page,
            pageSize,
            total: deals.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (p, size) => update({ page: String(p), size: String(size) }),
          }}
        />
      )}

      <DealFormDrawer
        open={editing !== undefined}
        deal={editing ?? null}
        onClose={() => setEditing(undefined)}
      />

      <Modal
        title={`驳回：${rejecting?.title ?? ""}`}
        open={rejecting !== null}
        okText="驳回"
        okButtonProps={{ danger: true, disabled: !reason.trim(), loading: action.isPending }}
        onOk={() => rejecting && run(rejecting, "reject", { reason: reason.trim() })}
        onCancel={() => setRejecting(null)}
      >
        <Input.TextArea
          rows={3}
          maxLength={200}
          showCount
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="驳回原因（必填），例如：官网找不到这个活动"
        />
      </Modal>
    </Card>
  );
}
