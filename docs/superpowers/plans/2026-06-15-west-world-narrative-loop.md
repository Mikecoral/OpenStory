# West World — Narrative Loop（每日 loop + 每 tick 反思 replan）实现计划

> 创建：2026-06-15
> 状态：设计待评审（尚未写代码）
> 参考实现：`examples/story_of_the_stone`（红楼梦：12 时辰 daily plan + reflect replan）

## 1. 背景与目标

### 问题
10-tick 仿真观测到 **13 个角色全程零 `move`**（130 次 `do`，0 次 `move`）。根因：west_world 的 plan 是「每 tick 让 LLM 现场自由决策」，profile 里的 `narrative_loop` 只作为一句软提示，LLM 每刻只被问「你现在做什么」，自然就地 `do`，缺少「该去哪、该走哪条路线」的结构约束。5 个角色因此全程孤立无互动。

### 目标
引入《西部世界》原作的 **Narrative Loop**：每个角色有一套每日循环脚本（带地点路线和时段意图），驱动角色按 loop 移动、相遇、推进叙事。机制参考 sots 的「每日定 plan + 每 tick 反思 + 有变故改剩余 plan」。

### 核心取舍（已与用户敲定）
**折中模型：loop 给骨架，每刻仍即兴。**
- loop 决定**人去哪、做哪类事**（解决零移动、制造相遇）。
- LLM 仍每 tick 基于 `percept` 决定**这一刻具体怎么演**（保住已涌现的叙事亮点：威廉觉醒弧、父女哲学对话）。

## 2. 决策汇总

| 维度 | 选择 | 影响 |
|---|---|---|
| plan 范式 | **折中**：loop 作软骨架，每 tick LLM 即兴 detail | invoke 不用改；只改 plan + reflect |
| 一天长度 | **6 tick / 天** | loop 分 6 段；对齐现有 `WW_REFLECT_INTERVAL=6`，记忆总结正好每天一次 |
| 每日重置 | **做**：host teleport 回 loop 起点 + 清短期记忆 | 还原原作；guest 不重置 |
| 觉醒挂钩 | **先不挂** | 本轮只交付 loop+replan；awakening 留到后续 A 阶段 |

## 3. 核心设计：三组件协作

sots 的三组件分工映射到 west_world（6 tick = 1 天，每 tick = 1 个「时段」）：

```
天首 tick（tick % 6 == 0）
  ├─ [每日重置] host: teleport 回 loop 起点 + 清短期记忆（见 §6）
  └─ plan 组件: 调 LLM 从 narrative_loop(+长期记忆) 生成当天 6 段 daily_loop

每个 tick
  ├─ perceive: （不变）recorder 主导感知
  ├─ plan:     取当前时段 loop 条目 → 作为软骨架注入 prompt → LLM 即兴决定 do/move/stay + detail
  ├─ invoke:   （不变）执行 decision；move 复用 apply_move
  ├─ state:    （不变）
  └─ reflect:  累积短期记忆 + 天边界总结（已有）
              + [新增] _should_replan: 判断有无重大变故 → replan 当天剩余时段
```

时段命名（6 段）：`清晨 / 上午 / 正午 / 下午 / 傍晚 / 夜晚`，对应 `tick % 6 == 0..5`。

## 4. 数据结构

### 4.1 profile 新增字段（`data/agents/profiles_sim.jsonl`）
```jsonc
{
  "agent_type": "host",   // "host" | "guest"；guest = william/logan，不参与每日重置
  // narrative_loop 保持自然语言不变，作为编写固定 loop 表的素材
  "daily_loop": [ /* 6 段固定 loop 表，预写，见 §7.1 示例 */ ]
}
```
> 理由：`role` 是中文职业串，用字符串匹配判断 guest 不稳。显式 `agent_type` 更清晰。
> `daily_loop` 预写在 profile（固定脚本），每天拷进 state 作当天工作副本。

### 4.2 state 新增字段（经 `BasicStatePlugin` 的通用 set_state/get_state）
```jsonc
{
  "current_day": 0,
  "loop_origin": "sweetwater_train_station",  // 每日重置回归点 = 初始 location，首 tick 记录
  "daily_loop": [ /* 当天工作副本：天首从 profile 固定表拷入；replan 只改当天剩余段 */ ],
  "replan_log": []   // [{day, tick, from_segment, reason}]，复用 sots 同名概念，供事后审计
}
```

