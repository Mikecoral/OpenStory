# West World 仿真日志体系设计

## 1. 目标

日志系统必须同时满足四种需求：

1. **运行监控**：当前运行到了哪个 tick，卡在哪个阶段或哪个 LLM 请求。
2. **行为解释**：某个 Agent 为什么做出某个决定，其输入、输出和执行结果是什么。
3. **状态回放**：能够恢复任意 tick 的 Agent 与 LocationRecorder 公开状态。
4. **实验审计**：保存运行配置、模型配置、代码版本、完整模型调用和错误信息。

日志系统不负责决定世界状态。结构化 Agent state 和 LocationRecorder state 仍然是仿真真值，
日志只持久化这些事实和状态转移。

## 2. 核心设计

采用三层存储：

### Layer A：原始事实层

只追加、不覆盖。保存每次模型调用、动作执行、状态变化和错误。

这是调试与审计的最终真值来源。

### Layer B：运行快照层

每个 tick 结束后保存完整 Agent 和 Scene 快照，用于快速回放和一致性检查。

快照是派生数据，可以从原始事件重新构建。

### Layer C：访问与报告层

提供：

- CLI 查询；
- 静态 HTML 报告；
- 可选 HTTP API；
- 面向人的摘要文件。

用户不需要直接阅读大型 JSONL 文件。

## 3. 统一关联标识

每条记录必须包含可以串联整个因果链的标识。

| 字段 | 含义 |
|---|---|
| `run_id` | 一次完整仿真运行 |
| `tick` | 仿真 tick，初始化使用 `-1` |
| `event_id` | 每条日志事件的全局唯一 ID |
| `trace_id` | 一次 Agent tick 行为链 |
| `span_id` | 行为链中的单个步骤 |
| `parent_span_id` | 上游步骤 |
| `agent_id` | 相关 Agent |
| `location_id` | 相关地点 |
| `request_id` | 一次 LLM 逻辑请求，跨重试保持不变 |
| `attempt_id` | 一次真实 HTTP/API 尝试 |

一次 Agent 行为链应当可以被完整串联：

```text
perceive
  -> plan.llm.request
    -> plan.llm.attempt[1..N]
  -> plan.decision
  -> invoke.move / invoke.do / invoke.stay
    -> recorder.judge.request
      -> recorder.judge.attempt[1..N]
  -> state.after
```

## 4. 运行目录

默认保存到可长期访问的仓库目录：

```text
examples/west_world_test/output/sim_runs/<run_id>/
├── manifest.json
├── summary.json
├── README.md
├── inputs/
│   ├── configs_sim/
│   ├── data/
│   ├── models_config.redacted.yaml
│   └── prompt_templates/
├── raw/
│   ├── events.jsonl
│   ├── llm_requests.jsonl
│   ├── llm_attempts.jsonl
│   ├── actions.jsonl
│   ├── state_changes.jsonl
│   └── errors.jsonl
├── snapshots/
│   ├── timeline.jsonl
│   ├── agents.jsonl
│   ├── scenes_public.jsonl
│   └── scenes_internal.jsonl
├── views/
│   ├── ticks/
│   │   └── tick_0000.json
│   ├── agents/
│   │   └── dolores.jsonl
│   ├── locations/
│   │   └── sweetwater_saloon.jsonl
│   ├── slow_requests.jsonl
│   └── failures.jsonl
└── report/
    ├── index.html
    └── report.md
```

测试产生的临时目录只用于 pytest。手动运行和正式实验必须写到
`output/sim_runs/<run_id>`，避免测试结束后被系统清理。

## 5. 原始事件 Schema

所有原始事件采用统一 envelope：

```json
{
  "schema_version": "1.0",
  "run_id": "20260613_120000_ab12cd",
  "event_id": "evt_...",
  "event_type": "llm.attempt.completed",
  "timestamp": "2026-06-13T12:00:03.123+08:00",
  "monotonic_ms": 12345,
  "tick": 2,
  "trace_id": "trace_tick2_dolores",
  "span_id": "span_plan_attempt_2",
  "parent_span_id": "span_plan_request",
  "agent_id": "dolores",
  "location_id": "abernathy_ranch",
  "payload": {}
}
```

