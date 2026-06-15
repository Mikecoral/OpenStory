# West World 多 pod 世界权威 + Recorder 主导感知 + 全激活扩编 Implementation Plan

> 日期：2026-06-15
> 配套设计决策见记忆 `west-world-next-redesign`；依赖现有 `2026-06-14-west-world-world-object-model.md` / `2026-06-14-west-world-tick-atomic-recorder-design.md`。
> 本计划范围 = **E（全激活+扩编）+ P（pod 并发 A2）+ R（recorder 主导感知）**。完整 A（觉醒动力学/search 动作）与 B（监管者）是后续计划，本计划只铺好它们要用的字段与基础设施。

## 目标

1. 把 31 个地点全部激活；按西部世界原作把 cast 扩到 ~16–20 个 agent。
2. 让仿真在**多 pod** 下保持世界真值一致——做法是 **A2：专用"世界 pod"独占托管 `scene_*` + `WorldObjectRegistry`，其余 pod 只装 agent**，并接进内核 save/load/snapshot/rollback。
3. 把感知协议从"agent 自选 next_read 拉取"改为 **recorder 按特定 agent 的信息千人千面决定告诉它什么**。

## 关键约束（实现前必读）

- **不可丢集中式 Recorder**：它是研究新意。A2 是把它"嵌进 kernel 既有骨架"，不是换成游离的 World Actor。
- **kernel 一致性**：世界权威必须是一个 pod（pods[0]），因为内核 `save_to_db("all")` 只让 pods[0] 存环境、`load_from_db` 灌所有 pod。世界 pod 之外不得出现第二份世界真值。
- **agent 侧零侵入优先**：agent 五段式里 `controller.run_environment(f"scene_{loc}", ...)` 的调用点尽量不改；改的是 controller 的**路由**与 invoke 里**直接 import registry** 这一处。
- **registry 单例只允许在世界 pod 进程实例化**；任何 agent pod 进程都不得 `import get_object_registry` 直接调。
- **基础在场信息（present_agents / recent_events）对同地点所有人一致**；per-agent 差异只作用于叙事性信息（隐藏物、违和细节、特质显著性）。
- **per-agent 因子固定为 5 个**：location / discovered_ids / awakening / profile 特质 / last_action(含关注点软提示)。energy/mood 暂不纳入。
- 全程 TDD：每个 Task 先写/改测试再实现。基线 `pytest examples/west_world_test/tests -q` 当前 136 passed。

## 实施顺序与依赖

```
P（并发基础，用现有 6 agent 拆 2 pod 验证）→ R（感知协议，仍用 6 agent 验证）→ E（全激活+扩编，规模化）
```
先 P 后 E 的理由：先用已知良好的小场景把最难的多 pod 一致性打通，再规模化；R 改的是感知协议，需在小场景验证后再放大。

---

## File Structure

```
修改：
  examples/west_world_test/WestWorldPodManager.py          # 去 fail-fast；世界 pod 路由
  examples/west_world_test/configs_sim/simulation_config.yaml  # pod_size 调小以强制多 pod
  examples/west_world_test/run_simulation.py               # tick_update 落点 / 世界 pod 驱动
  examples/west_world_test/recorder/world_object_registry.py   # per-agent 可见性；去进程单例风险
  examples/west_world_test/recorder/structured_location_recorder.py # perceive()；per-agent read
  examples/west_world_test/recorder/location_recorder.py   # perceive() 对齐（legacy）
  examples/west_world_test/plugins/environment/scene/LocationRecorderPlugin.py # perceive/relocate 路由方法 + save/load/snapshot
  examples/west_world_test/plugins/agent/perceive/WestWorldPerceivePlugin.py   # 组装 agent_context → 调 perceive
  examples/west_world_test/plugins/agent/invoke/WestWorldInvokePlugin.py       # 去直接 registry import，改路由
  examples/west_world_test/data/map/locations.yaml         # 全 active + wilderness 穿越成本
  examples/west_world_test/data/agents/profiles_sim.jsonl  # 扩编
  examples/west_world_test/data/agents/states_sim.jsonl    # 扩编 + discovered_ids/awakening 字段
  examples/west_world_test/data/relations/relations_sim.jsonl  # 扩编关系
  packages/.../mas/controller/controller.py                # run_environment 本地无则转发 pod_manager（见 P2）
新增：
  examples/west_world_test/tests/test_multi_pod_world.py   # 多 pod 一致性
  examples/west_world_test/tests/test_recorder_perceive.py # per-agent 感知
```

