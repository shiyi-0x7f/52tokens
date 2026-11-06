import { App, Form, Input, InputNumber, Modal, Select, Typography } from "antd";
import { useDeferredValue, useEffect, useState } from "react";

import { fieldErrors } from "../api/client";
import { useModelSearch, useSaveComparison } from "../api/queries";
import type { ComparisonInput, ModelComparison } from "../api/types";
import { useErrorNotice } from "../lib/useErrorNotice";

interface Props {
  open: boolean;
  /** null = 新建 */
  comparison: ModelComparison | null;
  onClose: () => void;
}

/** 远程搜索模型：输入名称或 slug，最多显示 20 个 */
function ModelSelect(props: { value?: string; onChange?: (slug: string) => void }) {
  const [q, setQ] = useState("");
  const models = useModelSearch(useDeferredValue(q.trim()));
  return (
    <Select
      {...props}
      showSearch={{ filterOption: false, onSearch: setQ }}
      loading={models.isFetching}
      placeholder="输入模型名或 slug 搜索"
      notFoundContent={models.isFetching ? "搜索中…" : "没有匹配的已发布模型"}
      options={(models.data ?? []).map((m) => ({
        value: m.slug,
        label: `${m.name}（${m.slug}）`,
      }))}
    />
  );
}

export function ComparisonFormModal({ open, comparison, onClose }: Props) {
  const [form] = Form.useForm<ComparisonInput>();
  const save = useSaveComparison();
  const { message } = App.useApp();
  const notifyError = useErrorNotice();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue(
      comparison
        ? { intro: comparison.intro, sort_order: comparison.sort_order }
        : { intro: "", sort_order: 0 },
    );
  }, [open, comparison, form]);

  const submit = (values: ComparisonInput) => {
    const base = { intro: values.intro ?? "", sort_order: values.sort_order ?? 0 };
    const args = comparison
      ? { id: comparison.id, input: base }
      : {
          input: { ...base, model_a_slug: values.model_a_slug, model_b_slug: values.model_b_slug },
        };
    save.mutate(args, {
      onSuccess: () => {
        message.success(comparison ? "已保存" : "已收录，公开站和 sitemap 会出现这组对比");
        onClose();
      },
      onError: (err) => {
        const fields = Object.entries(fieldErrors(err));
        if (fields.length > 0) {
          form.setFields(fields.map(([name, msg]) => ({ name, errors: [msg] })) as never);
        } else {
          notifyError("保存对比失败", err);
        }
      },
    });
  };

  return (
    <Modal
      title={comparison ? "编辑对比" : "收录对比"}
      open={open}
      okText="保存"
      confirmLoading={save.isPending}
      onOk={() => form.submit()}
      onCancel={onClose}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={submit} requiredMark="optional">
        {comparison ? (
          <Typography.Paragraph>
            <Typography.Text strong>{comparison.model_a.name}</Typography.Text> vs{" "}
            <Typography.Text strong>{comparison.model_b.name}</Typography.Text>
            <Typography.Text type="secondary">
              （模型不能改，需要换请删除后重新收录）
            </Typography.Text>
          </Typography.Paragraph>
        ) : (
          <>
            <Form.Item
              name="model_a_slug"
              label="模型 A"
              rules={[{ required: true, message: "请选择模型 A" }]}
              extra="网址按 A-vs-B 的顺序生成，一般把更常被搜索的模型放前面"
            >
              <ModelSelect />
            </Form.Item>
            <Form.Item
              name="model_b_slug"
              label="模型 B"
              dependencies={["model_a_slug"]}
              rules={[
                { required: true, message: "请选择模型 B" },
                ({ getFieldValue }) => ({
                  validator: (_, value) =>
                    value && value === getFieldValue("model_a_slug")
                      ? Promise.reject(new Error("两个模型不能相同"))
                      : Promise.resolve(),
                }),
              ]}
            >
              <ModelSelect />
            </Form.Item>
          </>
        )}
        <Form.Item
          name="intro"
          label="导语"
          rules={[{ max: 2000 }]}
          extra="可选。写选型建议等人工内容，显示在对比页顶部，能让页面内容更独特"
        >
          <Input.TextArea rows={4} maxLength={2000} showCount />
        </Form.Item>
        <Form.Item
          name="sort_order"
          label="排序"
          extra="数字小的排前面（模型页「对比」列表的顺序）"
        >
          <InputNumber min={0} max={9999} precision={0} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
