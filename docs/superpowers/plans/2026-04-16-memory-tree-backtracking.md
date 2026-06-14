# Memory Tree Backtracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a branching memory tree to the deduction simulation UI so users can view any past tick and optionally fork a new simulation branch from it.

**Architecture:** Backend (shared `server.py`) stores per-tick snapshots keyed by `(branch_id, tick)` and a branch metadata list. When a user views a historical tick and presses "Start Simulation", `run_simulation.py` detects the fork condition, calls `pod_manager.restore_all_agents()` to reinject Ray actor state, resets the timer, and continues the loop on a new branch. The frontend renders an SVG tree in a floating modal and reflects history-view mode via a yellow banner.

**Tech Stack:** Python 3.11, Ray (remote actors, `await` on ObjectRef), FastAPI WebSocket, vanilla JS + SVG, same CSS variables as existing UI.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `examples/story_of_the_stone/plugins/agent/state/BasicStatePlugin.py` | Modify | Add `restore_state(snapshot)` |
| `examples/story_of_the_stone_en/plugins/agent/state/BasicStatePlugin.py` | Modify | Same (copy) |
| `examples/story_of_the_stone/BasicPodManager.py` | Modify | Add `restore_all_agents(snapshot)` |
| `examples/story_of_the_stone_en/BasicPodManager.py` | Modify | Same (copy) |
| `packages/agentkernel-distributed/agentkernel_distributed/mas/interface/server.py` | Modify | Branch state, snapshot saving, new WS handlers, `broadcast_branch_event()` |
| `examples/story_of_the_stone/run_simulation.py` | Modify | Fork detection + restore after tick event fires |
| `examples/story_of_the_stone_en/run_simulation.py` | Modify | Same (copy) |
| `examples/story_of_the_stone/frontend/index.html` | Modify | Memory tree button + modal HTML |
| `examples/story_of_the_stone_en/frontend/index.html` | Modify | Same (English text) |
| `examples/story_of_the_stone/frontend/style.css` | Modify | Modal overlay, SVG tree, history banner styles |
| `examples/story_of_the_stone_en/frontend/style.css` | Modify | Same (copy) |
| `examples/story_of_the_stone/frontend/app.js` | Modify | Branch state vars, WS handlers, SVG renderer, modal toggle, history banner |
| `examples/story_of_the_stone_en/frontend/app.js` | Modify | Same (English text) |

---

## Task 1: BasicStatePlugin — add `restore_state()`

**Files:**
- Modify: `examples/story_of_the_stone/plugins/agent/state/BasicStatePlugin.py`
- Modify: `examples/story_of_the_stone_en/plugins/agent/state/BasicStatePlugin.py`

`restore_state` bulk-writes all fields from a snapshot dict into `state_data` and syncs `current_tick`. Apply to both projects identically.

- [ ] **Step 1: Add `restore_state` to deduction's BasicStatePlugin**

  Open `examples/story_of_the_stone/plugins/agent/state/BasicStatePlugin.py`.
  Append the following method at the end of the `BasicStatePlugin` class (after `get_inactive_reason`):

  ```python
  async def restore_state(self, snapshot: dict) -> None:
      """Restore agent state from a tick snapshot dict (used for branching/rollback)."""
      self.state_data.update(snapshot)
      if 'current_tick' in snapshot:
          self.current_tick = snapshot['current_tick']
      logger.info(f"[{self.agent_id}] State restored to tick {self.current_tick}")
  ```

- [ ] **Step 2: Verify no syntax errors**

  Run:
  ```bash
  python -c "import sys; sys.path.insert(0, 'packages/agentkernel-distributed'); \
  exec(open('examples/story_of_the_stone/plugins/agent/state/BasicStatePlugin.py').read())"
  ```
  Expected: no output (no errors).

- [ ] **Step 3: Apply identical change to deduction_en**

  Open `examples/story_of_the_stone_en/plugins/agent/state/BasicStatePlugin.py` and add the same method at the same location.

- [ ] **Step 4: Verify**

  ```bash
  python -c "import sys; sys.path.insert(0, 'packages/agentkernel-distributed'); \
  exec(open('examples/story_of_the_stone_en/plugins/agent/state/BasicStatePlugin.py').read())"
  ```
  Expected: no output.

- [ ] **Step 5: Commit**

  ```bash
  git add examples/story_of_the_stone/plugins/agent/state/BasicStatePlugin.py \
          examples/story_of_the_stone_en/plugins/agent/state/BasicStatePlugin.py
  git commit -m "feat(state): add restore_state() to BasicStatePlugin for rollback support"
  ```

---

## Task 2: BasicPodManager — add `restore_all_agents()`

**Files:**
- Modify: `examples/story_of_the_stone/BasicPodManager.py`
- Modify: `examples/story_of_the_stone_en/BasicPodManager.py`

Adds a Ray-remote method to bulk-restore all agents concurrently using the same semaphore pattern as `collect_agents_data`.

- [ ] **Step 1: Add `restore_all_agents` to deduction's BasicPodManager**

  Open `examples/story_of_the_stone/BasicPodManager.py`.
  Append the following method at the end of the `BasicPodManager` class (after `update_agents_status`):

  ```python
  async def restore_all_agents(self, snapshot: Dict[str, Any]) -> None:
      """
      Restore all agents to a previously saved state snapshot.
      Called during branch fork to roll back Ray actor state.

      Args:
          snapshot: dict of { agent_id -> agent_state_dict } as saved by collect_agents_data
      """
      sem = asyncio.Semaphore(10)

      async def restore_one(agent_id: str, state: dict) -> None:
          async with sem:
              pod = self._agent_id_to_pod.get(agent_id)
              if pod is None:
                  logger.warning(f"restore_all_agents: agent '{agent_id}' not found in pod map")
                  return
              try:
                  await asyncio.wait_for(
                      pod.forward.remote("run_agent_method", agent_id, "state", "restore_state", state),
                      timeout=30.0
                  )
              except asyncio.TimeoutError:
                  logger.warning(f"restore_all_agents: timeout restoring agent '{agent_id}'")
              except Exception as exc:
                  logger.error(f"restore_all_agents: failed for '{agent_id}': {exc}")

      await asyncio.gather(*(restore_one(aid, state) for aid, state in snapshot.items()))
      logger.info(f"restore_all_agents: restored {len(snapshot)} agents")
  ```

