# 当前入口 2026年11月2日

图文v3已重绘七图，提供中英文矢量图、44条文献、威胁模型与整房区间。GitHub现已公开。论文主线是条件空间可辨性；真实站点归属与物理同步未验收，不写端到端房间恢复。动作主展示为T3八类67/71（94.37%）；九类确认性65/71与同T复看67/71另列，任务不混。

阅读源码：[中文论文](paper/2026-11-02-v3/paper.md)。网站沿用http://127.0.0.1:8765/，仅本机；原始视频/ZIP/日志/模型/签名不入库。下方内容按其批次作为历史记录阅读。

---

<!-- current-evidence-20261101 -->
远端发布与主工作区分开：本轮从独立工作树推送，主工作区未自动pull或合并；本机站点为导出快照。

# 2026-11-01 当前研究进展

已同步DS动作/雷达回传，并从run007b原bag提取自动停留与地点关系；同地7/7，异地误并0/21。历史查询中固定阈值5/5回访、0/2新地点误联；密度法新地点误联2/2，仍不接受为可靠拒识门。这里只是雷达侧接口，不是三设备联合布局恢复。

T3九类联合64/71；八类67/71另列，最早T保留second-look说明。动作原件已恢复；47件内容哈希核对，142个事件的特征与639个冻结臂预测已原件重放一致。完整范围见[本轮进展](docs/research/2026-11-01-ds-action-radar-progress.md)。六类闭库模拟已补齐自动分组衔接：固定阈值28.38%、密度法7.24%，oracle52.46%（单例66.15%、同形20.27%）。不改冻结模型，不上传原始记录或签名。

---

更新于2026-10-29：自动地点分组与布局接入已完成本轮扫描。不给地点数，EqNIO在同一旧记录的八次声明访问上找回7对同地、未误并；RoNIN有2对误并。无回访负对照仍误报10对，不能称可靠新地点识别。882格×1,440次、密度法162个重叠格子完整重放一致，29项测试通过。暂不加门口起点或已知地点数限制，当前不要求补录。

完整入口：[自动分组结果与裁定](docs/research/2026-10-29-unknown-place-groups-checkpoint.md)。工作台当前更新入口为http://127.0.0.1:8766/，仅本机查看。下面保留早期结果；旧文的“下一步自动分组”已经执行，新的缺口是新地点误并与拒答校准。

---

更新于2026-10-29：run006腕部已找回；联合自动回访按固定1秒合并后，RoNIN确定3/5、EqNIO确定4/5另1次未定。新增六原型、事件错误及族外模拟共4,985,280次试验格，全量复跑22文件一致。原型排名给定真实地点分组；真实位置、物理时钟和泛化尚未验收。当前不要求补录。

完整入口：[本轮结果](docs/research/2026-10-29-joint-simulation-checkpoint.md) · [下一步与文献代码](docs/research/2026-10-29-automatic-place-groups-next-step.md)。工作台仅供本机查看（默认端口8765），私有原件不入库。以下较早状态按日期作为历史记录。

---

# IMU 室内空间隐私研究 · 当前入口

更新于2026-10-29：给定窗口的回访结果已明确标为oracle-segmentation upper bound参考条件，自动停留补试和固定四区模拟核查已完成。主时间假设下RoNIN近零速规则四查全中，IMU主规则确认2次、1次未定，全部时间情景与失败项并列。见[结果与限制](docs/research/2026-10-29-automatic-stop-and-simulation-closeout.md)。本轮先收尾实验，没有论文稿；腕部地点增益仍未验证。

更新于2026-10-26。当前软件组合：手机0.2.4、AstroBox插件0.2.5、S5手表0.2.23/code25。
源码在 [联合采集](collection/imu-capture-suite/README.md)，安装包与摘要在 [私有Release](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/tag/joint-watch-v0.2.23)。

当前汇总见 [2026-10-26快照](docs/reproducibility/current-2026-10-26.md)。研究工作台继续在本机8765访问。单人监督标定的动作条件结果与真实宿舍雷达几何参考已经取得，未知布局联合推断尚待功能区标注与评价。
原始IMU、点云、私人素材和签名私钥不入库。下面的旧版本和冻结状态是历史记录，当前软件入口以上面为准。

---

# IMU 室内空间隐私研究

