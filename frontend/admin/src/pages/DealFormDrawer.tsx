import {
  App,
  Button,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Segmented,
  Select,
  Space,
  Switch,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect } from "react";

import { fieldErrors } from "../api/client";
import { CYCLE_LABELS, DEAL_TYPE_LABELS } from "../api/labels";
import { usePlatforms, useSaveDeal } from "../api/queries";
import type { Deal, DealCycle, DealInput, DealType } from "../api/types";
import { useErrorNotice } from "../lib/useErrorNotice";

interface FormValues {
  platform_id: number;
  slug?: string;
  title: string;
  deal_type: DealType;
  reward_text: string;
  est_value_cny?: number | null;
  requirements: string[];
  cycle: DealCycle;
  starts_at?: Dayjs | null;
  ends_at?: Dayjs | null;
  description?: string;
  /** 每行一个步骤 */
  steps_text?: string;
  source_url: string;
  source_quote?: string;
  aff_url?: string;
  in_app_only: boolean;
}

const TYPE_OPTIONS = Object.entries(DEAL_TYPE_LABELS).map(([value, label]) => ({ value, label }));
const CYCLE_OPTIONS = Object.entries(CYCLE_LABELS).map(([value, label]) => ({ value, label }));

function toValues(deal: Deal | null): Partial<FormValues> {
  if (!deal) return { cycle: "once", requirements: [], in_app_only: false };
  return {
    platform_id: deal.platform.id,
    slug: deal.slug,
    title: deal.title,
    deal_type: deal.deal_type,
    reward_text: deal.reward_text,
    est_value_cny: deal.est_value_cny === null ? null : Number(deal.est_value_cny),
    requirements: deal.requirements,
    cycle: deal.cycle,
    starts_at: deal.starts_at ? dayjs(deal.starts_at) : null,
    ends_at: deal.ends_at ? dayjs(deal.ends_at) : null,
    description: deal.description,
    steps_text: deal.steps.join("\n"),
    source_url: deal.source_url,
    source_quote: deal.source_quote,
    aff_url: deal.aff_url ?? "",
    in_app_only: deal.in_app_only,
  };
}