---

# Phase P — pod 并发 A2（世界 pod 权威）

## Task P1：专用世界 pod（agents=[] + 唯一权威）

**改 `WestWorldPodManager`**：删掉"必须恰好一个 pod"的 fail-fast，改成"必须恰好一个**世界 pod**"。

- `init`：在切分 agent 之前，先创建 `pod_0`（`PodConfig(agents=[], environment=configs.environment, ...)`）作为世界 pod；agent 从 `pod_1` 起按 `pod_size` 切分、**不带 environment 组件**（或带但永不驱动）。
- 记录 `self._world_pod = pod_0`。
- `run_environment(component, method, *args)`：永远路由到 `self._world_pod`（替换现在的 `next(iter(...))`）。
- `add_agent`：禁止加进世界 pod；容量判断只在 agent pod 上做。
- 新增 `world_tick_update(tick)`：驱动世界 pod 把所有 active 地点的 `scene.execute(tick)` 跑一遍（见 P5）。

**测试** `test_multi_pod_world.py`：
- 构造 6 agent + `pod_size=3` → 期望 1 世界 pod + 2 agent pod。
- 断言世界 pod 的 agent 数为 0；两个 agent pod 各 3。
- 断言 `run_environment` 命中世界 pod。

> 注：世界 pod `agents=[]` 是否被内核接受要验证——`_create_new_pod` 已用 `agents=[]`，应支持。若 MasPod 在 0 agent 时 init 报错，则改为"世界 pod 带 1 个哑 agent 或复用 pods[0] 兼职"（回退到 A1）。

## Task P2：controller.run_environment 本地缺组件则转发世界 pod

agent pod 里的 controller 现在只查本地 `self._environment`。改成：

```python
# controller.py run_environment
async def run_environment(self, component_name, method_name, *args, **kwargs):
    if self._environment and component_name in self._environment.components:
        return await self._environment.run(component_name, method_name, *args, **kwargs)
    # 本地没有 → 转发给 pod_manager（世界 pod）
    if self._pod_manager:
        return await self._pod_manager.run_environment.remote(
            component_name, method_name, *args, **kwargs)
    raise RuntimeError(f"环境组件 {component_name} 不在本地且无 pod_manager 可转发")
```

这样 agent 侧 `controller.run_environment(f"scene_{loc}", ...)` **一字不改**，自动落到世界 pod。

**测试**：agent pod 的 controller 调 `scene_<loc>.read` → 经 pod_manager 命中世界 pod 的组件、返回正确内容。

## Task P3：去掉 invoke 对全局 registry 的直接 import

invoke 现在 `from ...world_object_registry import get_object_registry` 并直接 `registry.relocate_holdings(...)`——在 agent pod 进程里会拿到**错误的空 registry**。

- 在 `LocationRecorderPlugin` 暴露路由方法（运行在世界 pod，内部访问世界 pod 的 registry 单例）：
  ```python
  async def relocate_holdings(self, agent_id, from_location, to_location): ...
  ```
- invoke 的 move 分支删除 import，改为：
  ```python
  await self._scene_call(controller, new_state["location"], "relocate_holdings",
                         self.agent.agent_id, old_location, new_state["location"])
  ```
- `get_object_registry()` 仍是世界 pod 进程内单例（被所有 `scene_*` 共享），但**仅世界 pod 触碰**。在模块顶部加注释：禁止在 agent 插件 import。

**测试**：双 pod 下，pod_1 的 agent 持物 move 到另一地点，世界 pod registry 的 `held_by`/`location` 正确迁移；agent pod 进程内不存在 registry 实例。

## Task P4：世界状态接入 kernel 存档/回溯

- 实现 `LocationRecorderPlugin.save_to_db / load_from_db`（现为 no-op）：把 `WorldObjectRegistry` ledger + scene chunks 序列化进环境 adapter（Redis）。只在世界 pod 执行（其它 pod 无 scene 组件，天然跳过）。
- 给环境 adapter 补 `snapshot(tick)` / `undo(tick)`，使 `PodManager.make_snapshot / rollback_to_tick` 能覆盖世界真值（顺带结掉"框架级 rollback"待办）。
- 复用现有 `world_snapshot()/restore_world_snapshot()`、`snapshot()/restore_snapshot()` 作为序列化内核。

**测试**：snapshot → 改世界 → rollback → 世界态与 registry ledger 完全还原。

