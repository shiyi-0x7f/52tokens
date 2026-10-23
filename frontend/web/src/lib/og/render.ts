/** 分享图渲染：卡片 → satori（SVG）→ resvg（PNG）。服务端专用。 */
import { Resvg } from "@resvg/resvg-js";
import { createElement } from "react";
import satori from "satori";

// 字体以 data URL 打进服务端产物，不依赖部署后的文件路径；子集只含 GB2312 + ASCII，
// 生僻字会显示为空白（来源与裁剪方式见 assets/fonts/README.md）
import fontDataUrl from "../../assets/fonts/NotoSansSC-Bold-subset.otf?inline";
import type { OgCard } from "./cards";
import { OG_HEIGHT, OG_WIDTH, OgImage } from "./OgImage";

let font: Buffer | undefined;

function fontData(): Buffer {
  font ??= Buffer.from(fontDataUrl.slice(fontDataUrl.indexOf(",") + 1), "base64");
  return font;
}

export async function renderOgPng(card: OgCard): Promise<Uint8Array> {
  const svg = await satori(createElement(OgImage, { card }), {
    width: OG_WIDTH,
    height: OG_HEIGHT,
    fonts: [{ name: "Noto Sans SC", data: fontData(), weight: 700, style: "normal" }],
  });
  return new Resvg(svg, { fitTo: { mode: "width", value: OG_WIDTH } }).render().asPng();
}

export async function ogResponse(card: OgCard): Promise<Response> {
  // 拷贝成独立 ArrayBuffer 的 Uint8Array，才符合 Response 的 BodyInit 类型
  const png = new Uint8Array(await renderOgPng(card));
  return new Response(png, {
    headers: {
      "Content-Type": "image/png",
      // 渲染有开销：浏览器缓存 1 小时，CDN 缓存 1 天；内容更新靠页面引用时带的 ?v= 刷新
      "Cache-Control": "public, max-age=3600, s-maxage=86400",
    },
  });
}
