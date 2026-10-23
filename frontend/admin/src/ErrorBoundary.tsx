import { Button, Result, Typography } from "antd";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  error: Error | null;
  stack: string;
}

/** 渲染错误不吞：显示可见、可复制的错误详情（dev 带完整堆栈） */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  override state: State = { error: null, stack: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(error, info.componentStack);
    this.setState({ stack: `${error.stack ?? error.message}\n${info.componentStack ?? ""}` });
  }

  override render(): ReactNode {
    const { error, stack } = this.state;
    if (!error) return this.props.children;
    const text = import.meta.env.DEV ? stack || error.message : error.message;
    return (
      <Result
        status="error"
        title="页面出错了"
        subTitle={error.message}
        extra={[
          <Button key="copy" onClick={() => void navigator.clipboard.writeText(text)}>
            复制错误
          </Button>,
          <Button key="reload" type="primary" onClick={() => window.location.reload()}>
            刷新页面
          </Button>,
        ]}
      >
        {import.meta.env.DEV && (
          <Typography.Paragraph>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{stack}</pre>
          </Typography.Paragraph>
        )}
      </Result>
    );
  }
}