function toInput(values: FormValues): DealInput {
  return {
    platform_id: values.platform_id,
    slug: values.slug?.trim() || null,
    title: values.title,
    deal_type: values.deal_type,
    reward_text: values.reward_text,
    est_value_cny: values.est_value_cny ?? null,
    requirements: values.requirements,
    cycle: values.cycle,
    starts_at: values.starts_at ? values.starts_at.toISOString() : null,
    ends_at: values.ends_at ? values.ends_at.toISOString() : null,
    description: values.description ?? "",
    steps: (values.steps_text ?? "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    source_url: values.source_url.trim(),
    source_quote: values.source_quote?.trim() ?? "",
    aff_url: values.aff_url?.trim() || null,
    in_app_only: values.in_app_only,
  };
}

interface Props {
  open: boolean;
  /** null = 新建 */
  deal: Deal | null;
  onClose: () => void;
}

export function DealFormDrawer({ open, deal, onClose }: Props) {
  const [form] = Form.useForm<FormValues>();
  const platforms = usePlatforms();
  const save = useSaveDeal();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();
  const published = deal?.confirmed_at != null;

  useEffect(() => {
    if (open) form.setFieldsValue(toValues(deal) as FormValues);
    else form.resetFields();
  }, [open, deal, form]);

  const submit = (values: FormValues) => {
    save.mutate(
      { id: deal?.id, input: toInput(values) },
      {
        onSuccess: (saved) => {
          message.success(deal ? "已保存" : `已创建，状态为「待审核」：${saved.title}`);
          onClose();
        },
        onError: (err) => {
          const fields = Object.entries(fieldErrors(err));
          if (fields.length > 0) {
            form.setFields(fields.map(([name, msg]) => ({ name, errors: [msg] })) as never);
          } else {
            notifyError("保存活动失败", err);
          }
        },
      },
    );
  };

  return (
    <Drawer
      title={deal ? `编辑活动 · ${deal.title}` : "新建活动"}
      open={open}
      onClose={onClose}
      size="large"
      destroyOnHidden
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
            保存
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" onFinish={submit} requiredMark="optional">
        <Form.Item
          name="platform_id"
          label="平台"
          rules={[{ required: true, message: "请选择平台" }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            loading={platforms.isPending}
            options={(platforms.data ?? []).map((p) => ({ value: p.id, label: p.name }))}
            placeholder="选择平台"
          />
        </Form.Item>
        <Form.Item name="title" label="标题" rules={[{ required: true, min: 2, max: 200 }]}>
          <Input maxLength={200} showCount placeholder="例如：每日签到送积分" />
        </Form.Item>
        <Space.Compact block>
          <Form.Item
            name="deal_type"
            label="类型"
            rules={[{ required: true, message: "请选择类型" }]}
            style={{ flex: 1 }}
          >
            <Select options={TYPE_OPTIONS} placeholder="活动类型" />
          </Form.Item>
          <Form.Item
            name="reward_text"
            label="奖励"
            rules={[{ required: true, max: 100 }]}
            style={{ flex: 2 }}
          >
            <Input placeholder="例如：+200 积分/天、100 万 tokens" />
          </Form.Item>
        </Space.Compact>
        <Form.Item name="cycle" label="周期">
          <Segmented options={CYCLE_OPTIONS} />
        </Form.Item>
        <Form.Item name="requirements" label="参与门槛" extra="回车或逗号分隔，最多 8 项">
          <Select
            mode="tags"
            tokenSeparators={[",", "，"]}
            maxCount={8}
            placeholder="如：需实名、需手机号"
          />
        </Form.Item>
        <Space size="large" wrap>
          <Form.Item name="starts_at" label="开始时间">
            <DatePicker showTime />
          </Form.Item>
          <Form.Item name="ends_at" label="截止时间">
            <DatePicker showTime />
          </Form.Item>
          <Form.Item name="est_value_cny" label="估值（元）" extra="算不出就留空，不夸大">
            <InputNumber min={0} precision={2} prefix="¥" />
          </Form.Item>
        </Space>
        <Form.Item
          name="source_url"
          label="官方出处"
          rules={[{ required: true, type: "url", message: "请填写活动所在的官网链接" }]}
        >
          <Input placeholder="https://" />
        </Form.Item>
        <Form.Item
          name="source_quote"
          label="官网原文"
          rules={[{ max: 300 }]}
          extra="从官方页面逐字复制一句话（别改写）。页面会生成定位链接，用户打开官网后自动滚到这句话并高亮"
        >
          <Input.TextArea rows={2} maxLength={300} showCount placeholder="可留空" />
        </Form.Item>
        <Form.Item
          name="steps_text"
          label="参与步骤"
          extra="每行一步，按先后顺序，最多 8 步；例如：登录控制台 → 进入费用中心 → 领取资源包"
          rules={[
            {
              validator: (_, value?: string) => {
                const lines = (value ?? "").split("\n").filter((s) => s.trim());
                if (lines.length > 8) return Promise.reject(new Error("最多 8 步"));
                if (lines.some((s) => s.trim().length > 100)) {
                  return Promise.reject(new Error("每步不超过 100 字"));
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input.TextArea
            rows={4}
            placeholder={"打开 Trae 客户端\n点击右上角头像\n点「每日签到」"}
          />
        </Form.Item>
        <Form.Item
          name="aff_url"
          label="推广链接"
          rules={[{ type: "url", message: "链接格式不正确" }]}
          extra="填写后页面会自动标注「推广」，并加 rel=sponsored"
        >
          <Input placeholder="可留空" />
        </Form.Item>
        <Form.Item name="in_app_only" label="只能在客户端内查看" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={4} maxLength={2000} showCount />
        </Form.Item>
        <Form.Item
          name="slug"
          label="页面地址（slug）"
          extra={published ? "已发布过的活动不能改地址，否则已收录的页面会 404" : "留空自动生成"}
        >
          <Input disabled={published} placeholder="例如：trae-daily-checkin" />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