- [ ] **Step 2: Verify no syntax errors**

  ```bash
  python -c "
  import sys, types
  sys.path.insert(0, 'packages/agentkernel-distributed')
  # Stub out ray so the file can be parsed without a Ray cluster
  import unittest.mock as mock
  sys.modules['ray'] = mock.MagicMock()
  sys.modules['agentkernel_distributed.mas.pod'] = mock.MagicMock()
  sys.modules['agentkernel_distributed.toolkit.logger'] = mock.MagicMock()
  exec(open('examples/story_of_the_stone/BasicPodManager.py').read())
  print('OK')
  "
  ```
  Expected: `OK`

- [ ] **Step 3: Apply identical change to deduction_en's BasicPodManager**

  Open `examples/story_of_the_stone_en/BasicPodManager.py` and add the same `restore_all_agents` method.

- [ ] **Step 4: Verify deduction_en**

  ```bash
  python -c "
  import sys
  import unittest.mock as mock
  sys.modules['ray'] = mock.MagicMock()
  sys.modules['agentkernel_distributed.mas.pod'] = mock.MagicMock()
  sys.modules['agentkernel_distributed.toolkit.logger'] = mock.MagicMock()
  exec(open('examples/story_of_the_stone_en/BasicPodManager.py').read())
  print('OK')
  "
  ```
  Expected: `OK`

- [ ] **Step 5: Commit**

  ```bash
  git add examples/story_of_the_stone/BasicPodManager.py \
          examples/story_of_the_stone_en/BasicPodManager.py
  git commit -m "feat(pod): add restore_all_agents() to BasicPodManager for rollback support"
  ```

---

## Task 3: server.py — branch state, snapshot saving, new WS handlers

**Files:**
- Modify: `packages/agentkernel-distributed/agentkernel_distributed/mas/interface/server.py`

This is the shared server used by both projects. Changes here apply to both.

### 3a: Add module-level branch state variables

- [ ] **Step 1: Add branch state vars after existing `_snapshot_tick` declaration**

  Find this block in `server.py` (lines ~29-30):
  ```python
  # 内存缓存：存储最新一次 tick 的所有 agent 数据
  _agents_snapshot: Dict[str, Any] = {}
  _snapshot_tick: int = -1
  ```

  Replace with:
  ```python
  # 内存缓存：存储最新一次 tick 的所有 agent 数据
  _agents_snapshot: Dict[str, Any] = {}
  _snapshot_tick: int = -1

  # ── 回溯 / 分支树状态 ──────────────────────────────────────────────────────────
  # 每个 (branch_id, tick) 的完整 agent 状态快照
  _tick_snapshots: Dict[tuple, Dict[str, Any]] = {}
  # 分支元数据列表
  _branches: List[dict] = [
      {"id": 0, "parent_branch_id": None, "fork_tick": 0, "ticks": []}
  ]
  _current_branch_id: int = 0
  # 用户当前查看的历史 tick（-1 = 查看最新）
  _viewing_tick: int = -1
  _viewing_branch_id: int = -1
  ```

- [ ] **Step 2: Verify the file parses cleanly**

  ```bash
  python -c "
  import sys, unittest.mock as mock
  for mod in ['ray','uvicorn','fastapi','redis','redis.asyncio','httpx','pydantic','yaml']:
      sys.modules[mod] = mock.MagicMock()
  sys.modules['agentkernel_distributed.mas.interface.manager'] = mock.MagicMock()
  exec(open('packages/agentkernel-distributed/agentkernel_distributed/mas/interface/server.py').read())
  print('OK')
  "
  ```
  Expected: `OK`

### 3b: Save snapshots in `broadcast_tick_data` and add `broadcast_branch_event`

- [ ] **Step 3: Modify `broadcast_tick_data` to save snapshots and update branch ticks**

  Find `broadcast_tick_data` function (around line 600):
  ```python
  async def broadcast_tick_data(tick: int, agents_data: Dict[str, Any]) -> None:
      ...
      global _agents_snapshot, _snapshot_tick
      _agents_snapshot = agents_data
      _snapshot_tick = tick
  ```

  Replace the `global` line and the two assignment lines with:
  ```python
  async def broadcast_tick_data(tick: int, agents_data: Dict[str, Any]) -> None:
      """
      更新内存快照并通过 WebSocket 广播给所有前端连接。

      Args:
          tick: 当前 tick 编号。
          agents_data: collect_agents_data() 返回的字典。
      """
      import copy
      global _agents_snapshot, _snapshot_tick, _tick_snapshots, _branches, _current_branch_id
      _agents_snapshot = agents_data
      _snapshot_tick = tick

      # 保存快照：以 (branch_id, tick) 为 key
      _tick_snapshots[(_current_branch_id, tick)] = copy.deepcopy(agents_data)
      # 记录当前分支的 tick 列表
      branch = _branches[_current_branch_id]
      if tick not in branch["ticks"]:
          branch["ticks"].append(tick)
  ```
  (Keep the `payload = json.dumps(...)` and `await manager.broadcast(payload)` lines unchanged.)