`event_type` 使用稳定命名空间：

- `run.started`, `run.completed`, `run.failed`
- `tick.started`, `tick.completed`
- `agent.perceive.completed`
- `agent.plan.requested`, `agent.plan.completed`
- `agent.invoke.completed`
- `action.move.completed`, `action.do.completed`, `action.rejected`
- `recorder.judge.requested`, `recorder.judge.completed`
- `recorder.update.completed`
- `llm.attempt.started`, `llm.attempt.completed`, `llm.attempt.failed`
- `snapshot.completed`
- `consistency.failed`

## 6. LLM 输入输出日志

LLM 日志必须拆成“逻辑请求”和“真实尝试”两类。

### `llm_requests.jsonl`

一行代表一次业务层请求，例如 Dolores 在 tick 2 的 plan 请求。

```json
{
  "request_id": "req_...",
  "request_type": "agent_plan",
  "agent_id": "dolores",
  "tick": 2,
  "model": "qwen3.5-flash",
  "input": {
    "prompt": "完整 prompt",
    "percept": {},
    "profile": {},
    "feedback": ""
  },
  "output": {
    "raw_response": "完整原始响应",
    "parsed_response": {},
    "fallback_used": false
  },
  "attempt_count": 2,
  "duration_ms": 5321,
  "usage": {
    "prompt_tokens": 500,
    "completion_tokens": 120,
    "total_tokens": 620
  },
  "status": "success"
}
```

### `llm_attempts.jsonl`

一行代表一次真实 API 尝试，用于解释 tick 2 为什么耗时 1136 秒。

必须记录：

- request/attempt ID；
- provider、model、base URL host；
- 开始和结束时间；
- 单次耗时；
- timeout；
- HTTP status；
- 错误类型和错误摘要；
- 是否被限流；
- retry delay；
- token usage；
- 是否最终被采用。

API key、Authorization header 永远不得写入日志。

## 7. Agent 行为日志

每个 Agent 每 tick 生成一条面向人的行为记录：

```json
{
  "run_id": "...",
  "tick": 2,
  "agent_id": "teddy",
  "location_before": "sweetwater",
  "percept": {},
  "feedback_before": "",
  "decision": {
    "action": "move",
    "target": "sweetwater_saloon",
    "detail": ""
  },
  "invoke_result": {
    "success": true,
    "location_after": "sweetwater_saloon",
    "feedback_after": "..."
  },
  "plan_request_id": "req_...",
  "recorder_request_ids": [],
  "duration_ms": 4200
}
```

这条记录是定位 Agent 行为的首选入口，不需要从全量 state 中手工提取。

## 8. 状态变化日志

除了完整快照，还应保存 diff：

```json
{
  "tick": 2,
  "entity_type": "agent",
  "entity_id": "teddy",
  "changes": {
    "location": {"before": "sweetwater", "after": "sweetwater_saloon"},
    "feedback": {"before": "", "after": "你走进酒馆。"}
  },
  "caused_by_event_id": "evt_action_move..."
}
```

状态 diff 用于：

- 快速回答“这个字段什么时候变化”；
- 生成回放动画；
- 判断 Recorder 漂移；
- 减少查询完整快照的成本。

## 9. 快照与隐私边界

快照分为两类：

### Public

允许提供给 Agent、前端和普通查询接口：

- Agent 公开 state；
- Scene 的 `static_facilities`、`dynamic_objects`、`present_agents`、`recent_events`；
- 不含 `hidden_notes`；
- 不含其他 Agent 的 private feedback；
- 不含完整内部 prompt。

### Internal

仅用于开发与实验审计：

- `hidden_notes`；
- pending actions；
- 完整 prompt/response；
- private feedback；
- traceback。

HTTP API 默认只暴露 Public。访问 Internal 必须显式开启开发模式。

## 10. 面向用户的访问方式

### CLI

提供统一命令：