## 5. 分模块实现步骤

### 5.1 plan 组件（`WestWorldPlanPlugin.py`）—— 主改动
**A. 载入 daily_loop（固定表，已定）**
原作 host 的 loop 是**固定脚本、每天精确重演**，因此 **loop 不每天 LLM 生成，而是预写在 profile 里、每天照搬**。
- 预写位置：`profiles_sim.jsonl` 每个角色新增 `daily_loop` 字段（6 段固定表，见 §4.1）。
- 触发：`current_tick % 6 == 0` 时，把 profile 的固定 `daily_loop` 拷进 state（供当天 replan 临时改写，次日重置回固定表）。
- **校验**：每段 `location` 必须是合法地图地点 id（数据校验，写表时一次性查）。
- 与原作对应：固定表=日常脚本，replan=偶发打断，每日重置=次日复位重演。

**B. 每 tick 注入软骨架**（改 `render_plan_prompt`）
- 取当前段 `seg = daily_loop[current_tick % 6]`。
- 在现有 PLAN_PROMPT 里加一段「## 你今天的计划」：
  ```
  此刻是{segment}，按你的日常你本应在「{seg.location}」{seg.intent}。
  - 若你不在那里：可以用 move 朝它前进（一步一格，可能要走几刻）。
  - 若你已在那里：do 你这一刻具体在做什么。
  - 这是软引导，眼前若有更要紧的事（冲突/对话/异常），你可以偏离。
  ```
- **保留即兴**：decision 仍由 LLM 自由产出 `do/move/stay` + detail。loop 只改变「倾向」，不强制。

### 5.2 reflect 组件（`WestWorldReflectPlugin.py`）—— 加 replan
现有「短期记忆累积 + 天边界总结」保留。新增（参考 sots `BasicReflectPlugin._should_replan` / `_replan_remaining`）：
- **`_should_replan(current_tick)`**：当 `current_tick % 6 < 5`（当天还有剩余段）时，把「这一刻发生的事（decision+feedback）+ 当天 loop 剩余段」喂 LLM，判定布尔 + 理由（重大变故才改：如冲突、被卷入他人剧情、关键目标失败）。
- **`_replan_remaining(current_tick, reason)`**：调 plan 组件重写 `daily_loop` 中 `current_segment+1..5` 的剩余段，前面已执行段不动，追加 `replan_log`。
- 执行顺序：在现有 `execute` 里，记忆累积之后、天边界总结判断处一并做（同一组件内，省一次 state 往返）。

> 注意：sots 的 replan 在 reflect 组件里调 `plan_plugin.replan_remaining_plans`。west_world 同样可由 reflect 经 `agent.get_component("plan").get_plugin()` 调用 plan 的 replan 方法。

### 5.3 invoke 组件 —— **不改**
`apply_move` + scene 通知（agent_leave/agent_enter/record_event/relocate_holdings）已能处理 loop 驱动的移动。plan 输出 `action=move, target=loop地点`，invoke 照常执行。

### 5.4 state 组件 —— 仅加字段访问
`daily_loop` / `current_day` / `loop_origin` / `replan_log` 走通用 set_state/get_state，必要时加便捷方法（`get_daily_loop` / `set_daily_loop` / `add_replan_event`，后者 sots 已有同名可借鉴）。

## 6. 每日重置（host only）

### 触发位置
`WestWorldPodManager.step_agent` 三段 barrier 的 **reflect 之后**，当 `(current_tick + 1) % 6 == 0`（即当天最后一个 tick 结束）触发日切，使**下一天 tick 的 perceive 基于起点位置**。新增 `step_day_reset` 阶段方法。

> 备选位置：plan 组件天首逻辑开头。否决理由——perceive 在 plan 之前已基于旧位置感知，会造成「感知旧位置、却已 teleport」的错位。放在前一天 reflect 之后最干净。

### 重置内容（仅 `agent_type == "host"`）
1. **位置 teleport**：`location → loop_origin`。复用 invoke 的底层：`scene.agent_leave(旧)` → `scene.agent_enter(起点)` → `record_event("X 回到了起点")` → `relocate_holdings`。
2. **清短期记忆**：`clear_short_term_memory()`（当天经历抹除）。
3. **保留长期记忆**：reflect 总结进长期记忆的内容**不清**——作为未来觉醒（reveries）的种子。
4. `current_day += 1`。

