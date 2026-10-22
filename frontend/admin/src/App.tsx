export function App() {
  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6 flex items-center gap-3">
        <span className="text-xl font-black">
          52<span className="text-hot">tokens</span>
        </span>
        <span className="text-sm text-mute">后台</span>
      </header>
      <section className="rounded-2xl bg-card p-6 text-sm text-sub">
        后台骨架。登录接入 SCC 统一身份后，这里放来源审核、活动审核、采集日志等页面。
      </section>
    </div>
  );
}