## Task P5：tick_update 落点移到栅栏（pre_reflect 与 reflect 之间）

现状：`run_simulation` 在 `step_agent()` **整体结束后**才逐地点 `scene.execute(tick)`。多 pod 下要保证"所有 pod 的 invoke 入队完成"后才裁决，且让 reflect 能看到结果。

- 利用内核 `step_agent` 的两段式（`step_pre_reflect` 全 pod → `step_reflect` 全 pod）。在 `WestWorldPodManager.step_agent` 重写为：
  ```
  gather(pod.step_pre_reflect for all agent pods)   # perceive→plan→invoke(入队)→state
  await self.world_tick_update(tick)                # 世界 pod 一次性裁决所有地点
  gather(pod.step_reflect for all agent pods)       # reflect 可读到 feedback
  ```
- `world_tick_update`：在世界 pod 内对所有 active 地点 `scene.execute(tick)`（地点间可并行）。
- `run_simulation` 删除自己那段逐地点 execute 循环（移交给 step_agent 编排）。

**测试**：双 pod、两 agent 同地点争抢同一物体 → 一次 batch 裁决、结果确定、与单 pod 行为一致（对拍）。

---

# Phase R — Recorder 主导感知

## Task R1：per-agent 状态字段 discovered_ids / awakening

- `states_sim.jsonl` 每个 agent 增 `discovered_ids: []`、`awakening: 0`（默认）。
- 确认 `BasicStatePlugin` 接受任意字段（现有 health/energy/items/known_map 已是自由 KV，应可直接加）。
- 提供读写：`state.get_state("discovered_ids")` / `awakening`。本计划只读取它们做感知过滤；**如何上升/写入留给 A 计划**（search 动作写 discovered_ids；接触 secret 提升 awakening）。测试用 fixture 直接 seed。

**测试**：seed 不同 discovered_ids/awakening 的两个 agent，读取返回正确。

## Task R2：WorldObjectRegistry per-agent 可见性

- `objects_at(location_id, *, viewer_discovered=None, viewer_awakening=0, include_hidden=False)`：
  - 非 hidden 物：照常可见。
  - hidden 物：仅当 `object_id ∈ viewer_discovered` 时对该 viewer 可见。
  - "违和细节"（标 `secret` 且属于 reverie 类，或对象上打 `uncanny` 标）：当 `viewer_awakening ≥ 阈值` 时揭示其 `secret` 文本。
- 保持原 `objects_at(..., include_hidden=False)` 调用兼容（默认参数）。

**测试**：同一地点、同一隐藏物，对"已发现/未发现"两个 viewer 返回不同；awakening 跨阈值前后违和细节出现/消失。

## Task R3：recorder.perceive(agent_id, agent_context)

- 在 `LocationRecorderPlugin` + `StructuredLocationRecorder`（及 legacy 对齐）新增：
  ```python
  async def perceive(self, agent_id: str, agent_context: dict) -> dict:
      # agent_context = {location, discovered_ids, awakening, traits, last_action, focus(可选)}
      # 1. 基础在场信息：present_agents / recent_events —— 全员一致
      # 2. dynamic_objects：用 objects_at(..., viewer_discovered, viewer_awakening) per-agent 渲染
      # 3. ambient / static：按需
      # 4. focus(软提示) 只用于裁剪/排序，不解锁不可见信息
      return percept_chunks
  ```
- `next_read` 退化为 `agent_context.focus`（软关注点），不再决定"能否看到"。
- 保留 `read()` 作为内部/调试只读接口，agent 侧不再直接调。

**测试** `test_recorder_perceive.py`：
- 两 agent 同地点、不同 discovered_ids → present_agents 相同、dynamic_objects 不同。
- focus 只缩小范围、无法解锁未发现的隐藏物。
- agent_context 缺字段时有安全默认。

## Task R4：WestWorldPerceivePlugin 组装 context 并改调 perceive

- perceive 开头仍 `read_feedback`。
- 从本地 state 组装：
  ```python
  agent_context = {
    "location": loc,
    "discovered_ids": await state.get_state("discovered_ids") or [],
    "awakening": await state.get_state("awakening") or 0,
    "traits": (await profile.get_agent_profile() or {}).get("persona_traits"),  # 或从 persona 派生
    "last_action": await state.get_state("current_action"),
    "focus": await state.get_state("next_read"),  # 软提示，可空
  }
  percept["scene"] = await controller.run_environment(f"scene_{loc}", "perceive",
                                                      self.agent.agent_id, agent_context)
  ```
