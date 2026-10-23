import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";

import { ApiError } from "./api/client";
import { AdminLayout } from "./layout/AdminLayout";
import { DealsPage } from "./pages/DealsPage";
import { PricesPage } from "./pages/PricesPage";

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
        { path: "*", element: <Navigate to="/deals" replace /> },
      ],
    },
  ],
  { basename: "/admin" },
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
