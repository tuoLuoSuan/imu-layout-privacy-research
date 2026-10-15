# 0.3.2 圆形图标构建覆盖层

用户要求手表图标与系统应用一致为圆形。`icon.svg`保留手机原三轴线条，只把底形改成青色圆盘；`icon.png`为浏览器192px透明背景渲染结果。手机原图标和旧手表源包不改。

独立`tools/build_transfer_round_source.cjs`从0.3.1暂存副本升到0.3.2/code6，仅替换页面版本、采集元数据版本、图标。采集/存储/传输逻辑、普通能力和签名身份保持；回归测试对比暂存字节。此候选不代表真实传输已通过。

```text
python collection/watch-s5-probe/tools/export_round_icon.py collection/watch-s5-probe/variants/transfer-round/icon.svg
# 用浏览器将SVG以192x192、透明背景渲染为同目录icon.png。
node collection/watch-s5-probe/tools/build_transfer_round_source.cjs collection/watch-s5-probe/dist/transfer-0.3.2
```

不覆盖旧输出；用户先测接收插件0.1.1的同步界面检查，再保留数据更新此包。旧两秒记录和原始导出仍须独立核验。
