# 参考音频候选验收入口

`reference_audio_gate.validate_cue_candidates` 验收检测器已有候选，不检测提示音，不产生动作标签或跨端时钟。

输入为归一化单声道 PCM、已有候选、完整必需角色列表、原件 SHA 和从解码 PTS 得到的音频支持区间。能量门 RMS≥1e-4、peak≥1e-3，单候选相关≥0.6；全部角色、顺序、有限数值与时间支持合格才保留候选偏移。幅度门为工程策略；不通过不证明物理无声，通过也不证明存在目标提示。

不合格输出 `accepted=false`、`global_audio_offset_s=null`、`matches=[]`，理由显式保留。合格输出也只是 `candidate_recorded_cues_only`，clock/action_reference/physical_av_sync 始终 false。

后续读取必须调用 `load_cue_support(path, source_sha256=实际原件SHA)`，它拒绝裸候选、拒绝状态与错源。不能直接读历史 `tone-matches.json` 的 offset。SHA 是源绑定声明，不是签名或独立精度证明。

历史 `sustained-video-native/locate_video_cues.py` 是保留的审计脚本，未原地修改；直接使用它仍会输出近零 argmax。DS076 的真实负例已经通过新入口输出到 `output/joint-privacy/2026-10-18-camera-audio-preflight/ds076-old-audio-rejected.json`，原件/旧失败输出保持。

新文件只是候选验收/读取接口，未替换一个通用声事件检测器，也不保证音乐噪声下的检出率。现有短片有能量、没有已认证提示候选，依然不给偏移；后续电脑提示音检查另行验证。