- [ ] **Step 4: Add `broadcast_branch_event` helper after `broadcast_tick_data`**

  Immediately after the closing of `broadcast_tick_data`, add:

  ```python
  async def broadcast_branch_event(event_type: str, extra: dict = None) -> None:
      """
      广播分支树状态给所有前端，用于 branch_created 和 branch_tree 消息。

      Args:
          event_type: 消息 type 字段，如 'branch_tree' 或 'branch_created'
          extra: 附加字段，合并进广播消息
      """
      payload = {"type": event_type, "branches": _branches, "current_branch_id": _current_branch_id, "current_tick": _snapshot_tick}
      if extra:
          payload.update(extra)
      await manager.broadcast(json.dumps(payload, ensure_ascii=False))
  ```

### 3c: Send branch_tree on new connection

- [ ] **Step 5: In `websocket_endpoint`, after the existing snapshot send, also send `branch_tree`**

  Find this block (around line 392):
  ```python
  # 新连接时推送当前快照
  if _agents_snapshot:
      await websocket.send_text(json.dumps({
          "type": "snapshot",
          "tick": _snapshot_tick,
          "data": _agents_snapshot,
      }))
  ```

  Replace with:
  ```python
  # 新连接时推送当前快照 + 分支树
  if _agents_snapshot:
      await websocket.send_text(json.dumps({
          "type": "snapshot",
          "tick": _snapshot_tick,
          "data": _agents_snapshot,
      }))
  await websocket.send_text(json.dumps({
      "type": "branch_tree",
      "branches": _branches,
      "current_branch_id": _current_branch_id,
      "current_tick": _snapshot_tick,
  }, ensure_ascii=False))
  ```

### 3d: Add `view_tick` and `get_branch_tree` WS message handlers

- [ ] **Step 6: Add new message handlers inside the `while True` loop**

  Find the existing `elif msg_type == "add_agent":` block. Add the following two handlers BEFORE it (after the `elif msg_type == "set_plan":` block):

  ```python
  elif msg_type == "view_tick":
      # 用户点击历史 tick 节点查看（只读，不触发分支）
      tick = msg.get("tick")
      branch_id = msg.get("branch_id")
      if tick is None or branch_id is None:
          continue
      key = (branch_id, tick)
      if key in _tick_snapshots:
          _viewing_tick = tick
          _viewing_branch_id = branch_id
          await websocket.send_text(json.dumps({
              "type": "view_tick_ack",
              "tick": tick,
              "branch_id": branch_id,
              "data": _tick_snapshots[key],
          }, ensure_ascii=False, default=str))
      else:
          await websocket.send_text(json.dumps({
              "type": "view_tick_ack",
              "tick": tick,
              "branch_id": branch_id,
              "data": None,
              "error": "Snapshot not found",
          }))

  elif msg_type == "get_branch_tree":
      await websocket.send_text(json.dumps({
          "type": "branch_tree",
          "branches": _branches,
          "current_branch_id": _current_branch_id,
          "current_tick": _snapshot_tick,
      }, ensure_ascii=False))
  ```

  Also declare `_viewing_tick` and `_viewing_branch_id` as globals at the top of the `view_tick` handler:
  ```python
  elif msg_type == "view_tick":
      global _viewing_tick, _viewing_branch_id
      # ... rest of handler
  ```

- [ ] **Step 7: Final parse check**

  ```bash
  python -c "
  import sys, unittest.mock as mock
  for mod in ['ray','uvicorn','fastapi','redis','redis.asyncio','httpx','pydantic','yaml']:
      sys.modules[mod] = mock.MagicMock()
  sys.modules['agentkernel_distributed.mas.interface.manager'] = mock.MagicMock()
  exec(open('packages/agentkernel-distributed/agentkernel_distributed/mas/interface/server.py').read())
  print('OK')
  "
  ```
  Expected: `OK`

- [ ] **Step 8: Commit**

  ```bash
  git add packages/agentkernel-distributed/agentkernel_distributed/mas/interface/server.py
  git commit -m "feat(server): add tick snapshot storage, branch state, and view_tick/get_branch_tree WS handlers"
  ```

---

## Task 4: run_simulation.py — fork detection and restore

**Files:**
- Modify: `examples/story_of_the_stone/run_simulation.py`
- Modify: `examples/story_of_the_stone_en/run_simulation.py`

After `tick_start_event.wait()` fires, check if the user was viewing a historical tick. If so, restore agents and fork a new branch before continuing the tick loop.

- [ ] **Step 1: Add `broadcast_branch_event` to the import from server**

  Find (in `examples/story_of_the_stone/run_simulation.py`, around line 29):
  ```python
  from agentkernel_distributed.mas.interface.server import start_server, broadcast_tick_data
  ```

  Replace with:
  ```python
  from agentkernel_distributed.mas.interface.server import start_server, broadcast_tick_data, broadcast_branch_event
  import agentkernel_distributed.mas.interface.server as server_module
  ```

