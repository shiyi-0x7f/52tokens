import { App, Form, Input, Modal, Select, Switch } from "antd";
import { useEffect } from "react";

import { fieldErrors } from "../api/client";
import { SHOP_KIND_LABELS } from "../api/labels";
import { useSaveShopSource } from "../api/queries";
import type { ShopCollectorKind, ShopSource, ShopSourceInput } from "../api/types";
import { useErrorNotice } from "../lib/useErrorNotice";

const KIND_OPTIONS = (Object.keys(SHOP_KIND_LABELS) as ShopCollectorKind[]).map((value) => ({
  value,
  label: SHOP_KIND_LABELS[value],
}));

interface Props {
  open: boolean;
  /** null = 新建 */
  source: ShopSource | null;
  onClose: () => void;
}

export function ShopSourceModal({ open, source, onClose }: Props) {
  const [form] = Form.useForm<ShopSourceInput>();
  const kind = Form.useWatch("collector_kind", form);
  const save = useSaveShopSource();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue(
      source
        ? {
            entry_url: source.entry_url,
            collector_kind: source.collector_kind,
            name: source.name,
            enabled: source.enabled,
          }
        : { enabled: true, name: "" },
    );
  }, [open, source, form]);

  const submit = (values: ShopSourceInput) => {
    save.mutate(
      {
        id: source?.id,
        input: { ...values, entry_url: values.entry_url.trim(), name: values.name ?? "" },
      },
      {
        onSuccess: () => {
          message.success(source ? "已保存" : "已添加，下次定时同步时会采集，也可以点「立即采集」");
          onClose();
        },
        onError: (err) => {
          const fields = Object.entries(fieldErrors(err));
          if (fields.length > 0) {
            form.setFields(fields.map(([name, msg]) => ({ name, errors: [msg] })) as never);
          } else {
            notifyError("保存店铺失败", err);
          }
        },
      },
    );
  };

  return (
    <Modal
      title={source ? "编辑卡网店铺" : "添加卡网店铺"}
      open={open}
      okText="保存"
      confirmLoading={save.isPending}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={submit} requiredMark="optional">
        <Form.Item
          name="collector_kind"
          label="店铺系统"
          rules={[{ required: true, message: "请选择店铺系统" }]}
          extra="决定用哪种方式采集；不确定时可先选「通用页面解析」"
        >
          <Select showSearch optionFilterProp="label" options={KIND_OPTIONS} />
        </Form.Item>
        <Form.Item
          name="entry_url"
          label="店铺地址"
          rules={[{ required: true, type: "url", message: "请填写完整链接" }]}
          extra={
            kind === "shopApi"
              ? "多商户平台：填具体商户的店铺页，例如 https://wzyp.cn/shop/XXXX"
              : kind === "shopGoodsApi"
                ? "多商户平台：填具体商户的店铺页，要带 www，例如 https://www.16688.com.cn/shop/S123456"
                : "一般填店铺首页"
          }
        >
          <Input placeholder="https://" />
        </Form.Item>
        <Form.Item name="name" label="备注名" rules={[{ max: 80 }]}>
          <Input maxLength={80} placeholder="可留空，只在后台显示" />
        </Form.Item>
        <Form.Item name="enabled" label="参与定时同步" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
