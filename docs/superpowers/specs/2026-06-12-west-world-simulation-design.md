# 西部世界正式仿真（west_world_test）设计 Spec

> 日期：2026-06-12
> 状态：已与用户确认核心决策，待实现
> 关联文档：
> - 世界观与功能构想：`/Users/hongyuecheng/python-learn/ZJU/西部世界开发计划 35acd6633625809ea53cf4207256e140.md`
> - Recorder MVE 对照实验：`docs/superpowers/specs/2026-06-10-west-world-recorder-mve-design.md`
> - 主参考实现：`examples/story_of_the_stone/`

## 0. 目标与范围

把 `examples/west_world_test` 从"Recorder 对照实验（MVE）"扩展为一个**完整的西部世界多智能体仿真**，与红楼梦（story_of_the_stone）同级别的 example。本期范围：

1. **地图建模**：从 `map_total/西部世界游戏地图.tmx` 提取并人工补全场景真值数据，定义每个地点有什么、地点间空间关系，供 Recorder 初始化和 agent 初始感知。
2. **Recorder 正式版**：基于文本 LLM（用户已确定，不用文生图/VLM 路线）的每地点独立 LocationRecorder，被动调用、状态分块。
3. **框架迁移**：把红楼梦的 registry/configs/主循环/agent 五段式/动作/关系等可复用部分迁移过来，先后端。

**不在本期范围**（后续计划单独立项）：监管者/root 角色、记忆重置与觉醒机制、群聊/偷听对话感知、前端（仅预留接口与数据兼容性）。

已确认的四个核心决策：

| 决策点 | 结论 |
|---|---|
| Recorder 粒度 | **每地点一个独立 Recorder**（状态块 + 共享 LLM 更新逻辑） |
| 第一版激活范围 | **甜水镇核心 ~11 个地点**；全部 ~30 区域均建模为静态数据 |
| 地图真值源 | **JSON/YAML 场景数据文件**；TMX 仅供前端渲染，只修 typo |
| Agent 阵容 | **原作核心 6-7 人**（Dolores、Teddy、Maeve、Clementine、Abernathy、酒保/警长） |

## 1. 地图建模

### 1.1 数据来源与产出方式

- TMX 的 `zones` 对象层含 40 个对象、约 30 个命名区域（属性 `区域名称`），存在缺名字、缺宽高（点对象）、属性 typo（`区域mingc`）的问题。
- 写一次性脚本 `examples/west_world_test/map_total/extract_zones.py`：解析 TMX → 输出 locations 骨架（id/名称/bbox）。缺失项与 typo 在生成时人工修正。
- 描述、物件清单、邻接关系由 AI 结合西部世界原作知识补全，**生成后交用户审核**后定稿。
- 真值文件：`examples/west_world_test/data/map/locations.yaml`。TMX 中仅修正 `区域mingc` → `区域名称` 等 typo，不承载运行时数据。

### 1.2 数据模型

两层结构：`region`（甜水镇 / 帕里亚 / 边境 / 荒野 / 幕后区）→ `location`。每个 location：

```yaml
- id: sweetwater_saloon          # 英文 slug，全局唯一
  name: 甜水镇酒馆                # 中文显示名（与 TMX 区域名称一致）
  region: sweetwater             # 所属 region
  type: interior                 # town | interior | wilderness | backstage
  bbox: [531, 428, 0, 0]         # TMX 像素坐标 (x, y, w, h)，点对象 w/h 为 0，仅供前端
  adjacency: [sweetwater_plaza]  # 可达地点列表（无向图），move 默认 1 tick 一跳
  description: >                 # 静态基础描述：Recorder 初始化 + agent 初见感知
    昏黄的灯光下摆着吧台和几张牌桌，墙上挂着旧照片和通缉令……
  objects:                       # 初始物件，进入 Recorder 的 static/dynamic 块
    - {name: 自动演奏钢琴, note: 循环播放老歌}
    - {name: 墙上的通缉令, note: 三名劫匪的悬赏}
    - {name: 旧照片, hidden: true, secret: 照片上是现代都市的夜景}
  default_occupants: [maeve, clementine]   # 常驻 agent（初始位置参考）
  active: true                   # 第一版仿真是否激活（甜水镇核心为 true）
```

约定：

