import pino from "pino";

const isDev = import.meta.env.DEV;
const level = process.env["LOG_LEVEL"]?.toLowerCase() ?? (isDev ? "debug" : "info");

// dev 用同进程的 pino-pretty 流（Vite SSR 下 worker 线程 transport 无法解析模块）；
// prod 直接输出结构化 JSON 到 stdout
const stream = isDev ? (await import("pino-pretty")).default({ colorize: true }) : undefined;

export const logger = stream ? pino({ level }, stream) : pino({ level });
