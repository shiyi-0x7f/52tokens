import {
  Alert,
  App,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Segmented,
  Select,
  Space,
  Switch,
} from "antd";
import { useEffect } from "react";

import { fieldErrors } from "../api/client";
import { usePlatforms, useSavePrice } from "../api/queries";
import type { Currency, Price, PriceInput } from "../api/types";
import { useErrorNotice } from "../lib/useErrorNotice";

interface FormValues {
  platform_id: number;
  model_slug: string;
  model_name?: string;
  family?: string;
  context_window?: number | null;
  currency: Currency;
  input_price?: number | null;
  output_price?: number | null;
  cache_read_price?: number | null;
  is_free: boolean;
  free_note?: string;
  source_url: string;
}

const num = (v: string | null) => (v === null ? null : Number(v));

function toValues(price: Price | null): Partial<FormValues> {
  if (!price) return { currency: "CNY", is_free: false };
  return {
    platform_id: price.platform.id,
    model_slug: price.model.slug,
    currency: price.currency,
    input_price: num(price.input_price),
    output_price: num(price.output_price),
    cache_read_price: num(price.cache_read_price),
    is_free: price.is_free,
    free_note: price.free_note,
    source_url: price.source_url,
  };
}

function toInput(v: FormValues): PriceInput {
  return {
    platform_id: v.platform_id,
    model_slug: v.model_slug.trim(),
    model_name: v.model_name?.trim() || null,
    family: v.family?.trim() || null,
    context_window: v.context_window ?? null,
    currency: v.currency,
    input_price: v.input_price ?? null,
    output_price: v.output_price ?? null,
    cache_read_price: v.cache_read_price ?? null,
    is_free: v.is_free,
    free_note: v.free_note ?? "",
    source_url: v.source_url.trim(),
  };
}

interface Props {
  open: boolean;
  /** null = 新录入 */
  price: Price | null;
  onClose: () => void;
}

export function PriceFormDrawer({ open, price, onClose }: Props) {
  const [form] = Form.useForm<FormValues>();
  const platforms = usePlatforms();
  const save = useSavePrice();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();
  const isFree = Form.useWatch("is_free", form);

  useEffect(() => {
    if (open) form.setFieldsValue(toValues(price) as FormValues);
    else form.resetFields();
  }, [open, price, form]);

  const submit = (values: FormValues) => {
    save.mutate(toInput(values), {
      onSuccess: (saved) => {
        message.success(`已保存并发布：${saved.platform.name} · ${saved.model.name}`);
        onClose();
      },
      onError: (err) => {
        const fields = Object.entries(fieldErrors(err));
        if (fields.length > 0) {
          form.setFields(fields.map(([name, msg]) => ({ name, errors: [msg] })) as never);
        } else {
          notifyError("保存价格失败", err);
        }
      },
    });
  };

  return (
    <Drawer
      title={price ? `更新价格 · ${price.platform.name} · ${price.model.name}` : "录入价格"}
      open={open}
      onClose={onClose}
      size="large"
      destroyOnHidden
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
            保存并发布
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="请先在官网核对价格再保存"
        description="保存即视为当场核实，会立刻对外展示，核实时间记为现在。单位：每百万 tokens。"
      />
      <Form form={form} layout="vertical" onFinish={submit} requiredMark="optional">
        <Form.Item
          name="platform_id"
          label="平台"
          rules={[{ required: true, message: "请选择平台" }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            disabled={price !== null}
            options={(platforms.data ?? []).map((p) => ({ value: p.id, label: p.name }))}
          />
        </Form.Item>
        <Form.Item
          name="model_slug"
          label="模型 slug"
          rules={[
            { required: true },
            { pattern: /^[a-z0-9][a-z0-9-]{0,78}[a-z0-9]$/, message: "小写字母、数字和 -" },
          ]}
          extra="已有模型直接填它的 slug（如 deepseek-chat）；填新 slug 会新建模型"
        >
          <Input disabled={price !== null} placeholder="deepseek-chat" />
        </Form.Item>
        {price === null && (
          <Space size="large" wrap>
            <Form.Item name="model_name" label="模型名称（新模型必填）">
              <Input placeholder="DeepSeek V3" />
            </Form.Item>
            <Form.Item
              name="family"
              label="系列（新模型必填）"
              rules={[{ pattern: /^[a-z0-9-]{1,40}$/, message: "小写字母、数字和 -" }]}
            >
              <Input placeholder="deepseek" />
            </Form.Item>
            <Form.Item name="context_window" label="上下文（tokens）">
              <InputNumber min={1} placeholder="131072" />
            </Form.Item>
          </Space>
        )}
        <Form.Item name="currency" label="币种">
          <Segmented
            options={[
              { value: "CNY", label: "人民币" },
              { value: "USD", label: "美元" },
            ]}
          />
        </Form.Item>
        <Form.Item name="is_free" label="免费" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Space size="large" wrap>
          <Form.Item
            name="input_price"
            label="输入价"
            rules={[{ required: !isFree, message: "非免费价格必填" }]}
          >
            <InputNumber min={0} precision={4} />
          </Form.Item>
          <Form.Item
            name="output_price"
            label="输出价"
            rules={[{ required: !isFree, message: "非免费价格必填" }]}
          >
            <InputNumber min={0} precision={4} />
          </Form.Item>
          <Form.Item name="cache_read_price" label="缓存命中价">
            <InputNumber min={0} precision={4} />
          </Form.Item>
        </Space>
        <Form.Item name="free_note" label="说明" extra="例如：限 30 并发、错峰时段半价">
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item
          name="source_url"
          label="官方定价页"
          rules={[{ required: true, type: "url", message: "请填写官方定价页链接" }]}
        >
          <Input placeholder="https://" />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
