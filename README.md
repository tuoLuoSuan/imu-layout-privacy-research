# IMU 室内空间隐私研究

研究普通应用实际可读的手机和腕部惯性数据：随观察时间、活动覆盖与交互增加，可以区分多少空间信息；腕部是否增加空间层泄露；未观察区域如何保留不确定性。

当前安装候选为手机0.2.4＋插件0.2.4＋S5手表0.2.5，插件和手表需配套更新。旧组合两条20秒连续实录已核完整性，新候选真机停止重连仍待验证；接下来先补区域/录像参考，雷达按评价需要启用。RoNIN/PDR和联合评价脚手架已有，没有独立轨迹精度、真实oracle、腕部空间增益、布局或防护结论。GitHub承载经检查的私有源码与说明，App是其中的采集模块。

当前入口与证据边界见[2026-10-20联合快照](docs/reproducibility/joint-suite-2026-10-20.md)。历史冻结材料继续保留；本机完整实验日志与原始记录不随源码同步。

| 材料 | 入口与状态 |
|---|---|
| 统一研究合同 | [CCF-A合同与流程](docs/research/2026-10-14-research-contract-v1.md)、[主张—证据矩阵](docs/research/claim-evidence-matrix.md)，明确待验证主张与继续门槛 |
| 数据合同 | [字段/质量字典](docs/data/phone-v1-data-dictionary.md)、[空会话模板](templates/session-context-v1.template.json)，真实补充记录另存 |
| 当前状态 | [联合快照](docs/reproducibility/joint-suite-2026-10-20.md)；[PROJECT_STATE.md](PROJECT_STATE.md)为历史冻结正文，本机后续完整实验日志不上传 |
| 当前采集入口 | [IMU联合采集安装组合](collection/imu-capture-suite/README.md)、[使用卡](collection/imu-capture-suite/安装与使用.md)：手机/表/插件同身份更新，手机一次导出整包；20秒与1/2/5/10分钟 |
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
