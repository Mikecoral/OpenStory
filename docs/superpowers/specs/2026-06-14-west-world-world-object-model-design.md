# West World 世界对象模型（WorldObjectRegistry）设计

> 日期：2026-06-14
> 范围：west_world_test 正式仿真 Structured Recorder 的对象所有权重构（DEVELOPMENT_NOTES 的 Todo 1 + Todo 3 的 sim 侧）。
> 不在本 spec：Todo 2（baseline vs structured 对比评估 / 论文评估管线）、MVE `core/` 的解析泛化——另开 spec。

## 1. 背景与根因

正式仿真的 `StructuredLocationRecorder`（`recorder/structured_location_recorder.py`）把对象所有权**锚定在 location**：每个活跃地点是一个独立 kernel 环境组件 `scene_<id>`，各自持有一份 `object_facts` dict，地点之间没有共享存储。DEVELOPMENT_NOTES 记录的四个结构性缺口全部源自这一个事实：

- **无法创造/销毁对象**：对象在构造时一次性从 `location.objects` 播种，之后不可增删（涌现实体如新倒的酒、地上的血无处安放）。
- **跨地点转移结构不可能**：每个 `LocationRecorder` 独占自己的 `object_facts`，recorder 间无通路。
- **`held_by` 不能在 agent 间传递**：被校验死为 `""` 或当前行动者（`structured_location_recorder.py:147`）。
- **丢失 ambient / 非对象环境态**：`dynamic_objects` 现纯由对象派生（`_render_dynamic_objects`），没有光线/气味/声音/氛围这类非对象态。

**根因**：对象所有权锚定在 location 而非 world。修复方向是引入**世界级对象登记表**，让对象成为带 `location_id` / `held_by` 属性的一等实体，每个 recorder 退化为「查询本地点对象的视图」。

**技术前提（已核实）**：所有 `scene_<id>` 组件声明在同一个 `WestWorldEnvironment` 下（`configs_sim/environment_config.yaml`），即同一 pod、同一进程，因此一个共享的 Python 单例 registry 可行，且与既有 `get_world_map()` lru_cache 单例模式一致。

## 2. 设计原则：最大自由 + 可审计

用户明确诉求是让对象生命周期**尽可能自由**。本设计把「自由」与「可约束」拆开：真正限制自由的只有「硬上限 / 模板白名单」，本设计一律不加。其余的结构化手段（显式声明、分配 id、记 provenance、确定性 reducer）**不削减自由度**，只让自由变得确定性、可追溯——这正是论文「结构化表示比自由文本更抗漂移」论点所需。

- 创造：任意对象，无白名单、无模板、无硬上限。
- 销毁：LLM 主动驱动，软删除（无自动 TTL / 衰减）。
- 抗「重复创造」漂移：靠**全可见性**（每次把本地点现有对象完整清单喂给 LLM，引导 patch 现有而非重造），而非限速。

## 3. 核心数据模型 — `WorldObjectRegistry`

新模块 `recorder/world_object_registry.py`。全局单例 `get_object_registry()`，首次访问惰性 `seed_from_world(get_world_map())`。它是**所有地点所有对象的唯一真值源**。

每个对象是一条 `ObjectRecord`（dict 或轻量 dataclass，与现有 dict 风格保持一致）：

| 字段 | 含义 |
|---|---|
| `object_id` | 全局单调分配 `obj_0, obj_1, ...`（registry 分配，不再 per-location） |
| `name` | 中文名 |
| `location_id` | 物理所在地点 |
| `held_by` | 持有者 agent_id 或 `""` |
| `state` | 主状态描述 |
| `hidden` | 隐藏秘密标记 |
| `destroyed` | 软删除标记（保留在 ledger，不从历史抹除） |
| `<free fields>` | LLM 可加任意字段（quantity / container / ...），值为 ≤100 字中文字符串 |
| `provenance` | `{created_by, created_tick, created_action}`，涌现对象审计 |

保留字段（不可被 patch 覆盖）：`object_id`、`name`、`hidden`、`destroyed`、`provenance`。

**不变式**：`held_by != ""` 时 `location_id` 恒等于持有者当前地点。

方法：

- `create(name, location_id, by, tick, action, fields, hidden=False, held_by="") -> object_id`
- `apply_patch(object_id, updates)`
- `destroy(object_id, by, tick)`（软删除）
- `objects_at(location_id, include_hidden=False) -> List[ObjectRecord]`（过滤 destroyed 与 hidden）
- `relocate_holdings(agent_id, to_location)`（把该 agent 名下未销毁对象 `location_id` 迁到新地点）
- `seed_from_world(world_map)`（幂等，仅播种一次；hidden 对象按 `location.hidden_objects()` 播种）
- `snapshot() -> {objects, ledger}`（世界级，含 provenance）
- append-only `ledger`：每条 create/patch/destroy/relocate 带 `before` / `after` / `provenance`

并发：kernel 在 pod actor 内串行执行环境组件方法，registry 是普通单例，无需加锁。

## 4. `StructuredLocationRecorder` 退化为「视图」

不再自己持有 `object_facts`。它锚定一个 `location_id`，所有对象读写转调 registry：

- 读：`registry.objects_at(self.location.id)`；`_render_dynamic_objects` 改为从 registry 当前视图渲染本地点对象。
- 写：通过 registry 的 `create` / `apply_patch` / `destroy` / `relocate_holdings`。
- legacy 文本 `LocationRecorder`（`WW_RECORDER_MODE=legacy`）**完全不动**，registry 只支撑 structured 模式。

`ambient` 作为本地点的自由文本块存在 recorder 的 `chunks` 里（ambient 天然 per-location），可被 LLM 整体重写，且纳入 readable chunks 供 perceive 读取。