guest（william/logan）：跳过全部，位置/记忆跨天连续。

## 7. Prompt 草案

### 7.1 固定 loop 表（预写示例，dolores）
loop 不再天首生成，而是预写在 profile。示例（依据 dolores 的 narrative_loop 拆成 6 段）：
```jsonc
"daily_loop": [
  {"segment":"清晨","location":"abernathy_ranch","intent":"在农场醒来，帮父亲料理家务"},
  {"segment":"上午","location":"sweetwater_general_store","intent":"骑马进镇，在杂货铺采购，掉落一只罐头"},
  {"segment":"正午","location":"sweetwater_plaza","intent":"在镇上广场闲逛，与熟人交谈"},
  {"segment":"下午","location":"sweetwater","intent":"在镇上待着，可能遇到 teddy"},
  {"segment":"傍晚","location":"abernathy_ranch","intent":"回农场路上支起画架写生"},
  {"segment":"夜晚","location":"abernathy_ranch","intent":"听父亲讲过去的事"}
]
```
> 相邻段地点需大致可达（靠多 tick move 走完）；teddy 的 loop 应与 dolores 在「下午@sweetwater」交汇，制造原作的相遇。这是手工编排「齿轮咬合」的机会点。

### 7.2 _should_replan（每 tick）
```
你是西部世界角色「{name}」。你今天剩下的计划是：{remaining_loop}
刚刚这一刻发生了：{this_tick_event}（你的动作 + 结果 + 收到的消息）

判断：是否发生了重大变故，需要改写你今天剩余的计划？
（值得改的：被卷入冲突/他人剧情、关键目标失败或达成、出现必须应对的人或事。
 不值得改的：日常对话、环境细节、情绪波动。）

只输出 JSON：{"replan": true/false, "reason": "<简短>"}
```

## 8. 开放问题

### 已定
- **loop 生成方式** → **预写固定结构化 loop 表、每天照搬**（原作 loop 天天一样）。replan 当天临时偏离，每日重置复位。
- **loop_origin** → **取 `states_sim` 初始 location**（dolores=abernathy_ranch、teddy=sweetwater_train_station，已符合原作起点）。

### 已定（续）
- **`agent_type` 字段** → 新增 `agent_type: host|guest`。william/logan=`guest`（不重置、跨天连续），其余 11=`host`。
- **清记忆程度** → 每日重置「清短期、留长期」。长期记忆=未来觉醒的 reveries 种子，保留。
- **固定 loop 表** → 由我依据原作设定（联网核对）+ 现有 `narrative_loop` + 地图邻接起草，见 §11。

> 至此设计全部敲定，计划可执行。下一步：实现各模块 + 写入 §11 loop 表到 `profiles_sim.jsonl`。

## 9. 测试计划

- 单测（不依赖 Ray/Redis，纯函数）：
  - `generate_daily_loop` 输出校验（6 段、location 合法、JSON 解析兜底）。
  - 当前段选取 `daily_loop[tick % 6]`。
  - `_should_replan` 解析与剩余段重写边界（只动 `current_segment+1..5`）。
  - 每日重置：host 重置 / guest 跳过的分支。
- 集成验证：跑 12-tick（2 天）仿真，断言：
  - `move` 次数 > 0，且角色按 loop 地点流动。
  - host 在 tick 6 回到 loop_origin；guest 不回。
  - 出现跨地点相遇（如 teddy 从火车站走向镇上遇到 dolores）。
  - replan_log 在有冲突时被写入。

## 10. 范围边界（本轮不做）

- 觉醒度累积、偏离 loop → awakening（A 阶段）。
- 多 host 叙事链 / quest 动态分配（A 阶段）。
- loop 之间的「齿轮咬合」编排（如 Dolores 掉罐头触发 guest 互动）——本轮靠地点共现自然涌现，不做显式编排。
- 框架级 rollback 对 daily_loop 的快照集成。

## 11. 固定 loop 表草案（13 角色 × 6 段）

时段 = `tick % 6`：0清晨 / 1上午 / 2正午 / 3下午 / 4傍晚 / 5夜晚。
地图星形拓扑：`sweetwater` 为镇枢纽（甜水镇子地点 1 跳直达），`wilderness` 为荒野枢纽。所有相邻段均 ≤1 跳可达。
来源：原作 narrative loop（已联网核对，见文末 Sources）+ 现有 `narrative_loop` 字段 + `locations.yaml` 邻接。

