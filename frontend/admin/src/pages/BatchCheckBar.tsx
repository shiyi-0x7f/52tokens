import { useQueryClient } from "@tanstack/react-query";
import { Alert, App, Button, Progress, Space, Typography } from "antd";
import { useEffect, useRef } from "react";

import { useBatchStatus, useStartBatch } from "../api/queries";
import type { BatchStatus } from "../api/types";
import { formatDateTime, fromNow } from "../lib/format";
import { useErrorNotice } from "../lib/useErrorNotice";

function summaryText(last: NonNullable<BatchStatus["last"]>): string {
  return (
    `检查 ${last.checked} 个页面，新增 ${last.created} 条待审核，` +
    `刷新核实 ${last.reconfirmed} 条，失败 ${last.failed} 个`
  );
}

/** 「全部检查」：后端在后台逐个检查启用的来源，这里轮询进度，跑完刷新列表并提示结果 */
export function BatchCheckBar() {
  const status = useBatchStatus();
  const start = useStartBatch();
  const client = useQueryClient();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();

  const running = status.data?.running ?? null;
  const last = status.data?.last ?? null;
  const wasRunning = useRef(false);

  useEffect(() => {
    if (wasRunning.current && !running) {
      void client.invalidateQueries({ queryKey: ["sources"] });
      void client.invalidateQueries({ queryKey: ["deals"] });
      if (last) message.success(`全部检查完成：${summaryText(last)}`);
    }
    wasRunning.current = running !== null;
  }, [running, last, client, message]);

  const onStart = () =>
    start.mutate(undefined, { onError: (err) => notifyError("启动全部检查失败", err) });

  if (status.isError) {
    return (
      <Alert
        type="error"
        showIcon
        title="批量检查状态加载失败"
        description={status.error.message}
        action={<Button onClick={() => void status.refetch()}>重试</Button>}
        style={{ marginBottom: 16 }}
      />
    );
  }

  return (
    <Space wrap style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }}>
      {running ? (
        <Space>
          <Typography.Text>
            正在检查 {running.done}/{running.total || "…"}
          </Typography.Text>
          <Progress
            percent={running.total ? Math.round((running.done / running.total) * 100) : 0}
            size="small"
            style={{ width: 200, margin: 0 }}
          />
        </Space>
      ) : (
        <Typography.Text type="secondary">
          {last ? (
            <span title={formatDateTime(last.finished_at)}>
              上次全部检查：{fromNow(last.finished_at)}，{summaryText(last)}
            </span>
          ) : (
            "还没有跑过全部检查"
          )}
        </Typography.Text>
      )}
      <Button
        type="primary"
        loading={start.isPending || running !== null}
        disabled={status.isPending}
        onClick={onStart}
      >
        {running ? "检查中" : "全部检查"}
      </Button>
    </Space>
  );
}