- [ ] **Step 2: Add the fork logic immediately after `tick_start_event.clear()`**

  Find (around line 164):
  ```python
  tick_start_event.clear()  # Reset the event, ready for the next tick
  
  tick_start_time = time.time()
  ```

  Replace with:
  ```python
  tick_start_event.clear()  # Reset the event, ready for the next tick

  # ── 回溯分支检测 ─────────────────────────────────────────────────────────────
  if server_module._viewing_tick != -1:
      viewing_tick = server_module._viewing_tick
      viewing_branch_id = server_module._viewing_branch_id
      current_branch = server_module._branches[server_module._current_branch_id]
      max_branch_tick = max(current_branch["ticks"], default=-1)

      if viewing_tick <= max_branch_tick:
          # Fork: restore agents to the viewed tick's snapshot and create new branch
          snapshot_key = (viewing_branch_id, viewing_tick)
          if snapshot_key in server_module._tick_snapshots:
              logger.info(f"【Branch】Forking new branch from tick {viewing_tick} on branch {viewing_branch_id}")
              await pod_manager.restore_all_agents.remote(server_module._tick_snapshots[snapshot_key])
              await system.run('timer', 'set_tick', viewing_tick)

              new_branch = {
                  "id": len(server_module._branches),
                  "parent_branch_id": server_module._current_branch_id,
                  "fork_tick": viewing_tick,
                  "ticks": [],
              }
              server_module._branches.append(new_branch)
              server_module._current_branch_id = new_branch["id"]
              logger.info(f"【Branch】Created branch {new_branch['id']} forking at tick {viewing_tick}")

              await broadcast_branch_event("branch_created", {"new_branch_id": new_branch["id"], "fork_tick": viewing_tick})
          else:
              logger.warning(f"【Branch】Snapshot ({viewing_branch_id}, {viewing_tick}) not found — skipping fork")

      server_module._viewing_tick = -1
      server_module._viewing_branch_id = -1
  # ── 回溯分支检测结束 ──────────────────────────────────────────────────────────

  tick_start_time = time.time()
  ```

  Also add `json` to the imports at the top if not present (it's in stdlib, no pip needed):
  ```python
  import json
  ```

- [ ] **Step 3: Verify deduction/run_simulation.py parses**

  ```bash
  python -c "
  import ast
  with open('examples/story_of_the_stone/run_simulation.py') as f:
      src = f.read()
  ast.parse(src)
  print('AST OK')
  "
  ```
  Expected: `AST OK`

- [ ] **Step 4: Apply same import and fork-detection block to deduction_en**

  Open `examples/story_of_the_stone_en/run_simulation.py` and make the identical two edits (import line + fork-detection block after `tick_start_event.clear()`).

- [ ] **Step 5: Verify deduction_en**

  ```bash
  python -c "
  import ast
  with open('examples/story_of_the_stone_en/run_simulation.py') as f:
      src = f.read()
  ast.parse(src)
  print('AST OK')
  "
  ```
  Expected: `AST OK`

- [ ] **Step 6: Commit**

  ```bash
  git add examples/story_of_the_stone/run_simulation.py \
          examples/story_of_the_stone_en/run_simulation.py
  git commit -m "feat(sim): add branch fork detection and agent restore in tick loop"
  ```

---

## Task 5: Frontend HTML — memory tree button and modal

**Files:**
- Modify: `examples/story_of_the_stone/frontend/index.html`
- Modify: `examples/story_of_the_stone_en/frontend/index.html`

### deduction (Chinese)

- [ ] **Step 1: Add memory tree button to header-right**

  Find in `examples/story_of_the_stone/frontend/index.html`:
  ```html
  <button id="settingsBtn" class="control-btn settings-btn" onclick="openSettingsModal()"
  ```

  Insert the following button BEFORE the settings button line:
  ```html
  <!-- 记忆树按钮 -->
  <button id="memoryTreeBtn" class="control-btn memory-tree-btn" onclick="toggleMemoryTree()" title="记忆树">
    🌳 <span data-i18n="btn_memory_tree">记忆树</span>
  </button>
  ```

- [ ] **Step 2: Add memory tree modal HTML at the end of `<body>` (before `</body>`)**

  Find the closing `</body>` tag and insert before it:

  ```html
  <!-- ── 记忆树浮动弹窗 ─────────────────────────────────────────────────────── -->
  <div id="memoryTreeOverlay" class="memory-tree-overlay" style="display:none" onclick="handleMemoryTreeOverlayClick(event)">
    <div class="memory-tree-modal" onclick="event.stopPropagation()">
      <div class="memory-tree-header">
        <span class="memory-tree-title">🌳 <span data-i18n="btn_memory_tree">记忆树</span></span>
        <button class="memory-tree-close" onclick="toggleMemoryTree()">✕</button>
      </div>
      <div class="memory-tree-body">
        <!-- 历史查看 banner（查看旧 tick 时显示） -->
        <div id="historyViewBanner" class="history-view-banner" style="display:none">
          ⏪ <span id="historyViewText">正在查看 Tick —</span>
          <span class="history-view-hint">· 点击"开始模拟"将从此处创建新分支</span>
        </div>
        <!-- 图例 -->
        <div class="branch-legend" id="branchLegend"></div>
        <!-- SVG 树形图 -->
        <div class="branch-tree-container">
          <svg id="branchTreeSvg" width="100%" height="200"></svg>
        </div>
        <div class="branch-tree-hint" data-i18n="memory_tree_hint">点击节点可跳转查看 · 从旧 Tick 推进时自动创建新分支</div>
      </div>
    </div>
  </div>
  <!-- ── 历史查看提示条（模拟界面顶部） ──────────────────────────────────────── -->
  <div id="historyModeBanner" class="history-mode-banner" style="display:none">
    <span id="historyModeBannerText">⏪ 正在查看 Tick — · 点击"开始模拟"将从此处创建新分支</span>
    <button class="history-mode-banner-close" onclick="exitHistoryView()">✕ 返回最新</button>
  </div>
  ```

### deduction_en (English)

- [ ] **Step 3: Add button to deduction_en/frontend/index.html**

  Find the settings button in `examples/story_of_the_stone_en/frontend/index.html` and insert before it:
  ```html
  <!-- Memory Tree button -->
  <button id="memoryTreeBtn" class="control-btn memory-tree-btn" onclick="toggleMemoryTree()" title="Memory Tree">
    🌳 Memory Tree
  </button>
  ```

- [ ] **Step 4: Add modal HTML to deduction_en**

  Insert before `</body>`:
  ```html
  <!-- ── Memory Tree Modal ─────────────────────────────────────────────────── -->
  <div id="memoryTreeOverlay" class="memory-tree-overlay" style="display:none" onclick="handleMemoryTreeOverlayClick(event)">
    <div class="memory-tree-modal" onclick="event.stopPropagation()">
      <div class="memory-tree-header">
        <span class="memory-tree-title">🌳 Memory Tree</span>
        <button class="memory-tree-close" onclick="toggleMemoryTree()">✕</button>
      </div>
      <div class="memory-tree-body">
        <div id="historyViewBanner" class="history-view-banner" style="display:none">
          ⏪ <span id="historyViewText">Viewing Tick —</span>
          <span class="history-view-hint">· Click "Apply Tick" to fork a new branch from here</span>
        </div>
        <div class="branch-legend" id="branchLegend"></div>
        <div class="branch-tree-container">
          <svg id="branchTreeSvg" width="100%" height="200"></svg>
        </div>
        <div class="branch-tree-hint">Click a node to view it · Advancing from an old tick auto-creates a new branch</div>
      </div>
    </div>
  </div>
  <div id="historyModeBanner" class="history-mode-banner" style="display:none">
    <span id="historyModeBannerText">⏪ Viewing Tick — · Click "Apply Tick" to fork a new branch</span>
    <button class="history-mode-banner-close" onclick="exitHistoryView()">✕ Back to Latest</button>
  </div>
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add examples/story_of_the_stone/frontend/index.html \
          examples/story_of_the_stone_en/frontend/index.html
  git commit -m "feat(html): add memory tree button and modal structure"
  ```

---

## Task 6: Frontend CSS — modal, tree, and banner styles

**Files:**
- Modify: `examples/story_of_the_stone/frontend/style.css`
- Modify: `examples/story_of_the_stone_en/frontend/style.css`

Add styles at the end of each CSS file. Content is identical between both projects.

- [ ] **Step 1: Append memory tree styles to deduction's style.css**

  Add the following at the very end of `examples/story_of_the_stone/frontend/style.css`:

  ```css
  /* ── 记忆树 Memory Tree ───────────────────────────────────────────────────── */

  .memory-tree-btn {
    background: linear-gradient(135deg, #2a1f4e, #3d2a6e);
    border: 1px solid #7c5cbf !important;
    color: #c9a9f0 !important;
  }
  .memory-tree-btn:hover {
    background: linear-gradient(135deg, #3d2a6e, #5a3d9e);
  }

  .memory-tree-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(3px);
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .memory-tree-modal {
    background: #16233a;
    border: 1px solid #4a6a9a;
    border-radius: 12px;
    width: min(620px, 92vw);
    max-height: 80vh;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .memory-tree-header {
    background: #1e2f47;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #2a3f5a;
    flex-shrink: 0;
  }
  .memory-tree-title {
    color: #c9a9f0;
    font-size: 14px;
    font-weight: bold;
  }
  .memory-tree-close {
    background: none;
    border: none;
    color: #666;
    font-size: 16px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .memory-tree-close:hover { color: #ccc; background: rgba(255,255,255,0.08); }

  .memory-tree-body {
    padding: 14px 16px;
    overflow-y: auto;
    flex: 1;
  }

  .history-view-banner {
    background: rgba(180, 130, 0, 0.15);
    border: 1px solid #a07800;
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 12px;
    color: #e4c97e;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }
  .history-view-hint { color: #a09060; font-size: 11px; }

  .branch-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 10px;
    font-size: 11px;
  }
  .branch-legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    color: #aaa;
  }
  .branch-legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .branch-tree-container {
    overflow-x: auto;
    padding-bottom: 4px;
  }
  #branchTreeSvg { display: block; min-height: 60px; }

  .branch-tree-hint {
    margin-top: 10px;
    font-size: 11px;
    color: #555;
    text-align: center;
  }

  /* 顶部历史查看横幅（悬浮在模拟界面上方） */
  .history-mode-banner {
    position: fixed;
    top: 64px; /* below header */
    left: 50%;
    transform: translateX(-50%);
    z-index: 1500;
    background: rgba(140, 100, 0, 0.92);
    border: 1px solid #c8a020;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    color: #f5e090;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    white-space: nowrap;
    max-width: 90vw;
  }
  .history-mode-banner-close {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.25);
    color: #f5e090;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
  }
  .history-mode-banner-close:hover { background: rgba(255,255,255,0.22); }
  ```

- [ ] **Step 2: Copy identical styles to deduction_en**

  Append the exact same CSS block to `examples/story_of_the_stone_en/frontend/style.css`.

- [ ] **Step 3: Commit**

  ```bash
  git add examples/story_of_the_stone/frontend/style.css \
          examples/story_of_the_stone_en/frontend/style.css
  git commit -m "feat(css): add memory tree modal, branch legend, and history banner styles"
  ```

---

## Task 7: Frontend JS — branch state variables and WS message handlers

**Files:**
- Modify: `examples/story_of_the_stone/frontend/app.js`
- Modify: `examples/story_of_the_stone_en/frontend/app.js`

### Branch colors palette

We'll use a fixed palette of 8 colors cycling for branches:

```javascript
const BRANCH_COLORS = [
  '#ffd700', // branch 0: gold (main)
  '#4fc3f7', // branch 1: sky blue
  '#81c784', // branch 2: green
  '#ff8a65', // branch 3: orange
  '#ce93d8', // branch 4: purple
  '#80deea', // branch 5: cyan
  '#ffb74d', // branch 6: amber
  '#f48fb1', // branch 7: pink
];
```

### Step 1: Add state vars and helper functions

- [ ] **Step 1: Add branch state variables near the top of app.js (after existing `let tickHistory` declarations)**

  Find the block that contains `let tickHistory` or `let currentHistoryIndex` (existing history tracking vars). After them, add:

  ```javascript
  // ── Memory Tree / Branch State ─────────────────────────────────────────────
  const BRANCH_COLORS = [
    '#ffd700','#4fc3f7','#81c784','#ff8a65',
    '#ce93d8','#80deea','#ffb74d','#f48fb1',
  ];
  let branchTree = [];          // branch metadata list from backend
  let currentBranchId = 0;      // which branch is actively simulating
  let viewingTick = -1;         // tick being viewed in history mode (-1 = latest)
  let viewingBranchId = -1;     // branch of the viewed tick
  let isViewingHistory = false; // true when user has jumped to a past tick
  let memoryTreeOpen = false;   // modal visibility
  ```

### Step 2: Add `branch_tree` and `branch_created` handlers in the WebSocket `onmessage`

- [ ] **Step 2: Find the WebSocket `onmessage` handler and add new message type cases**

  Find the section that handles `msg.type === 'tick_update'` or `msg.type === 'snapshot'`. In the same switch/if-else chain, add:

  ```javascript
  } else if (msg.type === 'branch_tree') {
    branchTree = msg.branches || [];
    currentBranchId = msg.current_branch_id ?? 0;
    renderBranchTree();

  } else if (msg.type === 'branch_created') {
    branchTree = msg.branches || [];
    currentBranchId = msg.current_branch_id ?? 0;
    isViewingHistory = false;
    viewingTick = -1;
    viewingBranchId = -1;
    updateHistoryModeBanner();
    renderBranchTree();

  } else if (msg.type === 'view_tick_ack') {
    if (msg.data) {
      viewingTick = msg.tick;
      viewingBranchId = msg.branch_id;
      isViewingHistory = true;
      // Apply historical data to the UI (reuse existing render functions)
      applyAgentsData(msg.data, msg.tick);
      updateHistoryModeBanner();
      renderBranchTree();
    }
  }
  ```

  Note: `applyAgentsData(data, tick)` should be the existing function that updates the UI from agent data (the same logic used when receiving `tick_update`). If the existing code uses a different function name for rendering agents, substitute the correct name.

### Step 3: Add modal toggle and exitHistoryView functions

- [ ] **Step 3: Add the following functions at the end of app.js**

  ```javascript
  // ── Memory Tree Functions ──────────────────────────────────────────────────

  function toggleMemoryTree() {
    memoryTreeOpen = !memoryTreeOpen;
    const overlay = document.getElementById('memoryTreeOverlay');
    if (overlay) overlay.style.display = memoryTreeOpen ? 'flex' : 'none';
    if (memoryTreeOpen) renderBranchTree();
  }

  function handleMemoryTreeOverlayClick(event) {
    if (event.target === document.getElementById('memoryTreeOverlay')) {
      toggleMemoryTree();
    }
  }

  function exitHistoryView() {
    isViewingHistory = false;
    viewingTick = -1;
    viewingBranchId = -1;
    updateHistoryModeBanner();
    // Re-apply the latest tick data
    if (Object.keys(agentsData).length > 0) {
      applyAgentsData(agentsData, currentDisplayTick);
    }
    renderBranchTree();
  }

  function updateHistoryModeBanner() {
    const banner = document.getElementById('historyModeBanner');
    const bannerText = document.getElementById('historyModeBannerText');
    const innerBanner = document.getElementById('historyViewBanner');
    const innerText = document.getElementById('historyViewText');

    if (!banner) return;

    if (isViewingHistory && viewingTick !== -1) {
      // Main UI banner
      banner.style.display = 'flex';
      if (bannerText) bannerText.textContent = `⏪ 正在查看 Tick ${viewingTick} · 点击"开始模拟"将从此处创建新分支`;
      // Modal banner
      if (innerBanner) innerBanner.style.display = 'flex';
      if (innerText) innerText.textContent = `正在查看 Tick ${viewingTick}`;
    } else {
      banner.style.display = 'none';
      if (innerBanner) innerBanner.style.display = 'none';
    }
  }
  ```

  For deduction_en, change the banner text strings:
  - `'⏪ 正在查看 Tick ${viewingTick} · 点击"开始模拟"将从此处创建新分支'`
    → `⏪ Viewing Tick ${viewingTick} · Click "Apply Tick" to fork a new branch`
  - `'正在查看 Tick ${viewingTick}'`
    → `Viewing Tick ${viewingTick}`

- [ ] **Step 4: Commit JS changes so far**

  ```bash
  git add examples/story_of_the_stone/frontend/app.js \
          examples/story_of_the_stone_en/frontend/app.js
  git commit -m "feat(js): add branch state vars, WS handlers, modal toggle, and history banner"
  ```

---

## Task 8: Frontend JS — SVG branch tree renderer

**Files:**
- Modify: `examples/story_of_the_stone/frontend/app.js`
- Modify: `examples/story_of_the_stone_en/frontend/app.js`

The renderer builds an SVG entirely in JS, placing branches in horizontal rows with nodes connected by lines. Fork points use a diamond shape.

- [ ] **Step 1: Add `renderBranchTree()` at the end of app.js (deduction)**

  ```javascript
  function renderBranchTree() {
    const svg = document.getElementById('branchTreeSvg');
    if (!svg) return;
    if (!branchTree || branchTree.length === 0) {
      svg.innerHTML = '<text x="10" y="30" fill="#555" font-size="12">暂无数据</text>';
      return;
    }

    const NODE_R = 10;
    const H_GAP = 64;
    const V_GAP = 56;
    const PAD_X = 40;
    const PAD_Y = 36;

    // Collect all tick numbers across all branches, deduplicate, sort
    const allTicks = [...new Set(branchTree.flatMap(b => b.ticks || []))].sort((a, b) => a - b);
    if (allTicks.length === 0) {
      svg.innerHTML = '<text x="10" y="30" fill="#555" font-size="12">暂无数据</text>';
      return;
    }

    const tickToX = {};
    allTicks.forEach((t, i) => { tickToX[t] = PAD_X + i * H_GAP; });

    // Each branch occupies its own row
    const branchToY = {};
    branchTree.forEach((b, i) => { branchToY[b.id] = PAD_Y + i * V_GAP; });

    const svgWidth = PAD_X * 2 + (allTicks.length - 1) * H_GAP;
    const svgHeight = PAD_Y * 2 + (branchTree.length - 1) * V_GAP;
    svg.setAttribute('viewBox', `0 0 ${svgWidth} ${svgHeight}`);
    svg.setAttribute('height', Math.max(svgHeight, 80));

    // Identify fork points: any tick that is the fork_tick of a child branch
    const forkTicks = new Set(branchTree.filter(b => b.parent_branch_id !== null && b.parent_branch_id !== undefined).map(b => b.fork_tick));

    let html = '';

    // Draw connecting lines
    branchTree.forEach(branch => {
      const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
      const ticks = (branch.ticks || []).slice().sort((a, b) => a - b);
      const y = branchToY[branch.id];

      // If this is a child branch, draw a diagonal line from parent's fork_tick to first tick of this branch
      if (branch.parent_branch_id !== null && branch.parent_branch_id !== undefined && ticks.length > 0) {
        const parentY = branchToY[branch.parent_branch_id];
        const forkX = tickToX[branch.fork_tick] ?? PAD_X;
        const firstX = tickToX[ticks[0]] ?? forkX;
        html += `<line x1="${forkX}" y1="${parentY}" x2="${firstX}" y2="${y}" stroke="${color}" stroke-width="2" opacity="0.7"/>`;
      }

      // Draw horizontal line across all ticks in this branch
      if (ticks.length > 1) {
        const x1 = tickToX[ticks[0]];
        const x2 = tickToX[ticks[ticks.length - 1]];
        html += `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${color}" stroke-width="2"/>`;
      }
    });

    // Draw nodes
    branchTree.forEach(branch => {
      const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
      const ticks = (branch.ticks || []).slice().sort((a, b) => a - b);
      const y = branchToY[branch.id];

      ticks.forEach(tick => {
        const x = tickToX[tick];
        const isCurrentTick = branch.id === currentBranchId && tick === viewingTick && isViewingHistory ? false
          : branch.id === currentBranchId && !isViewingHistory && tick === ticks[ticks.length - 1];
        const isViewing = isViewingHistory && tick === viewingTick && branch.id === viewingBranchId;
        const isFork = forkTicks.has(tick) && branch.id === (branchTree.find(b => b.fork_tick === tick && b.parent_branch_id === branch.id - 1)?.parent_branch_id ?? -999);

        // Determine the current running tick (last tick of current branch)
        const currentBranch = branchTree.find(b => b.id === currentBranchId);
        const lastTickOfCurrentBranch = currentBranch ? Math.max(...(currentBranch.ticks || [0])) : -1;
        const isLiveCurrentTick = branch.id === currentBranchId && tick === lastTickOfCurrentBranch && !isViewingHistory;

        // Click handler data
        const clickHandler = `onClickTreeNode(${branch.id}, ${tick})`;

        if (isViewing) {
          // Dashed purple ring around viewed node
          html += `<circle cx="${x}" cy="${y}" r="${NODE_R + 5}" fill="none" stroke="#a0a0ff" stroke-width="2" stroke-dasharray="4 2"/>`;
        }
        if (isLiveCurrentTick) {
          // Pulsing red ring around live current tick
          html += `<circle cx="${x}" cy="${y}" r="${NODE_R + 4}" fill="none" stroke="#e94560" stroke-width="2" stroke-dasharray="3 2" opacity="0.8"/>`;
        }

        // Node circle
        const nodeStroke = isLiveCurrentTick ? '#fff' : 'rgba(255,255,255,0.4)';
        const nodeStrokeW = isLiveCurrentTick ? 2 : 1;
        const nodeFill = isLiveCurrentTick ? '#e94560' : color;
        html += `<circle cx="${x}" cy="${y}" r="${NODE_R}" fill="${nodeFill}" stroke="${nodeStroke}" stroke-width="${nodeStrokeW}" style="cursor:pointer" onclick="${clickHandler}"/>`;

        // Tick label
        html += `<text x="${x}" y="${y + NODE_R + 14}" text-anchor="middle" fill="${color}" font-size="10" style="cursor:pointer" onclick="${clickHandler}">T${tick}</text>`;
      });
    });

    // Branch labels (right side of each row)
    branchTree.forEach(branch => {
      const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
      const ticks = branch.ticks || [];
      if (ticks.length === 0) return;
      const lastTick = Math.max(...ticks);
      const x = tickToX[lastTick] + NODE_R + 8;
      const y = branchToY[branch.id];
      const label = branch.id === 0 ? '主线' : `分支${branch.id}`;
      html += `<text x="${x}" y="${y + 4}" fill="${color}" font-size="9" opacity="0.7">${label}</text>`;
    });

    svg.innerHTML = html;

    // Update legend
    renderBranchLegend();
  }

  function onClickTreeNode(branchId, tick) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'view_tick', tick, branch_id: branchId }));
    if (memoryTreeOpen) toggleMemoryTree(); // close modal after click
  }

  function renderBranchLegend() {
    const legend = document.getElementById('branchLegend');
    if (!legend || !branchTree) return;
    legend.innerHTML = branchTree.map(branch => {
      const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
      const label = branch.id === 0 ? '主线' : `分支${branch.id}`;
      const active = branch.id === currentBranchId ? ' (当前)' : '';
      return `<div class="branch-legend-item">
        <div class="branch-legend-dot" style="background:${color}"></div>
        <span>${label}${active}</span>
      </div>`;
    }).join('');
  }
  ```

- [ ] **Step 2: Add the same renderer to deduction_en's app.js with English labels**

  Apply the same `renderBranchTree()`, `onClickTreeNode()`, and `renderBranchLegend()` functions to `examples/story_of_the_stone_en/frontend/app.js`, with these text changes:
  - `'暂无数据'` → `'No data'`
  - `'主线'` → `'Main'`
  - `'分支${branch.id}'` → `` `Branch ${branch.id}` ``
  - `'${label}${active}'` active suffix `' (当前)'` → `' (current)'`

- [ ] **Step 3: Verify both files have no obvious syntax errors**

  ```bash
  node --input-type=module < /dev/null  # just checking node is available
  # Visual check: look for balanced braces around the new functions
  grep -n "function renderBranchTree\|function onClickTreeNode\|function renderBranchLegend" \
    examples/story_of_the_stone/frontend/app.js
  grep -n "function renderBranchTree\|function onClickTreeNode\|function renderBranchLegend" \
    examples/story_of_the_stone_en/frontend/app.js
  ```
  Expected: three matching lines in each file.

- [ ] **Step 4: Commit**

  ```bash
  git add examples/story_of_the_stone/frontend/app.js \
          examples/story_of_the_stone_en/frontend/app.js
  git commit -m "feat(js): add SVG branch tree renderer, node click handler, and legend"
  ```

---

## Task 9: Wire `applyAgentsData` reference and request branch tree on connect

**Files:**
- Modify: `examples/story_of_the_stone/frontend/app.js`
- Modify: `examples/story_of_the_stone_en/frontend/app.js`

The `view_tick_ack` handler calls `applyAgentsData(data, tick)`. This must map to the function that currently renders agent data into the UI after a tick. Also, on WebSocket connect, request the branch tree.

- [ ] **Step 1: Find the existing function that renders agent data to the UI**

  Search in app.js for the function called when `tick_update` arrives:
  ```bash
  grep -n "function apply\|tick_update\|agents_data\|applyAgentsData\|renderAgents\|updateAgents" \
    examples/story_of_the_stone/frontend/app.js | head -20
  ```

  Note the actual function name used to apply tick data to the UI.

- [ ] **Step 2: Add `applyAgentsData` shim if needed**

  If the existing function is named differently (e.g., `handleTickUpdate(data)`), add an alias at the end of app.js:

  ```javascript
  // Alias for history view support
  function applyAgentsData(data, tick) {
    // Call the existing tick-render function with the historical data
    // Replace 'handleTickUpdate' with the actual function name found in Step 1
    handleTickUpdate({ data, tick });
  }
  ```

  Also add a module-level variable to track the latest agent data for `exitHistoryView`:
  ```javascript
  let agentsData = {};        // latest tick's agent data
  let currentDisplayTick = -1; // tick number currently displayed
  ```

  Update the existing `tick_update` handler to keep `agentsData` and `currentDisplayTick` up to date:
  ```javascript
  // Inside the tick_update handler, add:
  agentsData = msg.data;
  currentDisplayTick = msg.tick;
  ```

- [ ] **Step 3: Request branch tree on WebSocket open**

  Find the `ws.onopen` handler in app.js. After the existing connection setup code, add:

  ```javascript
  ws.send(JSON.stringify({ type: 'get_branch_tree' }));
  ```

- [ ] **Step 4: Apply same changes to deduction_en**

  Repeat Steps 1–3 for `examples/story_of_the_stone_en/frontend/app.js`.

- [ ] **Step 5: Final commit**

  ```bash
  git add examples/story_of_the_stone/frontend/app.js \
          examples/story_of_the_stone_en/frontend/app.js
  git commit -m "feat(js): wire applyAgentsData, request branch_tree on connect, track agentsData ref"
  ```

---

## Task 10: Manual end-to-end test

No automated test suite exists for the frontend. Verify the feature manually.

- [ ] **Step 1: Start the deduction simulation**

  ```bash
  cd /Users/hongyuecheng/python-learn/OpenStory
  python -m examples.story_of_the_stone.run_simulation
  ```
  Open `http://localhost:8000/frontend/index.html`.

