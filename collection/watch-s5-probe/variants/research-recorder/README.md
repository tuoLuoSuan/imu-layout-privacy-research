# S5 科研记录器 0.3.0（真机待验）

本版是独立工作副本，基于普通 Vela 加速度与文件接口。用户已授权自主完善，不改变手机 App 或旧手表原型。图标直接沿用 research-ui 中与手机同源的图标，暂存构建时复制，不重复存一份二进制文件。

已实现：

- 手机同款浅色、青色按钮，采集／记录两页和六组设置。
- 2／10／30／60／180／300 秒；默认 2 秒。分钟档标为实验性，未在 S5 上验证。
- game／ui／normal 请求档位，页面另列实测平均回调到达率，不提供虚构的任意 Hz。
- 动作指令、腕侧、P01–P20 匿名参与者及 R01–R20 房间标签，默认未记录。
- 128 行或 2 秒分块保存，512 行未确认保存缓存上限，串行写入，明确失败和重试。不是物理 RAM 容量证明，也不承诺操作系统已 fsync。
- 最多 40 条本机会话（含回收区）。列表显示条数、时长、封口/中断状态；重新进入记录页刷新。
- 确认移入回收区、恢复、二次确认永久删除。永久删除中断可再次确认继续；中断/损坏采集禁止永久删除。不会自动清理科研数据。
- 页显示/隐藏/销毁、开始/停止/错误事件；回调墙钟时间及每会话自有序号。
- 按文件分段二维码导出；只加载当前文件。上一段/下一段定位，当前段自动轮播；拍完该段再手动下一段。重拍可合并，缺页报具体位置。
- 保留旧 0.1.x 最近记录只读恢复和旧二维码协议，不改写原始版本或 XYZ。

**边界：** 尚无新版本上表结果、真实 S5 原始样本或息屏持续性验收。三轴不是六轴；XYZ 单位、物理轴向和采样硬件时间未知。Date.now 回调率不是硬件采样率，隐藏页不等于系统锁屏。没有蓝牙接收端、自动上传或手机同步。本版二维码为备用出口，长记录可能需要数千页，不能作为正式分钟联采的高效传输方案。后续先验普通通信接收端，再投入批量研究采集。

## 本机核验

在仓库根目录：

```text
node --test collection/watch-s5-probe/tests/*.test.cjs
python -m unittest discover -s collection/watch-s5-probe/tests -p 'test_*source_archive.py' -v
python -m unittest discover -s collection/watch-s5-probe/tests -p test_research_export.py -v
```

Node 的五分钟往返用例从实际采集核心产生 15,000 行合成回调，实际 JS 生成分段 QR 文本，独立 Python 解码并比对所有原文件字节；不读设备、不产生真机证明。

依赖和签名沿用模块主 README 的本机配置。本版构建：

```text
node collection/watch-s5-probe/tools/build_research_source.cjs
```

默认输出 `dist/research-0.3.0`，拒绝覆盖。若它已是旧候选，可传模块 `dist` 内的新输出目录；保留之前产物。JSC／Protobuf 都关闭，同签名仅在使用同一本地签名材料时成立。RPK、密钥、证据截图与真实记录不进 Git。

## 解码

```text
python collection/watch-s5-probe/tools/decode_research_export.py packets.txt --output collection/watch-s5-probe/recordings/my-session
```

可传多个同会话文本、图片或视频。图片／视频需本机已有 OpenCV；脚本不自动安装。输出目录必须不存在。保留原始各文件、SHA-256、CSV、事件和完整性报告；无尾文件仍可导出部分数据，但报告标记 interrupted，绝不填缺。CRC 仅检测传输错误，不提供加密或来源认证。

新字段和判定的权威定义见 [腕部 v2 数据字典](../../../../docs/data/watch-s5-v2-data-dictionary.md)。真机先取回原 0.1.1 已保存的 2 秒会话，再按 [0.3.0 分级验收协议](../../../../docs/protocols/2026-10-15-s5-0.3.0-staged-validation.md)升级测试。
