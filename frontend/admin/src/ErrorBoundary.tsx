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
      <div role="alert" className="m-6 rounded-xl border border-hot bg-card p-5">
        <div className="mb-3 flex items-center gap-3">
          <strong className="text-hot">页面出错了</strong>
          <button
            type="button"
            className="ml-auto min-h-9 rounded-lg bg-ink px-3 text-sm text-white"
            onClick={() => void navigator.clipboard.writeText(text)}
          >
            复制错误
          </button>
        </div>
        <pre className="overflow-auto font-mono text-xs whitespace-pre-wrap">{text}</pre>
      </div>
    );
  }
}
