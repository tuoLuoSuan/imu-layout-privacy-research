# 版本、证据和备份

本仓库承载整项IMU空间隐私研究：采集、环境、数据合同、建模、实验、论文和展示。尚未实现的部分在项目状态中明确列出；首提交不是最终科研成果。

## 源码备份边界

`repository-policy.json`逐文件列出首批受控源码。检查：

```sh
python -m unittest discover -s tools/tests -v
python tools/repository_guard.py --candidate
python tools/repository_guard.py --staged
python tools/repository_guard.py --revision HEAD
```

分别检查候选文件、完整暂存区和提交对象。扫描结果中的`files`含大小和SHA-256；发现内容问题只报类别和行号，不打印匹配正文。原始记录、真实截图、日志、诊断、签名和SSH资料不进入源码提交。两项逐哈希二进制例外为Gradle wrapper和腕部原型图标。未来增加文件需先人工复核再改白名单；不能仅靠扩展名证明安全。

可在本地启用提交/推送钩子：`git config core.hooksPath tools/git-hooks`。提交检查完整暂存区，推送检查目标引用中尚未到达该远程引用的每个提交；首次推送检查全部历史，避免只检查最新树却漏掉已删除的旧秘密。钩子不会随clone自动启用，也不能防止人为绕过。扫描不具备自动识别人名/住址或所有秘密的能力，公开发布前还须人工审查与授权。

## 冻结App

`frozen-app-0.2.2.json`保存原66文件快照清单和关联APK摘要，不包含APK、签名或采集序列。原`source_digest`仅覆盖`app/src/main`下按路径排序的36文件字节拼接，不能当作整个仓库摘要。Git完整提交号另行追溯全仓。

导出检验例子见手机模块README，原始数据从受控备份自行提供。请求频率与实测事件率分开；短试基线不足保留未知，历史失败不改判。

## 本地私有材料

本机`environment/reports/INDEX.md`和相邻manifest索引18个报告目录；原始ZIP、点云、截图和诊断不在GitHub。仓库内部分历史计划/App说明保留本机路径作为原始开发记录，其他机器须替换路径，不能把这些路径当作仓库自带的文件。

本机`backups/`下的清单记录准备备份的原件、大小和摘要。生成清单、同机副本、VM快照都不等于独立介质备份。只有复制到用户指定的独立存储并逐文件复核后，才能称原件备份完成。源码推送与原件备份分开验收。

## 展示网站

源码包保留六页网站；`showcase/data/`真实曲线和`showcase/assets/`真实手机截图未打包。没有私有素材时，真实信号页会提示样例读取失败、截图不显示；人工三维演示和本地CSV导入仍可用。不要用合成数据填入真实样例位置。

本轮未验收干净clone下的完整视觉效果，只验证源码、依赖与静态服务入口。继续使用本机私有素材时的历史浏览器验收不能当作无数据源码包的视觉验收。

## 2026-10-17采集基线冻结

新增[手机/手表/插件冻结](collection-freeze-2026-10-17.md)与[机器可读清单](frozen-collection-2026-10-17.json)。Git标签只固定源码；真实数据与签名不上传，网站继续本机。后续研究按[路线](../research/2026-10-17-research-restart-and-sensor-capabilities.md)执行。
