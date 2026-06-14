# 反思模块每tick执行实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将反思逻辑改为每tick执行，并新增判断是否需要重新规划剩余hourly plans的功能

**Architecture:** 在ReflectPlugin中移除12 tick周期限制，增加判断是否需要重规划的方法；在PlanPlugin中新增增量规划方法

**Tech Stack:** Python, asyncio, LLM调用

---

## 文件结构

| 模块 | 文件 | 改动 |
|------|------|------|
| 中文版-反思 | `examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py` | 移除周期限制，新增判断和重规划方法 |
| 中文版-规划 | `examples/story_of_the_stone/plugins/agent/plan/BasicPlanPlugin.py` | 新增增量规划方法 |
| 英文版-反思 | `examples/story_of_the_stone_en/plugins/agent/reflect/BasicReflectPlugin.py` | 同上 |
| 英文版-规划 | `examples/story_of_the_stone_en/plugins/agent/plan/BasicPlanPlugin.py` | 同上 |

---

## 实现任务

### Task 1: 修改中文版ReflectPlugin - 移除12 tick周期限制

**Files:**
- Modify: `examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py:31-52`

- [ ] **Step 1: 查看现有execute方法结构**

  当前代码在第31-52行：
  ```python
  if (current_tick + 1) % 12 == 0:
      logger.info(f"[{self.agent_id}][{current_tick}] Starting reflection logic")
      # 完整的反思逻辑
  ```

- [ ] **Step 2: 修改execute方法，移除12 tick周期限制**

  将execute方法中的:
  ```python
  if (current_tick + 1) % 12 == 0:
      logger.info(...)
      # 完整反思逻辑
  ```
  改为:
  ```python
  logger.info(f"[{self.agent_id}][{current_tick}] Starting reflection logic")
  # 完整反思逻辑（移除if判断）
  ```

- [ ] **Step 3: 提交更改**

---

### Task 2: 中文版ReflectPlugin - 新增判断是否需要重新规划方法

**Files:**
- Modify: `examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py`

- [ ] **Step 1: 在BasicReflectPlugin类末尾添加新方法**

  在文件末尾（约489行）添加：
  ```python
  async def _should_replan(self, current_tick: int) -> Tuple[bool, str]:
      """
      判断是否需要重新规划剩余hourly plans
      
      Returns:
          Tuple[bool, str]: (是否需要重新规划, 原因)
      """
      try:
          state_component = self._component.agent.get_component("state")
          state_plugin = state_component.get_plugin()
          
          # 获取当前LongTask
          long_task = await state_plugin.get_long_task()
          if not long_task:
              return (False, "无长期任务")
          
          # 获取上一tick的短期记忆
          short_memories = await state_plugin.get_short_term_memory()
          if not short_memories:
              return (False, "无短期记忆")
          
          last_memory = short_memories[-1]
          last_memory_text = last_memory.get('content', str(last_memory))
          
          # 获取当前hour和剩余计划
          current_hour = current_tick % 12
          remaining_hours = 12 - current_hour - 1
          
          # 获取剩余未执行的hourly plans
          current_day = (current_tick // 12) + 1
          hourly_plans = await state_plugin.get_hourly_plans(day=current_day)
          
          remaining_plans = []
          if hourly_plans:
              for plan in hourly_plans:
                  if len(plan) >= 5 and plan[1] > current_hour:
                      remaining_plans.append(plan)
          
          remaining_plans_text = "\n".join([
              f"- 第{plan[1]}时辰: {plan[0]} (目标:{plan[2]}, 地点:{plan[3]})"
              for plan in remaining_plans
          ]) if remaining_plans else "无剩余计划"
          
          # 构建Prompt
          prompt = f"""你是一个智能体的计划评估助手。请根据近期记忆，判断是否需要重新规划剩余时间。
          
  当前长期任务：{long_task}
  
  上一tick发生的事件：{last_memory_text}
  
  当前时间：第{current_day}天 第{current_hour}个时辰（还剩{remaining_hours}个时辰）
  
  剩余未执行计划：
  {remaining_plans_text}
  
  判断标准：
  1. 上一tick是否发生了重大变化（如重要角色死亡、任务完成、突发事件）
  2. 当前任务是否已经失效或偏离
  3. 继续执行原计划是否合理
  
  请返回（仅返回结论）：
  - 需要重新规划："需要重新规划 | 原因"
  - 无需规划："无需规划 | 原因"
  """
          
          result = await self.model.chat(prompt)
          result = result.strip()
          
          logger.info(f"[{self.agent_id}][{current_tick}] 计划重规划判断结果: {result}")
          
          if "需要重新规划" in result:
              parts = result.split('|')
              reason = parts[1].strip() if len(parts) > 1 else "重大变化发生"
              return (True, reason)
          else:
              return (False, result)
              
      except Exception as e:
          logger.error(f"[{self.agent_id}][{current_tick}] 判断是否需要重规划出错: {e}")
          return (False, f"错误: {str(e)}")
  ```

