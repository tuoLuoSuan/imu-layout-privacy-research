# IMU 采集 / IMU Recorder

用于手机惯性数据科研的原生Android采集器。用户主动记录含重力加速度和角速度，停止后通过系统保存入口导出原始序列、事件、时间锚和完整性报告。应用没有网络权限，不自动上传。

当前开发版本 **0.2.2**：延续浅色仪表盘与“采集 / 记录”两页，新增25–200整数Hz请求配置（默认100Hz）与经确认的单条记录删除。两个通道使用同一份会话配置；采集中不可修改。保留v1文件格式、原r2判据和四权限；重力向量/线性加速度可选通道尚未实现。

0.2.2已在同机保留数据升级，升级时40个旧文件一致；用户检查120Hz设置保存/重开及删除弹窗，并主动确认删除两条旧测试记录，其电脑16文件备份仍与删除前一致，剩余24旧文件未变。另完成11.275秒120Hz参数贯通短试，metadata为120/8333，双通道1334/1335条、队列丢弃0，SAF原ZIP校验一致。短试基线不足，不是120Hz或新版长期稳定性通过。0.2.1冻结源码与原实验结果保留，不能将旧版结果推广到所有配置。

电脑测试为42项Java通过、1项符号链接用例因Windows权限跳过、4项Python通过；补充Windows Junction目录链接拒绝与源/目标保留检查通过。构建成功、lint无错误/1项原有依赖更新提示。真实界面、用户操作、文件比对与电脑测试分别记账。

## 已验证到哪里

0.2.0已在本项目小米17 Pro / Android17 / HyperOS4.0.0.41上保留数据升级。Codex观察了两页真实界面，用户确认记录选择、系统保存页、取消返回正常；3条会话的24个文件升级及界面检查前后SHA-256一致。34项Java和4项Python测试通过，lint为0错误、1项原有测试依赖更新提示。

0.2.1在同机、用户先前设置“不限制”、USB连接下完成841.581秒会话；全部9个实际状态段的r2频率稳定性通过，实际约118.38Hz，两通道无>1秒事件/交付缺口、队列丢弃0。每通道各2次>100ms交付告警，最大约141ms，原样保留。独立工具仍要求外部审核；这不是精确100Hz或通用定频保证。

旧0.1.0与本轮0.2.0对照按原r2频率稳定性失败的结论保留。尚未做0.2.1拔线短试、独立其他App亮屏60秒或标准30分钟，G1未全部通过；UTCpartial，跨设备同步未验。见[兼容性与限制](docs/compatibility.md)。

## 使用

1. 安装对应版本APK。更新须同一签名，不通过卸载清除尚未导出的记录。
2. 在“采集”页点“请求100Hz · 调整”，选25/50/100/200快捷值或输入25–200整数并保存。首次默认100Hz，记住上次选择。该值是请求提示；实际频率由系统决定，以原始时间检查为准。已报告能力不能支持该周期时拒绝启动，不静默夹值。
3. 点“开始采集”，首次允许通知后再主动点一次开始。启动时冻结本次配置，metadata保存用户Hz与取整微秒周期；例如120Hz对应8333µs。
4. 计数增长后按实验协议操作；锁屏/切出连续性以导出检查为准。
5. 点“停止并保存”，等待保存完成；异常结束的部分文件也保留。
6. 到“记录”选择会话，查看该会话原有请求配置，点“导出ZIP”，在系统保存页选择位置。
7. 不需要的记录可点“删除记录”，核对时间和会话ID后确认。只删除应用内单条已封口记录，已导出ZIP与电脑档案保留；不可恢复。采集、收尾、导出或其他记录操作时禁删。

删除先将整条会话移至应用私有的独立待删除区；清理中断不会恢复为实验。未清理完会明确提示，记录页提供“重试清理”，不冒称空间已全部释放。不会自动清理其他记录。

“正常结束”只表示完成收尾。“应用检查未通过”“检查结果未知”“待独立核验”分别显示，均不能替代外部验收。

## 构建

JDK21、AGP9.4.1、Gradle9.6.1，compile/target37、min34、build-tools37.0.0。实际锁定信息见[toolchain-lock.json](toolchain-lock.json)。无新增运行依赖，JUnit/org.json仅用于电脑测试。

在本模块根目录执行。先安装正式SDK包`platforms;android-37.0`与`build-tools;37.0.0`，将`JAVA_HOME`和`ANDROID_HOME`设为自己的路径，或用未提交的`local.properties`指定SDK。Windows推荐不含中文的检出路径：本机曾遇到中文路径导致测试JVM参数文件编码失败。

Windows：

```powershell
.\gradlew.bat --no-daemon testDebugUnitTest assembleDebug lintDebug
python -m unittest discover -s tools -p test_check_export.py -v
```

Linux/macOS标准入口：

```sh
sh ./gradlew --no-daemon testDebugUnitTest assembleDebug lintDebug
python3 -m unittest discover -s tools -p test_check_export.py -v
```

本轮仅在Windows实际构建Android APK，Linux/macOS入口未实测。产物位于`app/build/outputs/apk/debug/app-debug.apk`。第一次构建需联网取得Gradle/SDK/Maven依赖，这是电脑构建过程。

`tools/build.ps1`是本机便利脚本，带本地Java/缓存路径和英文目录联接，不是通用安装器。其他开发者使用自己的环境变量与Gradle入口，不复制本机代理、SDK或签名缓存。

## 检查ZIP

仅依赖Python标准库，无须安装模型训练环境：

```sh
python tools/check_export.py --zip /path/to/imu_session.zip --output /path/to/check_result
```

示例路径替换为实际文件，Windows也可用自己的`D:/...`路径。输出`independent_integrity.json`；退出码1表示明确数据失败，2可表示输入错误、未知或仍需外部审查。当前检查器不自动给出整体验收通过的0，请同时看结构化报告。

## 结构与文档

| 位置 | 用途 |
|---|---|
| MainActivity、ui包、res | 页面、只读展示、文字/样式/图标 |
| RecorderService、AndroidRecordingRuntime | 独立采集与Android适配 |
| core包、SessionExporter | 会话、租期、文件、时钟、完整性与导出 |
| app/src/test、tools/test_check_export.py | 明确标注的合成输入与行为测试 |
| tools/check_export.py | 独立核验哈希、计数、间隔和时间锚 |

- [导出格式与失败语义](docs/export-format.md)
- [实机协议](docs/device-test.md)
- [兼容性与限制](docs/compatibility.md)
- [GitHub发布准备清单](docs/open-source-release.md)

## 科研与开源定位

本模块拟作为主研究仓库中的采集工具发布，便于复核数据来源和复现实验。活动识别、手机/腕部同步、雷达地图与布局推断属于后续模块，当前没有模型准确率或重建精度结果。

当前APK为本机调试签名版本，尚未创建公开GitHub仓库或正式Release。发布前仍须确定作者/机构署名、许可证、引用和发布签名，并整理包含本机路径的历史材料。当前尚无确定的开源许可证，不应推定授权条款。私人家庭数据、完整系统诊断、签名材料、SDK和缓存不随源码公开。