### host（11 名，每日重置回起点）

**dolores**（起点 abernathy_ranch）— 原作核心 loop
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | abernathy_ranch | 在床上醒来，拿画具下楼到门廊见父亲 |
| 上午 | sweetwater | 骑马进镇 |
| 正午 | sweetwater_general_store | 采购，装鞍袋时掉落一只罐头（Teddy 会捡起） |
| 下午 | sweetwater | 在镇上与 Teddy 相会、调情 ★交汇 |
| 傍晚 | abernathy_ranch | 回农场路上支起画架写生 |
| 夜晚 | abernathy_ranch | 听父亲讲过去的事（夜里农场遭袭的原作钩子） |

**teddy**（起点 sweetwater_train_station）— 火车抵达找 Dolores 护送
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_train_station | 乘火车抵达甜水镇 |
| 上午 | sweetwater | 进镇，寻找 Dolores |
| 正午 | sweetwater_saloon | 去酒馆喝一杯 |
| 下午 | sweetwater | 在镇上找到 Dolores 相会 ★交汇 |
| 傍晚 | abernathy_ranch | 护送 Dolores 回农场方向 |
| 夜晚 | sweetwater | 返回镇上，被卷入暴力（原作 Teddy 夜里中枪） |

**maeve**（起点 sweetwater_saloon）— Mariposa 老鸨，定点
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_saloon | 酒馆开张，清点 |
| 上午 | sweetwater_saloon | 招呼客人 |
| 正午 | sweetwater_saloon | 管教侍女、与酒保对账 |
| 下午 | sweetwater_saloon | 二楼凝望远处，若有所思 |
| 傍晚 | sweetwater_saloon | 在入口迎接 Hector，他进门抢保险箱 ★交汇 |
| 夜晚 | sweetwater_saloon | 收拾残局 |

**clementine**（起点 sweetwater_saloon）— 侍女，定点
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_saloon | 在二楼栏杆招呼路人 |
| 上午 | sweetwater_saloon | 陪客、招揽 |
| 正午 | sweetwater_saloon | 在 Maeve 指导下招揽客人 |
| 下午 | sweetwater_saloon | 坐角落发呆，等人靠近 |
| 傍晚 | sweetwater_saloon | 继续陪客 |
| 夜晚 | sweetwater_saloon | 打烊 |

**peter_abernathy**（起点 abernathy_ranch）— 农场主，定点（觉醒征兆角色）
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | abernathy_ranch | 放牛 |
| 上午 | abernathy_ranch | 修理牧栏 |
| 正午 | abernathy_ranch | 在谷仓整理马具 |
| 下午 | abernathy_ranch | 门廊小坐，偶尔凝视远处喃喃自语 |
| 傍晚 | abernathy_ranch | 坐门廊摇椅看日落 |
| 夜晚 | abernathy_ranch | 等女儿回家，讲过去的事 |

**sheriff_pickett**（起点 sweetwater_sheriff）— 警长巡逻路线
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_sheriff | 处理文书、查阅逮捕记录 |
| 上午 | sweetwater | 出门巡逻主街 |
| 正午 | sweetwater_plaza | 广场巡逻、维持秩序 |
| 下午 | sweetwater_saloon | 酒馆门口巡查（可能撞见 rebus 闹事） |
| 傍晚 | sweetwater | 主街收尾巡逻 |
| 夜晚 | sweetwater_sheriff | 回警局整理记录 |

**kissy**（起点 sweetwater_saloon）— 酒保（原创角色），定点
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_saloon | 吧台后擦杯、备酒 |
| 上午 | sweetwater_saloon | 调酒、与客人闲聊打听消息 |
| 正午 | sweetwater_saloon | 招呼常客 |
| 下午 | sweetwater_saloon | 继续调酒、八卦 |
| 傍晚 | sweetwater_saloon | 应付突袭混乱 |
| 夜晚 | sweetwater_saloon | 后厨帮忙收拾 |

**rebus**（起点 sweetwater_plaza）— 地痞（原创角色）
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_plaza | 广场游荡找碴 |
| 上午 | sweetwater_saloon | 酒馆喝酒打牌 |
| 正午 | sweetwater_saloon | 继续豪赌 |
| 下午 | sweetwater_plaza | 街头找碴、勒索路人 |
| 傍晚 | sweetwater_saloon | 回酒馆闹事 |
| 夜晚 | sweetwater | 被赶出酒馆，街上叫骂 |

