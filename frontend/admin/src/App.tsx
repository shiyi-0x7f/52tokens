import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";

import { ApiError } from "./api/client";
import { AdminLayout } from "./layout/AdminLayout";
import { ComparisonsPage } from "./pages/ComparisonsPage";
import { DealsPage } from "./pages/DealsPage";
import { PricesPage } from "./pages/PricesPage";
import { ShopSourcesPage } from "./pages/ShopSourcesPage";
import { SourcesPage } from "./pages/SourcesPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // 未登录 / 无权限不重试，其余失败重试一次
      retry: (count, err) =>
        !(err instanceof ApiError && [401, 403, 404].includes(err.status)) && count < 1,
      refetchOnWindowFocus: false,
    },
  },
});

const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <AdminLayout />,
      children: [
        { index: true, element: <Navigate to="/deals" replace /> },
        { path: "deals", element: <DealsPage /> },
        { path: "prices", element: <PricesPage /> },
        { path: "comparisons", element: <ComparisonsPage /> },
        { path: "sources", element: <SourcesPage /> },
        { path: "shops", element: <ShopSourcesPage /> },
        { path: "*", element: <Navigate to="/deals" replace /> },
      ],
    },
  ],
  // 路由前缀跟随部署路径（开发 /admin/，生产由容器启动时替换），去掉末尾斜杠
  { basename: import.meta.env.BASE_URL.replace(/\/$/, "") },
);

// 主题与公开站一致：品牌红、10px 圆角
const THEME = { token: { colorPrimary: "#e11d2e", borderRadius: 10 } };

export function App() {
  return (
    <ConfigProvider locale={zhCN} theme={THEME}>
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  );
}
