# S5 0.4.3 前台自动保亮记录器

继承0.4.2，新增普通system.brightness.setKeepScreenOn。开始前保亮请求成功才录制，停止/失败/切出后释放；不会改变亮度值、系统超时或自动重录。页面明确提示“录制期间保持亮屏”。这是前台科研采集条件，不是自然息屏/后台稳定能力。

head写screen_policy，tail写screen_observation；异步释放与原传感器取消共用封口屏障。缺方法、原生失败或3秒无回调则不开始采集；释放未确认会告警。API回调成功不能独立证明物理屏幕状态。

```powershell
node collection/watch-s5-probe/tools/build_foreground_recorder_source.cjs
python collection/watch-s5-probe/tools/analyze_foreground_export.py INPUT.txt --output NEW_DIRECTORY
```

旧profiles、包、记录不改。已在本机通过107个Node及37个Python检查并完成实际源格式RPK、同证书/圆标/四能力核验；S5安装与保亮运行仍待真机，不能继承0.4.2的通过状态。按[首次协议](../../../../docs/protocols/2026-10-16-s5-foreground-first-run.md)先只核首页，再10秒、60秒不触屏，原件通过后才到5分钟。