**hector_escaton**（起点 pariah_casino）— 匪帮头目，奔袭甜水镇
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | pariah_casino | 赌场坐镇，接待来投靠的亡命之徒 |
| 上午 | pariah | 集结帮派 |
| 正午 | wilderness | 骑马奔赴甜水镇 |
| 下午 | sweetwater | 抵达镇外，伺机 |
| 傍晚 | sweetwater_saloon | 突袭 Mariposa 酒馆抢保险箱 ★交汇（Maeve 迎他） |
| 夜晚 | sweetwater | 得手后撤离 |

**armistice**（起点 pariah_fight_pit）— Hector 副手，寸步不离
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | pariah_fight_pit | 检查武器 |
| 上午 | pariah | 与 Hector 集结 |
| 正午 | wilderness | 随 Hector 奔袭 |
| 下午 | sweetwater | 抵达镇外，警戒 |
| 傍晚 | sweetwater_saloon | 参与突袭、守住退路 ★交汇 |
| 夜晚 | sweetwater | 掩护撤离 |

**lawrence**（起点 wilderness）— El Lazo，荒野与 Pariah 间
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | wilderness | 荒野牵马发呆 |
| 上午 | pariah | 回 Pariah 坐镇 |
| 正午 | pariah_casino | 以 El Lazo 身份在赌场派任务 |
| 下午 | pariah | 处理帮派事务 |
| 傍晚 | wilderness | 返回荒野 |
| 夜晚 | wilderness | 篝火旁独坐 |

### guest（2 名，不重置、跨天连续；loop 仅作初始倾向）

**william**（起点 sweetwater_train_station）— 访客新人
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_train_station | 抵达园区 |
| 上午 | sweetwater | 好奇地进镇探索 |
| 正午 | sweetwater_saloon | 去酒馆见识 |
| 下午 | sweetwater | 镇上闲逛，尝试与 host 交谈理解世界 |
| 傍晚 | sweetwater_plaza | 广场观察 |
| 夜晚 | sweetwater | 镇上过夜 |

**logan**（起点 sweetwater_train_station）— 访客老手
| 时段 | 地点 | 意图 |
|---|---|---|
| 清晨 | sweetwater_train_station | 抵达园区 |
| 上午 | sweetwater | 带 William 进镇 |
| 正午 | sweetwater_saloon | 寻欢作乐，怂恿 William |
| 下午 | sweetwater_saloon | 继续享乐 |
| 傍晚 | sweetwater_plaza | 镇上闲逛挑事 |
| 夜晚 | sweetwater_saloon | 酒馆豪赌 |

### ★ 关键交汇点（loop 齿轮咬合，自然涌现非硬编排）
- **下午 @ sweetwater**：dolores × teddy 相会（原作核心爱情线）。
- **傍晚 @ sweetwater_saloon**：hector + armistice 突袭，maeve 迎接（原作抢保险箱）。sheriff 下午在酒馆门口、rebus 傍晚在酒馆——可能撞上突袭。
- **全程同行**：william × logan（原作访客双人组，guest 不重置→可长期黑化弧）。

> 实现时将此表转成 `profiles_sim.jsonl` 每角色的 `daily_loop` 字段（6 条 `{segment, location, intent}`）+ `agent_type`。

---

## Sources（原作设定核对）
- [Dolores Abernathy/The Original — Westworld Wiki](https://westworld.fandom.com/wiki/Dolores_Abernathy/The_Original)
- [Hector Escaton — Westworld Wiki](https://westworld.fandom.com/wiki/Hector_Escaton)
- [Armistice — Westworld Wiki](https://westworld.fandom.com/wiki/Armistice)
- [Maeve Millay/The Original — Westworld Wiki](https://westworld.fandom.com/wiki/Maeve_Millay/The_Original)
- [Clementine Pennyfeather — Westworld Wiki](https://westworld.fandom.com/wiki/Clementine_Pennyfeather)
- [Lawrence — Westworld Wiki](https://westworld.fandom.com/wiki/Lawrence)
- [Mariposa Saloon — Westworld Wiki](https://westworld.fandom.com/wiki/Mariposa_Saloon)