```bash
python -m examples.west_world_test.log_cli runs
python -m examples.west_world_test.log_cli summary <run_id>
python -m examples.west_world_test.log_cli tick <run_id> 2
python -m examples.west_world_test.log_cli agent <run_id> dolores
python -m examples.west_world_test.log_cli location <run_id> sweetwater_saloon
python -m examples.west_world_test.log_cli slow <run_id> --threshold-ms 10000
python -m examples.west_world_test.log_cli failures <run_id>
python -m examples.west_world_test.log_cli report <run_id>
```

### HTTP API

基于现有 FastAPI 服务扩展：

```text
GET /api/runs
GET /api/runs/{run_id}
GET /api/runs/{run_id}/ticks/{tick}
GET /api/runs/{run_id}/agents/{agent_id}
GET /api/runs/{run_id}/locations/{location_id}
GET /api/runs/{run_id}/llm/requests
GET /api/runs/{run_id}/llm/slow
GET /api/runs/{run_id}/errors
```

### 静态报告

每次运行结束生成 `report/index.html` 与 `report/report.md`，至少展示：

- 运行结果和总耗时；
- 每 tick 各阶段耗时；
- Agent 轨迹；
- Agent 决策摘要；
- Scene 状态变化；
- LLM 调用数量、失败、重试、延迟和真实 token；
- 一致性违规；
- 慢请求排行榜。

## 11. Summary Schema

`summary.json` 是查看一次运行的第一入口：

```json
{
  "status": "completed",
  "ticks": 3,
  "duration_seconds": 1566,
  "agents": 6,
  "locations": 12,
  "actions": {"move": 3, "do": 15, "stay": 0},
  "llm": {
    "logical_requests": 41,
    "attempts": 48,
    "failed_attempts": 7,
    "retries": 7,
    "total_tokens": 123456,
    "p50_latency_ms": 5000,
    "p95_latency_ms": 70000,
    "max_latency_ms": 1130000
  },
  "consistency_violations": 0,
  "scene_errors": 0,
  "slowest_requests": []
}
```

Token 统计必须来自每次请求的增量 usage，不能累加模型路由器的累计 usage。

## 12. 写入与可靠性

- JSONL 每条写入后 flush。
- `manifest.json` 和 `summary.json` 使用临时文件原子替换。
- 原始事件只追加，禁止运行中重写。
- 日志写入失败不得静默忽略；写入 stderr，并把 run 标记为 `logging_degraded`。
- 每个 schema 包含版本号。
- 正常退出、异常退出和中断退出都必须更新 manifest。
- 对大型 prompt 可选 gzip 压缩，但索引中必须保留 request ID 和摘要。

## 13. 实施顺序

### P0：关联与可定位性

1. 引入 `run_id/event_id/trace_id/span_id/request_id/attempt_id`。
2. 在模型路由器记录每次真实 API attempt。
3. 将业务 LLM request 与真实 attempt 分开存储。
4. 修正 token 统计为每请求增量。

### P1：用户访问

1. 实现 `log_cli.py`。
2. 生成 `summary.json` 和 `report.md`。
3. 增加按 Agent、地点、tick 的派生视图。

### P2：实时访问

1. 扩展 FastAPI run 查询接口。
2. 当前运行持续更新 summary。
3. 增加慢请求与错误实时查询。

### P3：回放与前端

1. 从状态 diff 和快照生成轨迹回放。
2. 将 Public Scene 快照接入地图前端。
3. Internal 数据保留开发者访问控制。

## 14. 验收标准

- 能在 30 秒内回答“tick 2 为什么花了 1136 秒，以及是哪一次请求导致的”。
- 能通过一条 CLI 命令查看某 Agent 全部输入、决策、动作和结果。
- 能查看任意 tick 的完整公开世界状态。
- 能从日志定位所有 LLM 重试、超时、限流与 fallback。
- 能准确计算单次运行 token 使用量，不重复累计。
- Public API 和报告中不存在 `hidden_notes`、API key 或 Authorization header。
- 仿真异常退出后，已有日志仍然可读取，manifest 明确标记失败原因。
