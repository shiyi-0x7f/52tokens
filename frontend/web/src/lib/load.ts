import { logger } from "./logger";

/** 列表类数据加载失败时降级为空并记日志，页面照常渲染并提示，而不是整页 500 */
export async function loadOr<T>(fallback: T, load: () => Promise<T>): Promise<[T, boolean]> {
  try {
    return [await load(), true];
  } catch (err) {
    logger.error({ err }, "page data load failed");
    return [fallback, false];
  }
}
