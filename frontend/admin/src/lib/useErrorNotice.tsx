import { App, Button, Typography } from "antd";
import { useCallback } from "react";

import { ApiError } from "../api/client";

function detailText(err: unknown): string {
  if (err instanceof ApiError) {
    const lines = [`HTTP ${err.status} · 业务码 ${err.code}`, err.message];
    if (err.detail !== null) lines.push(JSON.stringify(err.detail, null, 2));
    if (import.meta.env.DEV && err.stack) lines.push(err.stack);
    return lines.join("\n");
  }
  if (err instanceof Error) return import.meta.env.DEV ? (err.stack ?? err.message) : err.message;
  return String(err);
}

/** 接口报错：常驻通知（不自动消失）+ 可复制的详情，dev 下附完整堆栈 */
export function useErrorNotice() {
  const { notification } = App.useApp();
  return useCallback(
    (title: string, err: unknown) => {
      const text = detailText(err);
      console.error(title, err);
      notification.error({
        title,
        description: (
          <div>
            <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 8 }}>
              {err instanceof Error ? err.message : String(err)}
            </Typography.Paragraph>
            <Button size="small" onClick={() => void navigator.clipboard.writeText(text)}>
              复制错误详情
            </Button>
          </div>
        ),
        duration: 0,
      });
    },
    [notification],
  );
}
