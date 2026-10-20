# 联合套件腕部消息与失败语义

本文件只描述当前联合套件的消息边界，不代表物理时钟、动作真值或研究验收。

## 正常路径

1. 手机 `ClockBridgeClient` 每秒向本机 `/bridge` 发送 `native_clock_req`。
2. 插件 `Server::native` 校验 native 会话、序号、nonce 和时钟区间，回复 `native_clock_reply`。
3. 手表发送 `J_HELLO1`，插件绑定 `watch_sid`，回复 `J_HELLO_ACK1`。
4. 手表0.2.4先mkdir本次 `internal://files/s5joint_<native_sid>_<watch_sid>/`，再list该会话目录并确认空，随后写head并订阅。mkdir成功不是独占创建证明；没有全根目录list或自动删除的回退。
5. 每 8 行写一个块文件；约每秒 flush 一次。
6. 停止后写 tail，逐块发 `J_DATA1`，收到 ACK 后发 `J_END1`，插件封口，手机轮询看到 `watch_finished` 后停止并保存。

## 失败路径（0.2.3/0.2.4 源码）

手表文件操作 8 秒无回调，或写入/发送失败时：

- 手表进入 `failed`，保留已经写入的块和 head。
- 若已获得 `native_sid`，发送一次：

```json
{"p":"J_FAIL1","sid":"...","native_sid":"...","stage":"unknown|cancel|hello|mkdir|list|head|block|tail|sensor|transport|clock|tick","error":"...","count":0,"blocks":0,"start_ms":0,"stop_ms":0,"stop_reason":"failure"}
```

- 插件校验字段、阶段、计数和时间，并要求失败包的 `count`/`blocks` 不小于已接收行/块；不一致时拒绝，不写已接受的 `watch_failure`、不发成功 ACK。校验通过后才写 `watch_failure` 并回复 `J_FAIL_ACK1`。
- 插件保持 `watch_sid` 绑定；失败后拒绝新的 `J_DATA1`/时钟包，避免新手表数据混进旧日志。
- 手机下一次轮询收到 `watch_failed=true`、`watch_failure_stage`，停止采集并保留部分记录，不再等 30 分钟上限。
- 若手机仍在录制，先停止并保存；能导出的整包先导出。插件再点“结束连接 · 保留记录”并重新准备，随后可开始新会话。结束后仍可单独保存已有插件日志；本机HTTP导出则需要插件服务可用。

## 兼容

`ClockBridgeRules` 同时接受不带 `watch_failed`/`watch_failure_stage` 的旧插件回复（按未失败处理）。从0.2.2升级0.2.3时需配套升级失败协议；当前安装组合为手机0.2.4＋插件0.2.4＋手表0.2.5。手机0.2.4＋插件0.2.3＋手表0.2.4是此前两条短实录的历史组合，不作为本次更新步骤。

手机0.2.4对 `/bridge` 和 `/export` 请求明确发送 `Connection: close`，避免请求结束后的旧连接跨插件服务编号复用。它没有自动重试或放宽会话校验；503仍为失败，完整错误保留。

DS109后候选为手机0.2.4＋插件0.2.4＋手表0.2.5。新插件将mkdir加入J_FAIL1阶段，并拒绝count/blocks低于已接收行/块的失败包；旧0.2.3插件不接受mkdir阶段，因此不得只更新到新手表。该候选已经构建、尚未安装验证。上传中页面销毁保留本引擎generation与在途ACK；软件模型可继续完成或等待超时报失败，不保证设备销毁JS上下文后还会运行。

## 不做

- 不把 `J_FAIL1` 当成正常结束；失败会话不会有 `J_END1`。
- 不自动删除旧记录，不自动重开会话，不把部分包称为联合完整。
- 不把 `Date.now` 回调到达时间当原生采样时间。

## 失败通知确认与计数

失败包的count/blocks是表端已接纳/排队数量，不是插件已收到数量，也不是已核本地落盘数量。分析输出单列这两套分母；本地持久化数无法从插件日志证明时保持unknown。

表端failure_notification_attempted仅表示尝试发送；身份匹配且saved=true的J_FAIL_ACK1才令failure_notified=true。未确认时不能宣称手机已经停。失败后可接收该ACK，但保持failed。已在途的文件操作可能仍返回，后续排队块不再发起写入；原件不删。

页面在 `recording/finishing/uploading` 阶段被销毁时保留 generation，让在途 ACK 仍能进入引擎；在 `idle/connecting/opening` 销毁时递增 generation，迟到 ready/status 不能开启新会话。页面销毁不是“已保存”证明，最终以本机文件/插件日志为准。
