/** 公开站地址：生产与后台同域（空字符串）；dev 下端口不同，由 vite 注入 */
export const WEB_ORIGIN: string = import.meta.env["VITE_WEB_ORIGIN"] ?? "";