- [ ] **Step 2: 提交更改**

---

### Task 3: 中文版ReflectPlugin - 新增重规划剩余计划方法

**Files:**
- Modify: `examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py`

- [ ] **Step 1: 在类末尾添加重规划方法**

  在`_should_replan`方法后添加：
  ```python
  async def _replan_remaining(self, current_tick: int, reason: str) -> None:
      """
      重新生成剩余hourly plans
      
      Args:
          current_tick: 当前tick
          reason: 重规划原因
      """
      try:
          state_component = self._component.agent.get_component("state")
          state_plugin = state_component.get_plugin()
          
          profile_component = self._component.agent.get_component("profile")
          profile_plugin = profile_component.get_plugin()
          profile = profile_plugin.get_agent_profile()
          
          # 获取当前LongTask
          long_task = await state_plugin.get_long_task()
          
          # 计算当前hour和剩余hour数
          current_hour = current_tick % 12
          current_day = (current_tick // 12) + 1
          
          logger.info(f"[{self.agent_id}][{current_tick}] 开始重新生成剩余计划，当前第{current_hour}时辰，剩余{12-current_hour-1}个时辰")
          
          # 调用PlanPlugin重新生成剩余计划
          # 需要通过agent.controller调用其他agent的plugin方法
          # 这里直接调用PlanPlugin的方法
          plan_component = self._component.agent.get_component("plan")
          if plan_component:
              plan_plugin = plan_component.get_plugin()
              # 调用新增的replan方法
              await plan_plugin.replan_remaining_plans(
                  agent_id=self.agent_id,
                  current_tick=current_tick,
                  profile=profile,
                  long_task=long_task,
                  start_hour=current_hour + 1
              )
              logger.info(f"[{self.agent_id}][{current_tick}] 剩余计划重规划完成")
          else:
              logger.warning(f"[{self.agent_id}][{current_tick}] 无法获取plan组件")
              
      except Exception as e:
          logger.error(f"[{self.agent_id}][{current_tick}] 重规划剩余计划出错: {e}")
  ```

- [ ] **Step 2: 提交更改**

---

### Task 4: 修改中文版ReflectPlugin - 在execute中调用判断逻辑

**Files:**
- Modify: `examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py:23-52`

- [ ] **Step 1: 在execute方法的反思逻辑末尾添加判断调用**

  在第50行 `logger.info(f"[{self.agent_id}][{current_tick}] Reflection logic execution completed")` 之前添加：
  ```python
  # 判断是否需要重新规划剩余计划
  should_replan, replan_reason = await self._should_replan(current_tick)
  if should_replan:
      logger.info(f"[{self.agent_id}][{current_tick}] 检测到需要重新规划: {replan_reason}")
      await self._replan_remaining(current_tick, replan_reason)
  ```

- [ ] **Step 2: 提交更改**

---

### Task 5: 中文版PlanPlugin - 新增增量规划方法

**Files:**
- Modify: `examples/story_of_the_stone/plugins/agent/plan/BasicPlanPlugin.py`

