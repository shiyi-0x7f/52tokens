/**
 * 分享图模板（1200×630），由 satori 渲染成 SVG，只支持 flex 布局和内联样式。
 * 颜色与 global.css 的设计令牌保持一致。
 */
import type { OgCard } from "./cards";

const COLORS = {
  bg: "#f6f6f8",
  card: "#ffffff",
  ink: "#18181b",
  sub: "#52525b",
  mute: "#71717a",
  line: "#ececf0",
  hot: "#e11d2e",
};

/** 标题过长时截断，避免溢出卡片（satori 不支持多行省略） */
function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export const OG_WIDTH = 1200;
export const OG_HEIGHT = 630;

export function OgImage({ card }: { card: OgCard }) {
  return (
    <div
      style={{
        // 用像素而不是 100%：百分比宽高加内边距会把内容撑出画布
        width: OG_WIDTH,
        height: OG_HEIGHT,
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        background: COLORS.bg,
        padding: 48,
        fontFamily: "Noto Sans SC",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 30,
          color: COLORS.ink,
        }}
      >
        <div style={{ display: "flex" }}>
          52<span style={{ color: COLORS.hot }}>tokens</span>
        </div>
        <div style={{ fontSize: 24, color: COLORS.mute }}>AI 羊毛热榜</div>
      </div>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          marginTop: 28,
          padding: "44px 52px",
          background: COLORS.card,
          borderRadius: 24,
          borderTop: `10px solid ${COLORS.hot}`,
        }}
      >
        <div style={{ fontSize: 30, color: COLORS.mute }}>{clip(card.eyebrow, 30)}</div>
        <div
          style={{
            marginTop: 16,
            fontSize: card.title.length > 16 ? 56 : 68,
            lineHeight: 1.2,
            color: COLORS.ink,
          }}
        >
          {clip(card.title, 36)}
        </div>
        {card.highlight && (
          <div style={{ marginTop: 24, fontSize: 52, color: COLORS.hot }}>
            {clip(card.highlight, 28)}
          </div>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          {card.tags.map((tag) => (
            <div
              key={tag}
              style={{
                fontSize: 24,
                color: COLORS.sub,
                background: COLORS.bg,
                border: `2px solid ${COLORS.line}`,
                borderRadius: 999,
                padding: "6px 18px",
              }}
            >
              {clip(tag, 16)}
            </div>
          ))}
          {card.note && (
            <div style={{ fontSize: 26, color: COLORS.mute }}>{clip(card.note, 40)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