- 删除"agent 直接决定 next_read 即决定可见内容"的旧路径；plan 仍可写 `next_read` 作为软关注点。

**测试**：端到端 perceive 返回个性化 scene；消息消费、feedback 读取不回归。

---

# Phase E — 全激活 + 角色扩编

## Task E1：全激活地图 + wilderness 穿越成本

- `locations.yaml`：把全部 31 地点 `active: true`（含 backstage 5 个——激活≠可达，backstage 无邻接边仍是孤岛，留给 B）。
- wilderness 穿越成本：在 `worldmap/loader.py` 给 `type=wilderness` 的地点加"穿越需 N tick / 触发遭遇"的机制钩子（最小版：经过 wilderness 的 move 消耗 2 tick）。**先做最小版**，遭遇事件留给 A。
- 校验脚本：复用本会话的对称性/连通性检查，确认全激活后主世界连通、backstage 仍孤岛（预期）。

**测试**：`test_worldmap.py` 增"全激活后 active_ids==31、主世界连通分量==26、backstage 分量==5"。

## Task E2：按原作扩编 cast

- `profiles_sim.jsonl` 增角色（host：Kissy / Mariposa 酒保 / Rebus / Hector / Armistice / Lawrence；guest：William / Logan）。staff（Ford/Bernard/Stubbs/Lee/Elsie/Felix/Sylvester）**本计划可先不加**，留给 B（非 host 生命周期）。
- `states_sim.jsonl`：新角色起始点（帕里亚相关角色落 `pariah`/`pariah_casino`；guest 落 `sweetwater_train_station`），且都带 `discovered_ids/awakening`。
- `relations_sim.jsonl`：补关键关系（Hector↔Armistice 同伙、Lawrence↔Pariah、William↔Dolores 等）。
- `simulation_config.yaml`：`pod_size` 设为使总数落到 3–4 个 agent pod 的值（例如 pod_size=5，16 agent → 1 世界 pod + 4 agent pod）。

**测试**：扩编后 `run_simulation` 短跑（`WW_MAX_TICKS=3`）冒烟通过，多 pod 正确分布。

---

# Phase V — 验证与收尾

## Task V1：全量回归
`pytest examples/west_world_test/tests -q` 全绿（含新增 `test_multi_pod_world.py` / `test_recorder_perceive.py`）。

## Task V2：多 pod 端到端冒烟 + 单/多 pod 对拍
- `WW_MAX_TICKS=10` 跑 structured 模式，确认世界态一致、无脑裂、日志/summary 正常。
- 同 seed 下"6 agent 单世界pod+1 agentpod" vs "拆多 agentpod"，关键 timeline 应一致（tick-atomic 保证无顺序依赖）。

## Task V3：回写文档
- `DEVELOPMENT_NOTES.md`：把"多 pod 共享世界真值""框架级 rollback"从待办移入已完成；记录 recorder 主导感知协议。
- CLAUDE.md §7：更新激活地点数（12→31）、agent 规模、pod 模型（世界 pod）。

---

## 风险与回滚

- **0-agent 世界 pod 不被内核接受**（P1）：回退到 A1（pods[0] 兼职 agent + 世界）。路由逻辑不变。
- **跨 pod RPC 延迟**：tick-atomic 已按 tick 聚合，单 tick 内 agent→世界 pod 调用次数有限；若成热点，可在世界 pod 内对 perceive 批量化。
- **感知协议变更回归面大**（R）：保留 `read()` 内部接口，perceive 失败时回落静态感知（现有兜底逻辑保留）。
- **token 成本**：per-agent perceive 不调 LLM（只是确定性过滤渲染），不增 LLM 调用；裁决仍是每地点一次 batch。

## Self-Review 备注（实现者注意）

- 确认 `MasPod` 在 `agents=[]` 下能 init/post_init（P1 的前置验证，先写一个最小 spike）。
- `controller.run_environment` 转发会引入"世界 pod 调自己"的情形（世界 pod 内 agent=0，不会发生 agent→转发；但 world_tick_update 是 pod_manager 直接调世界 pod，OK）。
- per-agent 可见性不要污染世界真值：`objects_at` 的 viewer 过滤是**读路径**，绝不能改 registry 状态。
- `discovered_ids/awakening` 的**写**不在本计划——R 只读。若测试需要变化，用 fixture seed，不要顺手在 R 里实现 search/觉醒。