- [ ] **Step 1: 在类末尾添加增量规划方法**

  在文件末尾（约498行）添加：
  ```python
  async def replan_remaining_plans(self, agent_id: str, current_tick: int, 
                                   profile: Dict[str, Any], long_task: str = None,
                                   start_hour: int = 0) -> List[List[Any]]:
      """
      重新生成剩余hourly plans（从start_hour开始）
      
      Args:
          agent_id: Agent ID
          current_tick: Current tick number
          profile: Agent profile data
          long_task: Agent long-term task
          start_hour: 起始hour（从哪个hour开始生成）
      
      Returns:
          List[List[Any]]: 重新生成的hourly plans列表
      """
      if not profile:
          logger.warning(f"[{agent_id}][{current_tick}] No profile provided, using default configuration")
          profile = {}
      
      # Format character profile
      formatted_profile = self._format_profile_for_prompt(profile)
      
      # Get all characters info
      all_agent_ids = await self._get_all_agent_ids()
      characters_info = self._format_characters_info(all_agent_ids)
      
      # Build prompt - 只生成剩余hour
      remaining_hours = 12 - start_hour
      long_task_info = f"\n\n【长期目标】\n{long_task}" if long_task else ""
      
      # Build location constraint text
      if self._available_locations:
          locations_str = "、".join(self._available_locations)
          location_rule = f"6. 【严格限制】地点必须从以下列表中选择，不能使用列表外的地点：\n   {locations_str}"
      else:
          location_rule = "6. 地点必须是具体的场所（如：怡红院、潇湘馆、荣庆堂等）"
      
      prompt = f"""你是一个智能体的时辰计划生成器。请根据以下人物档案信息，生成该人物剩余{remaining_hours}个时辰的详细行动计划。

【重要背景】
- 你当前处于红楼梦第80回
- 请生成符合当前情节背景的计划

【当前世界角色】
{characters_info}

{formatted_profile}{long_task_info}

古代12时辰对照：
{start_hour}-子时(23-1点)：休息
{start_hour+1}-丑时(1-3点)：深夜
...（继续）

要求：
1. 仅为从第{start_hour}个时辰之后的时间生成计划
2. 行动必须符合人物性格、身份和核心驱动
3. 行动要具体，包含动作、目标人物和地点
4. 【重要建议】大部分时间应该专注于自己的事情
5. 【关键】目标人物必须使用全名
{location_rule}
7. 行动描述控制在10-20字
8. 为每个行动评估重要性分数(1-10)
9. 严格按照JSON格式返回，不要有任何其他文字

请按以下JSON格式返回{remaining_hours}个时辰的计划：
[
  {{"action": "行动描述", "time": {start_hour}, "target": "目标人物", "location": "地点", "importance": 重要性分数}},
  ...
]"""
      
      try:
          if not self.model:
              logger.error(f"[{agent_id}][{current_tick}] Model not initialized, cannot replan")
              raise Exception("Model not initialized")
          
          response = await self.model.chat(prompt)
          response = response.strip()
          
          # Parse JSON response
          import json
          start_idx = response.find('[')
          end_idx = response.rfind(']') + 1
          if start_idx != -1 and end_idx > start_idx:
              json_str = response[start_idx:end_idx]
              plans_data = json.loads(json_str)
          else:
              plans_data = json.loads(response)
          
          # 合并新旧计划：保留已执行的，更新剩余的
          state_component = self._component.agent.get_component("state")
          state_plugin = state_component.get_plugin()
          current_day = (current_tick // 12) + 1
          hourly_plans = await state_plugin.get_hourly_plans(day=current_day)
          
          # 构建新的计划列表
          new_plans = []
          for hour in range(12):
              if hour < start_hour:
                  # 保留已执行的计划
                  if hourly_plans:
                      for plan in hourly_plans:
                          if len(plan) >= 5 and plan[1] == hour:
                              new_plans.append(plan)
                              break
              else:
                  # 添加新生成的计划
                  for plan_data in plans_data:
                      if plan_data['time'] == hour:
                          hourly_plan = HourlyPlan(
                              action=plan_data['action'],
                              time=plan_data['time'],
                              target=plan_data['target'],
                              location=plan_data['location'],
                              importance=plan_data['importance']
                          )
                          new_plans.append(hourly_plan.to_list())
                          break
          
          # 保存新计划
          await state_plugin.set_hourly_plans(new_plans)
          logger.info(f"[{agent_id}][{current_tick}] 剩余计划重规划完成，共{len(new_plans)}个时辰")
          return new_plans
          
      except Exception as e:
          logger.error(f"[{agent_id}][{current_tick}] 重规划剩余计划失败: {e}")
          raise
  ```

- [ ] **Step 2: 提交更改**

---

### Task 6: 同步英文版ReflectPlugin

**Files:**
- Modify: `examples/story_of_the_stone_en/plugins/agent/reflect/BasicReflectPlugin.py`

- [ ] **Step 1: 应用Task 1-4的相同修改到英文版**

  英文版文件结构与中文版类似，执行相同的修改：
  - 移除12 tick周期限制
  - 添加`_should_replan`方法
  - 添加`_replan_remaining`方法
  - 在execute中调用判断逻辑

- [ ] **Step 2: 提交更改**

---

### Task 7: 同步英文版PlanPlugin

**Files:**
- Modify: `examples/story_of_the_stone_en/plugins/agent/plan/BasicPlanPlugin.py`

- [ ] **Step 1: 应用Task 5的修改到英文版**

  添加`replan_remaining_plans`方法到英文版

- [ ] **Step 2: 提交更改**

---

### Task 8: 测试验证

**Files:**
- Test: 运行simulation测试

- [ ] **Step 1: 运行deduction示例验证功能**

  ```bash
  cd examples/story_of_the_stone
  python run_simulation.py
  ```

- [ ] **Step 2: 检查日志输出**

  观察日志中是否每tick都有反思逻辑执行，以及判断是否需要重新规划的Prompt是否正常工作

- [ ] **Step 3: 提交测试结果**

---

## 执行选项

Plan complete and saved to `docs/superpowers/plans/2026-04-13-reflect-per-tick-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?