# 分享图字体

`NotoSansSC-Bold-subset.otf`：分享图（`/og/*`）渲染用的中文字体。

- 来源：[Noto Sans SC Bold](https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Bold.otf)（2026-10-23 下载）
- 授权：SIL Open Font License 1.1，见同目录 `OFL.txt`
- 裁剪：GB2312 全部字符 + ASCII + 常用全角标点 / 符号（共 7547 个字符），8.5 MB → 1.7 MB。生僻字不在子集里，会显示为空白

重新裁剪（fonttools 用 `uvx` 临时运行，不进项目依赖）：

```bash
# chars.txt：GB2312 区位 0xA1A1–0xF7FE 全部可解码字符 + ASCII 0x20–0x7E + 常用符号
uvx --from fonttools pyftsubset NotoSansSC-Bold.otf --text-file=chars.txt \
  --output-file=NotoSansSC-Bold-subset.otf --layout-features='*' --no-hinting --desubroutinize
```
