/**
 * 点击即反馈：带 data-pending-text 的链接 / 提交按钮，点下去立刻进入加载态
 * （换文案 + 转圈 + 禁止重复点击），不用等服务端返回才有变化。
 *
 * - 表单带 data-require-turnstile 时，人机验证没完成就不提交，并提示用户。
 * - 浏览器后退回到页面（bfcache）时恢复原状。
 */

const BUSY = "aria-busy";

export function setPending(el: HTMLElement): boolean {
  const text = el.dataset["pendingText"];
  if (!text || el.getAttribute(BUSY) === "true") return false;
  el.dataset["idleText"] = el.textContent ?? "";
  el.textContent = text;
  el.setAttribute(BUSY, "true");
  el.setAttribute("aria-disabled", "true");
  if (el instanceof HTMLButtonElement) el.disabled = true;
  return true;
}

export function clearPending(el: HTMLElement): void {
  if (el.getAttribute(BUSY) !== "true") return;
  el.textContent = el.dataset["idleText"] ?? el.textContent;
  el.removeAttribute(BUSY);
  el.removeAttribute("aria-disabled");
  if (el instanceof HTMLButtonElement) el.disabled = false;
}

function isPlainLeftClick(event: MouseEvent): boolean {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

document.addEventListener("click", (event) => {
  const link = (event.target as Element | null)?.closest<HTMLAnchorElement>("a[data-pending-text]");
  if (!link || event.defaultPrevented || !isPlainLeftClick(event)) return;
  if (link.getAttribute(BUSY) === "true") {
    event.preventDefault(); // 已经在跳转了，忽略重复点击
    return;
  }
  setPending(link);
});

document.addEventListener("submit", (event) => {
  const form = event.target as HTMLFormElement;
  const button = form.querySelector<HTMLButtonElement>("button[type=submit][data-pending-text]");
  if (!button) return;
  if (button.getAttribute(BUSY) === "true") {
    event.preventDefault();
    return;
  }
  if (form.dataset["requireTurnstile"] !== undefined) {
    const token = form.querySelector<HTMLInputElement>("[name='cf-turnstile-response']")?.value;
    if (!token) {
      event.preventDefault();
      form.querySelector<HTMLElement>("[data-turnstile-hint]")?.classList.remove("hidden");
      return;
    }
  }
  setPending(button);
});

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  document.querySelectorAll<HTMLElement>(`[${BUSY}="true"]`).forEach(clearPending);
});
