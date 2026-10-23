import { DollarOutlined, GiftOutlined, RadarChartOutlined, ShopOutlined } from "@ant-design/icons";
import { Avatar, Button, Layout, Menu, Result, Space, Spin, Typography } from "antd";
import { NavLink, Outlet, useLocation } from "react-router";

import { ApiError } from "../api/client";
import { useMe } from "../api/queries";
import { WEB_ORIGIN } from "../lib/env";

// 登录在公开站完成（会话 Cookie 同域共享）；dev 下公开站和后台端口不同，新窗口打开登录页
const LOGIN_URL = WEB_ORIGIN ? `${WEB_ORIGIN}/login` : "/login?next=%2Fadmin%2F";

const MENU = [
  { key: "/deals", icon: <GiftOutlined />, label: <NavLink to="/deals">活动审核</NavLink> },
  { key: "/prices", icon: <DollarOutlined />, label: <NavLink to="/prices">价格录入</NavLink> },
  {
    key: "/sources",
    icon: <RadarChartOutlined />,
    label: <NavLink to="/sources">监测来源</NavLink>,
  },
  { key: "/shops", icon: <ShopOutlined />, label: <NavLink to="/shops">卡网店铺</NavLink> },
];

function AuthGate({ status }: { status: number }) {
  if (status === 403) {
    return (
      <Result
        status="403"
        title="需要管理员账号"
        subTitle="当前登录的账号不是管理员。管理员邮箱在后端 ADMIN_EMAILS 中配置，需用已验证的邮箱登录。"
      />
    );
  }
  return (
    <Result
      status="info"
      title="请先登录"
      subTitle="后台和公开站共用登录状态。登录完成后回到这里刷新即可。"
      extra={
        <Space>
          <Button type="primary" href={LOGIN_URL} target={WEB_ORIGIN ? "_blank" : undefined}>
            去登录
          </Button>
          <Button onClick={() => window.location.reload()}>我已登录，刷新</Button>
        </Space>
      }
    />
  );
}

export function AdminLayout() {
  const me = useMe();
  const { pathname } = useLocation();

  if (me.isPending) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }
  if (me.isError) {
    const status = me.error instanceof ApiError ? me.error.status : 0;
    if (status === 401 || status === 403) return <AuthGate status={status} />;
    return (
      <Result
        status="error"
        title="后台接口不可用"
        subTitle={me.error instanceof Error ? me.error.message : String(me.error)}
        extra={<Button onClick={() => void me.refetch()}>重试</Button>}
      />
    );
  }

  const selected = MENU.find((m) => pathname.startsWith(m.key))?.key ?? "/deals";
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider breakpoint="lg" collapsedWidth={0} theme="light" width={200}>
        <div style={{ padding: "18px 24px", fontSize: 18, fontWeight: 900 }}>
          52<span style={{ color: "#e11d2e" }}>tokens</span>
          <Typography.Text type="secondary" style={{ marginLeft: 6, fontSize: 12 }}>
            后台
          </Typography.Text>
        </div>
        <Menu mode="inline" selectedKeys={[selected]} items={MENU} />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            background: "#fff",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            paddingInline: 24,
          }}
        >
          <Space>
            {me.data.avatar_url ? (
              <Avatar src={me.data.avatar_url} size="small" />
            ) : (
              <Avatar size="small">{me.data.nickname.slice(0, 1)}</Avatar>
            )}
            <Typography.Text>{me.data.nickname}</Typography.Text>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ padding: 24 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
