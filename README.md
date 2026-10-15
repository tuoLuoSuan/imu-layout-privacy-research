# IMU 室内空间隐私研究

研究普通应用实际可读的手机和腕部惯性数据：随观察时间、活动覆盖与交互增加，可以区分多少空间信息；腕部是否增加空间层泄露；未观察区域如何保留不确定性。

当前处于采集入口与可行性验证，尚无HAR、轨迹、布局推断或防护效果结果。GitHub最终承载整项研究，App是采集模块。当前远程只用于私有源码备份。

| 材料 | 入口与状态 |
|---|---|
| 统一研究合同 | [CCF-A合同与流程](docs/research/2026-10-14-research-contract-v1.md)、[主张—证据矩阵](docs/research/claim-evidence-matrix.md)，明确待验证主张与继续门槛 |
| 数据合同 | [字段/质量字典](docs/data/phone-v1-data-dictionary.md)、[空会话模板](templates/session-context-v1.template.json)，真实补充记录另存 |
| 当前状态 | [PROJECT_STATE.md](PROJECT_STATE.md)，区分已验证、未知与下一步 |
| 手机采集 | [IMU采集App](collection/phone-imu-recorder/README.md)：0.2.2，双通道、频率请求、单条删除、手动ZIP导出 |
| 腕部原型 | [9Pro探针](collection/band9pro-probe/README.md)：普通快应用加速度原型，S5入口与出口仍待真机验证 |
| 环境 | [Ubuntu脚本](environment/setup_ubuntu.sh)、[CPU依赖](environment/requirements-cpu.txt)，ML与ROS分离 |
| 研究路线 | [路线v2](docs/superpowers/plans/2026-10-13-ccfa-imu-layout-research-roadmap-v2.md)，历史规划，当前进度以项目状态为准 |
| 完整研究交付 | [交付清单](docs/research/2026-10-14-完整研究成果交付与下一步.md)：协议、数据合同、模型、实验、图表、论文与网站 |
| 雷达参考准备 | [新参考工具](environment/lidar/README.md)、[下一次协议](docs/protocols/2026-10-15-reference-and-phone-pilot.md)：离线已测，ROS/机位/几何仍待验 |
| 展示 | [本地六页工作台](showcase/README.md)：人工三维示意、信号、XGBoost说明、采集准备与成果 |
| 版本与证据 | [复现/备份说明](docs/reproducibility/README.md)、[冻结App清单](docs/reproducibility/frozen-app-0.2.2.json) |
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