## 5. 动作提议 schema（`submit_action`）

LLM 输出在原有裁决字段上新增三段（`new_objects` / `destroy` / `ambient`）：

```json
{ "permission": true, "reason": "", "private_feedback": "...",
  "broadcast_level": "none|location", "event_summary": "",
  "patches":     [{"object_id": "obj_3", "state": "新状态"}],
  "new_objects": [{"name": "地上的血", "state": "暗红一滩", "held_by": ""}],
  "destroy":     ["obj_5"],
  "ambient":     "（可选）整体氛围/光线/气味/声音的自由文本" }
```

处理流程（`structured_location_recorder.submit_action`）：

1. 构 prompt：喂入本地点**可见对象完整清单 + 当前事实 + ambient + 隐藏秘密 + 在场 agent 列表**。
2. LLM 提议 → 校验（见 §6）→ 若 `permission=false` 则丢弃所有写操作。
3. 按 `new_objects` → `patches` → `destroy` 顺序经 registry 确定性应用；`ambient` 整体替换。
4. 记 `fact_ledger`（recorder 侧的动作级 ledger，保留 before/after 与 judgement，与 registry 的对象级 ledger 并存）。
5. `event_summary` 进 `recent_events`；重渲染 `dynamic_objects`。

裁决/解析失败仍降级为 `FALLBACK_JUDGEMENT`（`permission=false` 时不写）。

## 6. 校验规则

- `patches`：`object_id` 必须存在且属于本地点、未 destroyed、非 hidden；不可改保留字段；值为 ≤100 字字符串。
- `new_objects`：`name` 必填；可带任意自由字段；`hidden` 一律置 false（隐藏对象只由地图播种，LLM 不能造隐藏物）；registry 分配 id 并记 provenance（`created_by`=行动者，`created_tick`=tick，`created_action`=action_text）。无白名单、无上限。
- `destroy`：id 必须存在且属于本地点、未 destroyed、非 hidden。
- `held_by`（patches / new_objects 中）：`∈ {"", 行动者, 本地点在场的任意 agent}`，从 recorder 的 `present_agents` 取。递给不在场者校验失败（物理上不该成立）。
- 隐藏对象：永不出现在 patches / new_objects / destroy；秘密只通过 `private_feedback` 渐进揭示，对象状态不迁移（沿用现有行为）。
- 单条非法 patch/destroy：丢弃该条但不让整个动作失败（沿用现有「隐藏对象 patch 丢弃」的宽容策略）；结构性错误（patches 非数组等）才整体拒绝。

## 7. 跨地点转移机制

持有的对象**跟随持有者移动**：

- `invoke.apply_move`（`WestWorldInvokePlugin.py`）成功后，调 `registry.relocate_holdings(agent_id, target)`，把该 agent 名下所有未销毁对象 `location_id` 迁到新地点。
- **删除** structured recorder 现 `agent_leave` 里 `_release_holdings`「丢弃持有物」的行为——那是旧 location-anchored 模型的补丁，新模型下持有物随人走，不再凭空掉落。
- 放下（`held_by=""`）则对象留在当前地点。
- agent 移动到非活跃 / 无 scene 的地点：对象仍由 registry 跟踪，只是暂不被任何活跃 scene 视图渲染，重新进入活跃地点时自然可见。

## 8. 审计与快照（为论文铺路）

- registry 的 `snapshot()` 暴露整 registry + 完整对象级 ledger（create/patch/destroy/relocate，带 before/after + provenance）。
- `run_simulation` 每 tick 落盘**世界级对象快照**（新增 `world_objects_snapshots.jsonl` 或并入现有 internal 快照），论文用来量化：涌现对象数量、转移链、对象级漂移。
- scene snapshot 仍给本地点对象视图（向后兼容现有 `scene_snapshots_*.jsonl`）。

## 9. 测试（TDD）

新增 / 改动单测：

- `test_world_object_registry.py`：create / patch / destroy（软删除）/ relocate_holdings / objects_at 可见性与 destroyed 过滤 / provenance / seed 幂等 / id 全局单调。
- `StructuredLocationRecorder` as-view：submit_action 的 new_objects / patches / destroy / ambient 路径；held_by 在场校验；跨地点跟随（结合 relocate_holdings）。
- 世界级 snapshot / ledger 结构。
- 现有依赖 `object_facts` 内部结构的测试（`test_structured_location_recorder.py` 等）随之改造为查 registry。

## 10. 已定的设计选择（实现时遵循）

- 对象 id **全局**分配，非 per-location。
- 销毁用**软删除**（`destroyed=true`，留 ledger），无自动 TTL / 衰减。
- `ambient` 作为可被 LLM 整体重写的**自由文本块**，per-location，存 recorder chunks。
- registry **首次访问惰性 seed**，幂等。
- 抗漂移靠**全可见性**引导，不加创造上限 / 模板白名单。
- legacy 文本 Recorder 与 MVE `core/` 不在本次改动范围。

## 11. 实现顺序建议

1. `WorldObjectRegistry` + 单测（纯 Python，无需 Ray/Redis）。
2. `StructuredLocationRecorder` 改为 registry 视图 + 新 schema + 校验 + 单测。
3. `invoke.apply_move` 接 `relocate_holdings`；移除旧 `_release_holdings` 丢弃逻辑。
4. 世界级 snapshot 落盘接入 `run_simulation` + `simulation_logging`。
5. 改造现有受影响测试；跑全量回归。
6. 短 tick 烟雾跑（`WW_MAX_TICKS` 小值）人工核对涌现/转移/ambient 行为。