- [ ] **Step 2: Run at least 4 ticks**

  Click "开始推演" then "开始模拟" four times. After each tick, the UI should update and the memory tree button should appear.

- [ ] **Step 3: Open memory tree modal**

  Click "🌳 记忆树". The modal should open showing the main branch with 4 tick nodes (T0–T3). Verify legend shows "主线".

- [ ] **Step 4: Click an old tick node**

  Click T1 in the tree. Expected:
  - Modal closes.
  - Yellow history banner appears at top: "正在查看 Tick 1 · 点击'开始模拟'将从此处创建新分支".
  - UI shows T1's agent states (older data).

- [ ] **Step 5: Fork a new branch**

  Click "开始模拟". Expected:
  - Backend logs: `【Branch】Forking new branch from tick 1...` and `【Branch】Created branch 1 forking at tick 1`.
  - History banner disappears.
  - Tick advances from 1 on the new branch.

- [ ] **Step 6: Open memory tree again**

  Click "🌳 记忆树". Expected:
  - Two branches visible: 主线 (gold) and 分支1 (blue).
  - 分支1 forks from T1 in the diagram.
  - Current position indicated with pulsing red circle on 分支1's latest tick.

- [ ] **Step 7: Test deduction_en**

  Repeat Steps 1–6 for deduction_en:
  ```bash
  python -m examples.story_of_the_stone_en.run_simulation
  ```
  Open `http://localhost:8000/frontend/index.html`.
  Verify English text: "Memory Tree", "Branch 1 (current)", "Viewing Tick N · Click 'Apply Tick' to fork a new branch".

- [ ] **Step 8: Commit if any fixes were made during testing**

  ```bash
  git add -p  # stage only intentional changes
  git commit -m "fix(memory-tree): post-integration fixes from manual testing"
  ```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 5 spec sections covered: UX (Tasks 5–9), backend snapshots (Task 3), WS protocol (Tasks 3–4), plugin restore (Tasks 1–2), both projects (all tasks apply to both)
- [x] **No placeholders:** All steps contain complete code
- [x] **Type consistency:** `branchTree`, `currentBranchId`, `viewingTick`, `viewingBranchId` used consistently across Tasks 7–9; `(branch_id, tick)` tuple key used consistently in Tasks 3–4; `restore_state`/`restore_all_agents` names match Tasks 1–2
- [x] **`applyAgentsData` ambiguity:** Task 9 Step 1 explicitly asks implementer to find the real function name before adding the shim — avoids hardcoding a wrong name
