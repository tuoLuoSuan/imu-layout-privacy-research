# RoomTrace：用手机和手表恢复家具布局

**简体中文** · [English](README.md)

在房间里走一圈，再坐下、躺下或开柜子，这些动作能透露多少家具位置？RoomTrace 拿到房间轮廓和家具尺寸清单后，用配准过的走位点和带类别的接触事件，为每件家具预测一个矩形框。

在独立的合成确认实验中，RoomTrace 有 **412/1,500（27.47%）** 个请求的所有家具中心误差都在 0.5 m 以内。纯几何基线为 254/1,500（16.93%）。走路覆盖达到 100% 时，两者分别是 76.0% 和 50.2%。同样是全覆盖、但没有接触时，分别是 71% 和 15%。实验使用 50 个留出条件组，生成失败也计入分母，得分为零。

[复算论文主表](#复算论文主表) · [回放真实宿舍](examples/registered-dorm/) · [录制新数据](docs/roomtrace/capture.zh-CN.md)

设备下载 · [安卓 APK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Capture-0.2.4.apk) ·
[小米 Watch S5 RPK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/org.imuresearch.s5joint.release.0.2.23.rpk) ·
[AstroBox 桥接插件 ABP](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Bridge-0.2.5-clock-discard.abp) ·
[安装和导出指南](docs/roomtrace/capture.zh-CN.md)

## 复算论文主表

一台支持 AVX2 的 x86-64 电脑和 Python 3.11 或更新版本就能跑。在仓库根目录执行下面几条命令。

```bash
python -m pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python -m roomtrace download
python -m roomtrace summarize --out output/confirmation-recomputed.json
python -m roomtrace verify --out output/inference-check.json
```

`download` 下载并校验 SHA-256。`summarize` 从归档预测重算主表和按条件组配对的置信区间。`verify` 从 15 个覆盖率与接触数组合中各选一例，重跑后逐项比对坐标。

比对坐标时请使用[已测试的依赖版本](reproducibility/requirements-tested.txt)。不同的数值库可能改变分数接近的候选顺序。命令行入口会在加载库前选择参考 AVX2、oneDNN 和 MKL 设置，也会保留你显式指定的环境变量。

从头对全套 1,500 个请求运行三种解码器：

```bash
python -m roomtrace evaluate --out output/my-confirmation --threads 4
```

原评估在 12 核桌面 CPU 上耗时约 13 分钟。

## 看一间房怎么恢复

```bash
python -m roomtrace predict --input examples/synthetic-zero-contacts.json \
  --baseline --out output/zero-contact-layout.json
python -m roomtrace predict --input examples/synthetic-six-contacts.json \
  --baseline --out output/six-contact-layout.json
```

输入里有房间轮廓、家具类别和尺寸、配准后的走位点、接触类别及位置，以及声明的桌椅关联。解码器按输入里实际有几条接触选分支。零接触时用学习到的空间残差，有接触时用冻结的接触解码器 D。真值框在打分时使用。[528,064 个参数和解码流程](docs/roomtrace/architecture.md)

[真实宿舍样例](examples/registered-dorm/)来自一段 56.45 秒的录制。回放从配准后的 128 个走位点、5 个接触和房间几何开始，四件家具全部命中，平均中心误差 **0.143 m**。

## 从采集到动作分类

[采集指南](docs/roomtrace/capture.zh-CN.md)写清了手机、手表和桥接插件怎么安装，怎么录、怎么导出，以及怎样检查导出的 ZIP。整理好手机 CSV 后，可以生成动作时间线。

```bash
python -m roomtrace actions --session YOUR_EXPORTED_SESSION \
  --out output/activity-timeline.json
```

手机采加速度和角速度，手表采三轴加速度。[手机分类器](analysis/layout/action_model.py)使用冻结的随机森林和[惯性特征](analysis/layout/action_features.py)。[RoNIN 适配器](analysis/phone_ronin)用于手机里程计。布局解码需要把走位和接触配准到房间坐标系。[RoNIN 上游模型](https://github.com/Sachini/ronin)

## 训练、图表和代码

```bash
python -m roomtrace download --training
```

这条命令额外下载合成训练观测及精化器训练用的粗布局。缓存怎么生成、各模块怎么训练、原来的参数在哪，都在[训练指南](docs/roomtrace/training.md)。

| 路径 | 里面是什么 |
|---|---|
| `roomtrace/` | 下载、推理、打分和校验的命令行入口 |
| `analysis/layout/` | 模型、候选搜索和动作分类 |
| `collection/` | 手机、手表和桥接插件的采集代码 |
| `reproducibility/` | 数据清单、权重校验值、训练协议和结果表 |

[评估协议](docs/roomtrace/protocol.md) · [复现范围](docs/roomtrace/reproduction-matrix.md) · [论文图表和历史对照](docs/roomtrace/paper-artifacts.md)

## 许可

自有代码和模型权重采用 Apache-2.0，自有合成数据采用 CC BY 4.0。真实宿舍、设备安装包和第三方材料的适用范围见[许可说明](LICENSING.md)。