研究普通应用实际可读的手机和腕部惯性数据：随观察时间、活动覆盖与交互增加，可以区分多少空间信息；腕部是否增加空间层泄露；未观察区域如何保留不确定性。

当前日常组合为手机0.2.4＋插件0.2.4＋S5手表0.2.19/code21。用户确认当前使用无阻断，记录清理已完成；手机/插件不换。已有三条路线仅作非盲开发诊断，原四条formal_score=null。先做当前人/房间的配对机制增量，再做未见布局外推；不追加旧三位码或删除实验。RoNIN/PDR和联合评价脚手架已有，没有独立轨迹精度、真实oracle、腕部空间增益、布局或防护结论。GitHub承载经检查的私有源码与说明，App是其中的采集模块。

当前入口与证据边界见[当前日常快照](docs/reproducibility/joint-suite-2026-10-23.md)。历史冻结材料继续保留；本机完整实验日志与原始记录不随源码同步。

| 材料 | 入口与状态 |
|---|---|
| 统一研究合同 | [CCF-A合同与流程](docs/research/2026-10-14-research-contract-v1.md)、[主张—证据矩阵](docs/research/claim-evidence-matrix.md)，明确待验证主张与继续门槛 |
| 数据合同 | [字段/质量字典](docs/data/phone-v1-data-dictionary.md)、[空会话模板](templates/session-context-v1.template.json)，真实补充记录另存 |
| 当前状态 | [联合快照](docs/reproducibility/joint-suite-2026-10-20.md)；[PROJECT_STATE.md](PROJECT_STATE.md)为历史冻结正文，本机后续完整实验日志不上传 |
| 当前采集入口 | [IMU联合采集安装组合](collection/imu-capture-suite/README.md)、[日常使用](collection/imu-capture-suite/日常使用.md)：手机/插件保持，日常表支持勾选删除，手机一次导出整包；20秒与1/2/5/10分钟 |
| 历史采集基线 | 手机独立0.2.2、S5记录器0.4.15与接收插件0.2.5保留；旧S5十分钟9886条为工程证据，不替代新版联合十分钟实测 |
| 环境 | [Ubuntu脚本](environment/setup_ubuntu.sh)、[CPU依赖](environment/requirements-cpu.txt)，ML与ROS分离 |
| 研究路线 | [联合研究边界](docs/reproducibility/joint-suite-2026-10-20.md)：比较时长、覆盖与交互；手机单端只是对照，S5三轴固定，腕部增益仍待验证 |
| 完整研究交付 | [交付清单](docs/research/2026-10-14-完整研究成果交付与下一步.md)：协议、数据合同、模型、实验、图表、论文与网站 |
| 雷达参考准备 | [参考工具](environment/lidar/README.md)：已有15秒静态候选，坐标/几何仍待核，机位改变须重新记录；只进评价侧 |
| 展示 | [本地六页工作台](showcase/README.md)：人工三维示意、信号、XGBoost说明、采集准备与成果 |
| 版本与证据 | [采集软件冻结](docs/reproducibility/collection-freeze-2026-10-17.md)、[精确清单](docs/reproducibility/frozen-collection-2026-10-17.json)，保留旧手机66文件冻结清单 |
| 协作 | [CONTRIBUTING.md](CONTRIBUTING.md)、[源码白名单](repository-policy.json) |

网站启动：在`showcase/`执行`npm ci`、`npm start`，浏览器访问`http://127.0.0.1:8765`。服务只监听本机。源码备份不含真实曲线/截图；缺素材时信号页提示不可用，人工房间和本地CSV导入可用。不要将人工场景理解为恢复结果。

首批源码检查（Python3.10+、Git；网站解析测试另需Node）：

```sh
python -m unittest discover -s tools/tests -v
python tools/repository_guard.py --revision HEAD
python -m unittest discover -s collection/phone-imu-recorder/tools -p 'test_*.py' -v
node --test showcase/tests/data.test.mjs
```

原始IMU/点云、家庭截图、诊断、签名和SSH资料只在受控本地存储，不包含在源码包。历史验收链接可能指向这些未打包材料，不能在干净clone中声称已重现实验。当前没有可公开的完整研究数据集；数据共享和公开发布需另行审查。已验证条件与边界见项目状态，不能把请求120Hz写成实测120Hz，也不能把HAR准确率写成房间恢复精度。
