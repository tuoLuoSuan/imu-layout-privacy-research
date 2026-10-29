本页计划已执行，当前结果见[自动分组与限制裁定](2026-10-29-unknown-place-groups-checkpoint.md)。固定阈值失败、密度分组正例和无回访误并均保留。以下为实施前冻结的方向与来源。

---

# 下一步：从自动事件发现地点，再推空间原型

2026-10-29。本页是实施方向与停止条件，尚未产生无oracle分组的新结果。本轮未安装或运行下列第三方项目。

## 当前缺口

真实记录已经有自动事件与回访身份的探索线索。典型原型排名则预给了真实地点分组。两者之间要补的是数据关联：哪些不同时间的事件属于同一地点，哪些是新地点、过分割或多报事件；地点总数也不能预告。

先保持相对答案空间。门口起步、绝对朝向、雷达坐标与真实路线不进入攻击输入；雷达只在评价侧使用。模型输出保留未知与多解，后验很尖也不能强迫报房间名称。

## 查过的论文与代码，具体能借什么

本次检索优先机器人学期刊和模式识别顶刊，并核对作者开源实现。Consensus当月额度已用完，改用Crossref DOI记录、arXiv作者摘要和GitHub源文件；没有把这些材料称为已通读出版社全文。

| 来源 | 本轮核验范围 | 可借鉴的部分 | 接入前必须解决 |
|---|---|---|---|
| IJRR 2024：Group-k consistent measurement set maximization | DOI、出版社摘要与作者预印本摘要 | 多个关联之间的一致性；成对一致未必约束充分 | 本文任务、观测模型和我们的二维IMU漂移不同；不能移植其成功率 |
| IEEE RA-L 2020：DOOR-SLAM | DOI、作者预印本摘要、官方仓库入口 | 回环候选生成与错误候选筛查分开处理 | 机器人前端观测不等于只有手机/手表的输入 |
| IEEE RA-L 2020：Graduated Non-Convexity for Robust Spatial Perception | DOI与作者摘要 | 对候选约束使用鲁棒软权重 | 鲁棒后端需要可用的候选和残差模型，不会凭空创造锚或正确分组 |
| IEEE TPAMI 2013：Toward Open Set Recognition | DOI与期刊/年份元数据 | 用于开放集问题定义的后续阅读 | 本轮只核元数据，未据此选择具体拒识器或阈值 |
| Kimera-RPGO，BSD许可 | README、许可、Pcm.h接口，固定commit | 可借鉴错误回环的一致性筛查 | 输入是GTSAM因子图/里程计与候选回环；不是原始IMU地点发现器 |
| CLIPPER，MIT许可 | README、许可、src/clipper.cpp与欧氏距离一致性实现 | 带权几何一致性图，避免过早二值化 | 默认禁止同一目标被重复匹配，且比较未经尺度归一化的距离；不适合直接塞入多次回访 |

CLIPPER代码中的distinctness条件会跳过两个候选共享任一端点的情况；我们的重复访问需要多个事件归到一个地点，直接使用会错误排除这些关系。其默认残差是两边距离差的绝对值；未知模型单位换算率时，必须另外处理尺度，不能默认米制一致。Kimera-RPGO的Pcm.h也明确将输入分成ODOMETRY和LOOP_CLOSURE等因子。这些是实际接口限制。

## 先做一个便宜、能失败的基线

1. 输入只保留自动事件起止、手机相对位置及声明可用的不确定度、两端粗类概率。不给站名、真实地点数、访问顺序脚本、雷达或真实分组。
2. 做未知地点数的分组基线；单例和未归属事件保留，不强塞进四类。门槛在独立合成开发集上选定，测试集不得按真实分组挑门槛。开发与测试使用不同随机数；测试覆盖未参与选择的形状。
3. 按固定物理访次查询评价。分组漏检、多报、错误合并/拆分、回访精确率与召回、分组覆盖率、预测地点数偏差都保留；同次片段匹配不算回访。类别用软证据，硬筛另列对照。
4. 基线可用后再加关联之间的一致性约束。先用小图验证多对一、尺度、相关漂移及对称多解，随后才考虑移植重依赖后端。
5. 接布局时保留族外形状和拒绝作答。选择拒识门槛须用独立开发数据，报告准确率随作答覆盖率变化；本轮三个已看过的族外形状只能作开发诊断，不能再当盲测。

以上是执行顺序，尚不是可直接开大扫描的完整预注册合同。具体分组算法、参数选择规则、随机数划分与未知类测试族应先落盘，再生成正式测试结果。当前固定1秒真实后处理的探索性等级不升级。

## 先过的反例与停止条件

无噪声且有足够重复访问的非对称形状，先检查地点组能否恢复到标签置换等价；零回访和不可区分对称情景应保留未知或等价类。必须测两个真实交互相隔很短时被1秒合并器误并，以及同一次访问被切成多片时的假回访。

若最简无噪声情景仍靠真实地点数或真标签才能恢复分组，先停在实现/可识别性诊断，不扩网格。若仅在知道真实分组时布局排名好，而自动分组后没有收益，就如实保留上界与失败，不把问题转回物理ε。若只有重度筛掉查询才能提高分数，必须同时报告作答覆盖率与固定分母结果。

## 来源

- IJRR，2024，Group-k consistent measurement set maximization via maximum clique over k-uniform hypergraphs for robust multi-robot map merging：[DOI](https://doi.org/10.1177/02783649241256970)，[作者预印本](https://arxiv.org/abs/2308.02674)。
- DOOR-SLAM，IEEE RA-L，2020：[DOI](https://doi.org/10.1109/LRA.2020.2967681)，[作者摘要](https://arxiv.org/abs/1909.12198)，[官方代码](https://github.com/MISTLab/DOOR-SLAM)。
- Graduated Non-Convexity，IEEE RA-L，2020：[DOI](https://doi.org/10.1109/LRA.2020.2965893)，[作者摘要](https://arxiv.org/abs/1909.08605)。
- Toward Open Set Recognition，IEEE TPAMI，2013：[DOI](https://doi.org/10.1109/TPAMI.2012.256)。
- [Kimera-RPGO](https://github.com/MIT-SPARK/Kimera-RPGO/tree/d28b4df0570d642a2bb00e511344ce1110f87519)，commit `d28b4df0570d642a2bb00e511344ce1110f87519`；[Pcm接口](https://github.com/MIT-SPARK/Kimera-RPGO/blob/d28b4df0570d642a2bb00e511344ce1110f87519/include/KimeraRPGO/outlier/Pcm.h)，[BSD许可](https://github.com/MIT-SPARK/Kimera-RPGO/blob/d28b4df0570d642a2bb00e511344ce1110f87519/LICENSE.BSD)。
- CLIPPER，ICRA 2021会议论文，另列为实现参考：[DOI](https://doi.org/10.1109/ICRA48506.2021.9561069)，[固定代码版本](https://github.com/mit-acl/clipper/tree/e514dc29c273837ffdfeebbefbdcb2a93d970969)，[一对一限制](https://github.com/mit-acl/clipper/blob/e514dc29c273837ffdfeebbefbdcb2a93d970969/src/clipper.cpp#L35)，[距离残差](https://github.com/mit-acl/clipper/blob/e514dc29c273837ffdfeebbefbdcb2a93d970969/src/invariants/euclidean_distance.cpp#L28)。

本轮未引入它们的源代码或依赖。若后续复制实现，仍须保留对应版权和许可证。现在不要求用户补录，也不按文献作者的实验数字给本项目承诺。