- `hidden: true` 的物件不出现在 agent 可读的任何块中，其 `secret` 仅存于 Recorder 的 `hidden_notes`，由 `submit_action` 裁决后定向泄露。
- `region` 自身也是一条 location 记录（`type: town/wilderness/backstage`），interior 与所属 region 的街道/广场邻接；region 之间通过道路/火车连接。
- `active: false` 的地点不创建 Recorder，move 到该地点会被拒绝（"道路被封锁了"之类的世界观内理由）。

### 1.3 第一版激活集（甜水镇核心）

甜水镇（街道/广场）、酒馆、警察局、邮局、火车站、旅店、医院、武器铺、裁缝铺、杂货铺、艾伯纳西农场，约 11 个。其余区域（帕里亚、赌场、格斗场、边境小镇/驿站、矿洞、教堂、荒野、幕后区各点等）建模但 `active: false`。

## 2. Recorder 正式版（文本 LLM）

### 2.1 形态

- 纯 Python 类 `LocationRecorder`（`examples/west_world_test/recorder/`），TDD 先行，不依赖 Ray/Redis 可单测（沿用 MVE 的 Phase A/B 两段模式）。
- 内核接入：利用 `mas/environment/components/generic.py` 的动态组件机制，每个激活地点注册一个 `scene:<location_id>` 环境组件，组件内部持有一个 `LocationRecorder` 实例。所有实例共享同一套 LLM 更新 prompt/逻辑。
- MVE 的 `core/`（oracle、text/image representation、metrics）与 `SceneRecorderPlugin` **保留不动**，继续服务对照评测；正式版是新代码，可复用 `core/llm_client.py` 与 `adapters/model_clients.py`。

### 2.2 状态分块（硬编码块名）

| 块名 | 内容 | 变化频率 |
|---|---|---|
| `static_facilities` | 固定设施与场景基调（来自 locations.yaml 的 description + 非 hidden objects） | 几乎不变 |
| `dynamic_objects` | 可移动/可变物品的当前状态（杯子碎了、照片被捡走） | 每 tick 可能变 |
| `present_agents` | 在场 agent 及其公开行为 | 每 tick 变 |
| `recent_events` | 近期公开事件，滚动窗口（默认保留最近 N=10 条） | 每 tick 追加+淘汰 |
| `hidden_notes` | 仅 Recorder 可见的秘密（hidden 物件的 secret、未广播的隐蔽行为记录） | 按需 |

### 2.3 接口（被动调用）

```python
class LocationRecorder:
    def read(self, agent_id: str, chunks: list[str]) -> dict[str, str]
        # perceive 阶段调用；纯文本读取，不调 LLM；agent 决定读哪些块；
        # 永远不返回 hidden_notes。

    def submit_action(self, agent_id: str, action: dict) -> dict
        # invoke 阶段调用；LLM 一次裁决三件事：
        #   permission: 允许/拒绝（含世界观内理由）
        #   private_feedback: 仅对行动者的结果反馈（如照片内容）
        #   broadcast_level: none | location（写入 recent_events）
        # 动作暂存到本 tick 的 pending 队列，结果即时返回。

    def tick_update(self, tick: int) -> None
        # 每 tick 末由环境组件统一调用；把 pending 动作合并，
        # 一次 LLM 调用刷新 dynamic_objects / present_agents / recent_events；
        # 这是唯一的 LLM 状态更新点（防漂移、可测）。

    def agent_enter(self, agent_id: str) -> str   # 返回初见描述（description + 可见物件概览）
    def agent_leave(self, agent_id: str) -> None
```

错误处理：LLM 裁决输出要求 JSON 结构，解析失败重试一次，再失败则降级为"允许、无反馈、不广播"并记 warning 日志；`tick_update` 失败时保留旧状态块并记 error（宁可状态滞后，不可状态损坏）。

### 2.4 信息流（一个 tick）

```
perceive:  agent → read(所在地点, 选定 chunks) + 邻接地点名单（来自 locations 图）
plan:      LLM 自由决策（含软引导的 narrative loop，见 §3.3）
invoke:    动作 → submit_action() → 即时拿到裁决与私密反馈
           move 动作 → agent_leave(旧地点) + agent_enter(新地点)，更新 known_map
tick 末:   每个有 pending 动作的地点跑一次 tick_update()
```

成本特征：`read` 零 LLM 调用；`submit_action` 每动作一次；`tick_update` 每**地点**每 tick 至多一次（无动作的地点跳过）。

## 3. 红楼梦框架迁移（后端）

### 3.1 直接复制改造（预期改动小）

