# Band 9 Pro activity probe 0.1.0

普通 Vela 快应用采集原型：三轴加速度，2/10/30 秒手动指令标签，2000 回调上限，私有 JSON 存储和二维码分片导出。

完整使用入口：[中文教程](D:/Project/imu环境重建/手环9Pro_安装连接与加速度采集教程.md)。

## 开发与复核

```powershell
cd 'D:\Project\imu环境重建\collection\band9pro-probe'
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd test
$env:PYTHONUTF8='1'
python -m unittest discover -s tests -p 'test_*.py'
npm.cmd run build
```

局部依赖固定于 `package-lock.json`，使用 aiot-toolkit 2.0.5 与 @aiot-toolkit/jsc 1.0.9。Node 软件检查使用 v24.16.0；Python 媒体解码使用现有 OpenCV。Python 核心 JSON/CSV 解码只需标准库，二维码媒体检查另外依赖 OpenCV。

`tools/build_rpk.cjs` 用英文临时目录绕过供应商 Windows JSC 对中文输入路径的限制。构建后要求本轮确实生成 RPK，不依赖可能吞掉错误的工具退出码。当前的 `sign/private.pem` 是本地研究包签名私钥，不能放进分享压缩包；`sign/certificate.pem` 为公开证书。缺少私钥时需要先生成自己的证书，不能伪称可直接重建同一签名。

本机曾用 Git 附带的 OpenSSL，显式指定其配置文件，避免默认配置路径不存在：

```powershell
# 仅在没有本地签名文件时生成，不覆盖已有签名身份。
New-Item -ItemType Directory -Path sign -Force | Out-Null
if (!(Test-Path sign\private.pem)) {
  & 'D:\Application\Git\usr\bin\openssl.exe' req -config 'D:\Application\Git\usr\ssl\openssl.cnf' -x509 -newkey rsa:2048 -nodes -keyout sign\private.pem -out sign\certificate.pem -days 3650 -subj '/CN=IMU Research Local Probe/O=Local Research'
}
```

数据恢复也可运行：

```powershell
python tools/decode_export.py 'D:\你的样例\二维码录像.mp4'
python tools/decode_export.py 'D:\你的样例\原录像.mp4' 'D:\你的样例\补拍.png'
```

## 协议与证据边界

- 行数据：`[callback_elapsed_ms, x, y, z, page_state]`。不补值、不按显示精度舍入。
- 帧格式：`IMU9P|1|session_id|index|total|crc32|ASCII JSON payload`。CRC32 校验整个 JSON；缺片、冲突或校验失败拒绝完整导出。
- Date.now 是系统回调到达时间；没有硬件样本时间戳，单位未知。
- 固件/手机 App 版本为用户报告的基线元数据，不是自动检测结果；升级后须更新配置并保留版本记录。
- “静止/走路/摆手”是动作指令，不是识别器输出；未训练分类器。
- 页面隐藏仅记录事件和后续真实回调，不承诺后台继续运行。当前无后台保活配置。
- 主界面恢复最近成功保存的会话；独立旧文件保留，但没有历史浏览器。每次先导出再录新记录。
- 保存失败保留当前内存记录，可重存或二维码导出；卸载/系统强杀可能丢失未保存数据。
- 二维码短测试导出不是正式长时传输方案。没有手机采集 App、双端时钟同步或全天训练。

测试中的数值、二维码图片和视频全部是软件生成夹具，不是硬件结果。测试不覆盖手环运行时、二维码真实屏幕可读性或固件 3.1.175 的实际行为。
