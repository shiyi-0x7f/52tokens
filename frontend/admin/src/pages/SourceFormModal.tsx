import { App, Form, Input, Modal, Select, Switch } from "antd";
import { useEffect } from "react";

import { fieldErrors } from "../api/client";
import { usePlatforms, useSaveSource } from "../api/queries";
import type { Source, SourceInput } from "../api/types";
import { useErrorNotice } from "../lib/useErrorNotice";

interface Props {
  open: boolean;
  /** null = 新建 */
  source: Source | null;
  onClose: () => void;
}

export function SourceFormModal({ open, source, onClose }: Props) {
  const [form] = Form.useForm<SourceInput>();
  const platforms = usePlatforms();
  const save = useSaveSource();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue(
      source
        ? {
            platform_id: source.platform.id,
            url: source.url,
            label: source.label,
            enabled: source.enabled,
          }
        : { enabled: true, label: "" },
    );
  }, [open, source, form]);

  const submit = (values: SourceInput) => {
    save.mutate(
      { id: source?.id, input: { ...values, url: values.url.trim(), label: values.label ?? "" } },
      {
        onSuccess: () => {
          message.success(source ? "已保存" : "已添加，下次定时检查时会抓取");
          onClose();
        },
        onError: (err) => {
          const fields = Object.entries(fieldErrors(err));
          if (fields.length > 0) {
            form.setFields(fields.map(([name, msg]) => ({ name, errors: [msg] })) as never);
          } else {
            notifyError("保存监测来源失败", err);
          }
        },
      },
    );
  };

  return (
    <Modal
      title={source ? "编辑监测来源" : "添加监测来源"}
      open={open}
      okText="保存"
      confirmLoading={save.isPending}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
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
        <Form.Item
          name="url"
          label="页面地址"
          rules={[{ required: true, type: "url", message: "请填写官方页面的完整链接" }]}
          extra="选活动页、免费额度文档、公告页等静态页面；前端渲染的页面抓不到正文"
        >
          <Input placeholder="https://" />
        </Form.Item>
        <Form.Item name="label" label="备注" rules={[{ max: 60 }]}>
          <Input maxLength={60} placeholder="例如：免费额度文档" />
        </Form.Item>
        <Form.Item name="enabled" label="参与定时检查" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