- `registry.py`、`configs/` 全套 yaml（simulation/environment/actions/agents/system/db/models）
- `BasicPodManager`（west_world_test 已有 `WestWorldPodManager.py`，按需对齐）、Controller、`run_simulation.py` 主循环（含 snapshot/rollback 能力）
- relation 环境插件 + `data/relations/` 关系数据（人物换成西部世界）
- communication 动作插件（一对一对话先用 sots 原版；群聊不在本期）
- agent 的 profile/plan/state/reflect 插件（prompt 换西部世界世界观，机制不动）

### 3.2 需要改造的三处

1. **perceive**：从"读全局/关系文本"改为：
   - 调用所在地点 Recorder 的 `read()`（agent 在 prompt 中自选 chunks）；
   - 附加邻接地点名单（仅限 `known_map` 已知项 + 当前位置的直接邻接）；
   - agent state 新增 `location`（当前位置）与 `known_map`（已探索地点集合，靠 `agent_enter` 增长）——实现开发计划中"agent 通过探索获得地图信息"。
2. **move**：从自由文本改为沿 locations 邻接图移动，校验可达性与 `active`，落地时触发 `agent_leave/agent_enter`。
3. **invoke / otheractions**：非对话动作统一经 `submit_action()` 走 Recorder 裁决，私密反馈写回 agent 记忆。

### 3.3 Agent 数据与 narrative loop（软引导）

- `data/agents/profiles.jsonl` / `states.jsonl` 重写为西部世界 6-7 人：Dolores、Teddy、Maeve、Clementine、Peter Abernathy、酒保（或警长）。
- 每人 profile 中以自然语言写入 narrative loop（日常习惯 + 性格基调），plan 阶段仍由 LLM 自由决策。**不用硬脚本**：loop 是行为倾向而非动作表，agent 可被事件扰动而偏离。
- 这是后续觉醒研究的基础：觉醒信号 = 实际轨迹相对 profile 中 loop 的偏离度，loop 已知则偏离可度量。
- MVE 的 `ScriptedPlanPlugin` 与 `data/script.jsonl` 保留，仅服务对照评测，不进入正式仿真入口。

### 3.4 入口与共存

- 正式仿真入口：`examples/west_world_test/run_simulation.py`（新建，参考 sots）。
- MVE 入口 `run_test.py` 不动。两套入口共享 `configs/models_config.yaml` 与 registry（registry 增量注册新插件，不删旧项）。

## 4. 里程碑与验收

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| **M0 地图建模** | extract_zones.py + locations.yaml 全量 ~30 区域 | 脚本可重跑；yaml 通过 schema 校验（id 唯一、adjacency 双向一致、active 集连通）；**用户审核通过** |
| **M1 LocationRecorder** | 纯 Python 实现 + 单测（TDD） | 不依赖 Ray/Redis；read/submit/tick_update/enter/leave 各接口有测试；hidden 信息不泄露的测试通过 |
| **M2 迁移骨架** | configs/registry/主循环/agents 数据/relation/move | 6-7 agent 在甜水镇核心地图上跑 ≥10 tick 不崩；move 沿邻接图、known_map 正确增长；此阶段 perceive 用占位（静态 description），不接 Recorder |
| **M3 接入 Recorder** | perceive/invoke 改造 + 全链路联调 | 跑 ≥20 tick：agent 能读分块、动作被裁决、私密反馈只达行动者、公开事件次 tick 可被他人读到 |
| **M4（可选后置）** | 前端（sots app.js 换西部世界 TMX）；评估指标 | 不阻塞 M0–M3 |

测试策略：M1 全程 TDD；M2/M3 以集成冒烟脚本 + 关键单测（move 校验、known_map、广播可见性）为主。

## 5. 风险与开放问题

- **LLM 成本**：每地点每 tick 一次 tick_update + 每动作一次裁决。激活集 11 地点、7 agent 时量级可控；若后续全图激活需要再评估批处理/缓存。
- **裁决一致性**：submit_action 即时裁决与 tick_update 合并更新之间可能出现叙述不一致（先答应了"捡到照片"，合并时又写丢）。缓解：pending 队列里保存裁决结果原文，tick_update 的 prompt 必须以裁决结果为既定事实。
- **同 tick 动作冲突**（两人同时拿同一物品）：本期按提交顺序裁决，先到先得；真正的并发协商不在本期。
- **开放**：reflect/记忆压缩沿用 sots 现状，觉醒所需的"每日记忆重置"留到下一期设计。
