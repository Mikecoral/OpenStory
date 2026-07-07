# Story Branch Tree (回溯树) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the full backtrack-tree / branch-fork feature from `examples/story_of_the_stone` into `examples/story`, including score snapshot/restore and player-task clearing on fork.

**Architecture:** Add `restore_all_agents()` to story's `BasicPodManager`; maintain a local `_score_snapshots` dict in `run_simulation.py` alongside server's `_tick_snapshots`; copy the branch-tree SVG modal and all JS logic from deduction's frontend.

**Tech Stack:** Python/Ray (backend), FastAPI/WebSocket (server.py shared), Vanilla JS + SVG (frontend)

---

## File Map

| File | Change |
|---|---|
| `examples/story/BasicPodManager.py` | Add `restore_all_agents()` method |
| `examples/story/run_simulation.py` | Import `broadcast_branch_event`, reset branch state per session, add `_score_snapshots`, fork detection block, `_first_tick_after_fork` offset, score snapshot after each tick |
| `examples/story/frontend/index.html` | Add memory-tree button, modal overlay, history-mode banner |
| `examples/story/frontend/app.js` | Add branch state vars, `get_branch_tree` on connect, 3 new WS handlers, 8 branch-tree functions |
| `examples/story/frontend/style.css` | Add memory-tree CSS (copy from deduction) |

---

### Task 1: Add `restore_all_agents()` to BasicPodManager

**Files:**
- Modify: `examples/story/BasicPodManager.py`

- [ ] **Step 1: Append `restore_all_agents` method to the class**

Open `examples/story/BasicPodManager.py`. After the last method `update_agents_status` (line 215), add:

```python
    async def restore_all_agents(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore all agents to a previously saved state snapshot.
        Called during branch fork to roll back Ray actor state.
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

- [ ] **Step 2: Commit**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
git add examples/story/BasicPodManager.py
git commit -m "feat(story): add restore_all_agents to BasicPodManager"
```

---

### Task 2: Update run_simulation.py — imports, session reset, fork detection, score snapshots

**Files:**
- Modify: `examples/story/run_simulation.py`

- [ ] **Step 1: Add `broadcast_branch_event` to the import line**

Find this line (line 30):
```python
from agentkernel_distributed.mas.interface.server import start_server, broadcast_tick_data
```
Replace with:
```python
from agentkernel_distributed.mas.interface.server import start_server, broadcast_tick_data, broadcast_branch_event
import agentkernel_distributed.mas.interface.server as server_module
```

Note: `server_module` is already imported later inside `main()` at line 128 — the module-level import here is just to make the alias available. Remove the duplicate `import agentkernel_distributed.mas.interface.server as server_module` line that appears at line 128–129 after you add it here.

- [ ] **Step 2: Declare `_score_snapshots` at module level after the server import block**

After the two new import lines above, add:
```python
from typing import Dict, Any, Tuple
_score_snapshots: Dict[Tuple, Dict[str, Any]] = {}
```

- [ ] **Step 3: Reset branch and score state at each session start**

Inside the `while True:` game loop, after line `server_module._snapshot_tick = -1` (currently around line 199), add these resets:

```python
            # Reset branch / backtrack state for new session
            server_module._tick_snapshots = {}
            server_module._branches = [{"id": 0, "parent_branch_id": None, "fork_tick": 0, "ticks": []}]
            server_module._current_branch_id = 0
            server_module._viewing_tick = -1
            server_module._viewing_branch_id = -1
            server_module._first_tick_after_fork = False
            _score_snapshots.clear()
```

- [ ] **Step 4: Add fork detection block inside the tick loop**

After the `tick_start_event.clear()` line (currently around line 231) and before `tick_start_time = time.time()`, insert the full fork detection block:

```python
                # ── 回溯分支检测 ─────────────────────────────────────────────────
                if server_module._viewing_tick != -1:
                    viewing_tick = server_module._viewing_tick
                    viewing_branch_id = server_module._viewing_branch_id
                    viewing_branch = server_module._branches[viewing_branch_id]
                    max_viewing_tick = max(viewing_branch["ticks"], default=-1)

                    is_current_tip = (
                        viewing_branch_id == server_module._current_branch_id
                        and viewing_tick == max_viewing_tick
                    )

                    if viewing_tick <= max_viewing_tick and not is_current_tip:
                        snapshot_key = (viewing_branch_id, viewing_tick)
                        if snapshot_key in server_module._tick_snapshots:
                            logger.info(f"【Branch】Forking new branch from tick {viewing_tick} on branch {viewing_branch_id}")
                            # 1. Restore agent states
                            await pod_manager.restore_all_agents.remote(server_module._tick_snapshots[snapshot_key])
                            # 2. Reset simulation timer
                            await system.run('timer', 'set_tick', viewing_tick)
                            # 3. Restore score + score_events to Redis
                            if snapshot_key in _score_snapshots:
                                score_snap = _score_snapshots[snapshot_key]
                                await _story_redis.set('story:score', score_snap["score"])
                                await _story_redis.delete('story:score_events')
                                if score_snap["events"]:
                                    await _story_redis.rpush('story:score_events', *reversed(score_snap["events"]))
                                logger.info(f"【Branch】Restored story:score={score_snap['score']} with {len(score_snap['events'])} events")
                            # 4. Clear all player-assigned tasks
                            async for key in _story_redis.scan_iter('user_plan:*'):
                                await _story_redis.delete(key)
                            logger.info("【Branch】Cleared all user_plan:* keys")
                            # 5. Create new branch metadata
                            new_branch = {
                                "id": len(server_module._branches),
                                "parent_branch_id": viewing_branch_id,
                                "fork_tick": viewing_tick,
                                "ticks": [],
                            }
                            server_module._branches.append(new_branch)
                            server_module._current_branch_id = new_branch["id"]
                            server_module._first_tick_after_fork = True
                            logger.info(f"【Branch】Created branch {new_branch['id']} forking at tick {viewing_tick} from branch {viewing_branch_id}")
                            await broadcast_branch_event("branch_created", {"new_branch_id": new_branch["id"], "fork_tick": viewing_tick})
                        else:
                            logger.warning(f"【Branch】Snapshot {snapshot_key} not found — skipping fork")

                    server_module._viewing_tick = -1
                    server_module._viewing_branch_id = -1
                # ── 回溯分支检测结束 ─────────────────────────────────────────────
```

- [ ] **Step 5: Add `_first_tick_after_fork` broadcast-tick offset**

After the `current_tick = await system.run('timer', 'get_tick')` line, add:

```python
                # fork 后第一次广播：tick 编号 = fork_tick + 1，避免与父分支节点重叠
                if server_module._first_tick_after_fork:
                    server_module._first_tick_after_fork = False
                    broadcast_tick = current_tick + 1
                else:
                    broadcast_tick = current_tick
```

Then replace every subsequent use of `current_tick` in the tick loop (performance logs and `broadcast_tick_data(current_tick, ...)`) with `broadcast_tick`. Specifically:

Replace:
```python
                logger.info(f"【Performance】--- Tick {current_tick} Performance Report ---")
```
with:
```python
                logger.info(f"【Performance】--- Tick {broadcast_tick} Performance Report ---")
```

Replace:
```python
                logger.info(f"【System】--- Tick {current_tick} finished in {tick_duration:.4f} seconds ---")
```
with:
```python
                logger.info(f"【System】--- Tick {broadcast_tick} finished in {tick_duration:.4f} seconds ---")
```

Replace inside the try block:
```python
                    logger.info(f"【System】Collecting agents data for Tick {current_tick}...")
```
with:
```python
                    logger.info(f"【System】Collecting agents data for Tick {broadcast_tick}...")
```

Replace:
```python
                    logger.info(f"【System】Broadcasting data for Tick {current_tick} (agents count: {len(agents_data)})...")
```
with:
```python
                    logger.info(f"【System】Broadcasting data for Tick {broadcast_tick} (agents count: {len(agents_data)})...")
```

Replace:
```python
                    await broadcast_tick_data(current_tick, agents_data)
```
with:
```python
                    await broadcast_tick_data(broadcast_tick, agents_data)
```

Replace:
```python
                    logger.info(f"【System】Tick {current_tick} data broadcasted to frontend.")
```
with:
```python
                    logger.info(f"【System】Tick {broadcast_tick} data broadcasted to frontend.")
```

Replace:
```python
                    logger.info(f"【Story】Tick {current_tick}: story:score = {story_score}")
```
with:
```python
                    logger.info(f"【Story】Tick {broadcast_tick}: story:score = {story_score}")
```

Also fix the score_events filter — currently it matches `ev.get('tick') == current_tick`. Change to `broadcast_tick`:
```python
                        if ev.get('tick') == broadcast_tick:
```

- [ ] **Step 6: Save score snapshot after broadcasting**

After the `await server_module.manager.broadcast(score_payload)` line and before the victory/defeat check, add:

```python
                    # Save score snapshot for this (branch, tick)
                    all_events_raw = await _story_redis.lrange('story:score_events', 0, -1)
                    _score_snapshots[(server_module._current_branch_id, broadcast_tick)] = {
                        "score": story_score,
                        "events": list(all_events_raw),
                    }
```

- [ ] **Step 7: Commit**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
git add examples/story/run_simulation.py
git commit -m "feat(story): add branch fork detection, score snapshots, player-task clearing"
```

---

### Task 3: Update index.html — button, modal, banner

**Files:**
- Modify: `examples/story/frontend/index.html`

- [ ] **Step 1: Add memory-tree button in header-right**

Find in `index.html`:
```html
      <button id="settingsBtn" class="control-btn settings-btn" onclick="openSettingsModal()" title="设置">
```

Insert **before** that line:
```html
      <!-- 回溯树按钮 -->
      <button id="memoryTreeBtn" class="control-btn memory-tree-btn" onclick="toggleMemoryTree()" title="回溯树">
        🌳 回溯树
      </button>
```

- [ ] **Step 2: Add memory-tree modal overlay**

Find at the end of `<body>` (just before `<script src="i18n.js">`):
```html
  <script src="i18n.js"></script>
```

Insert **before** that line:
```html
  <!-- ── 回溯树浮动弹窗 ──────────────────────────────────────────────────────── -->
  <div id="memoryTreeOverlay" class="memory-tree-overlay" style="display:none" onclick="handleMemoryTreeOverlayClick(event)">
    <div class="memory-tree-modal" onclick="event.stopPropagation()">
      <div class="memory-tree-header">
        <span class="memory-tree-title">🌳 回溯树</span>
        <button class="memory-tree-close" onclick="toggleMemoryTree()">✕</button>
      </div>
      <div class="memory-tree-body">
        <!-- 历史查看 banner（查看旧 tick 时显示） -->
        <div id="historyViewBanner" class="history-view-banner" style="display:none">
          ⏪ <span id="historyViewText">正在查看 Tick —</span>
          <span class="history-view-hint">· 点击"开始推演"将从此处创建新分支</span>
        </div>
        <!-- 图例 -->
        <div class="branch-legend" id="branchLegend"></div>
        <!-- SVG 树形图 -->
        <div class="branch-tree-container">
          <svg id="branchTreeSvg" width="100%" height="200"></svg>
        </div>
        <div class="branch-tree-hint">点击节点可跳转查看 · 从旧 Tick 推进时自动创建新分支</div>
      </div>
    </div>
  </div>
  <!-- ── 历史查看提示条（模拟界面顶部） ─────────────────────────────────────────── -->
  <div id="historyModeBanner" class="history-mode-banner" style="display:none">
    <span id="historyModeBannerText">⏪ 正在查看 Tick — · 点击"开始推演"将从此处创建新分支</span>
    <button class="history-mode-banner-close" onclick="exitHistoryView()">✕ 返回最新</button>
  </div>
```

- [ ] **Step 3: Commit**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
git add examples/story/frontend/index.html
git commit -m "feat(story): add branch-tree modal and history banner to HTML"
```

---

### Task 4: Update app.js — state vars, WS handlers, branch-tree functions

**Files:**
- Modify: `examples/story/frontend/app.js`

- [ ] **Step 1: Add branch state variables**

Find in `app.js` (around line 222):
```javascript
let tickHistory = []; // 记录已经模拟的 tick 数据历史
let currentHistoryIndex = -1; // 当前展示的历史索引
```

Insert **after** those two lines:
```javascript

// ── 回溯树 / 分支状态 ──────────────────────────────────────────────────────────
const BRANCH_COLORS = [
  '#ffd700','#4fc3f7','#81c784','#ff8a65',
  '#ce93d8','#80deea','#ffb74d','#f48fb1',
];
let branchTree = [];
let currentBranchId = 0;
let viewingTick = -1;
let viewingBranchId = -1;
let isViewingHistory = false;
let memoryTreeOpen = false;
```

- [ ] **Step 2: Send `get_branch_tree` on WebSocket open**

Find in `app.js`:
```javascript
  ws.onopen = () => {
    setStatus('connected');
    // If we were waiting for a restart to complete, reload the page
    if (isReconnectingAfterRestart) {
      isReconnectingAfterRestart = false;
      window.location.reload();
    }
  };
```

Replace with:
```javascript
  ws.onopen = () => {
    setStatus('connected');
    if (isReconnectingAfterRestart) {
      isReconnectingAfterRestart = false;
      window.location.reload();
    }
    ws.send(JSON.stringify({ type: 'get_branch_tree' }));
  };
```

- [ ] **Step 3: Add WS message handlers for branch_tree, branch_created, view_tick_ack**

Find in `ws.onmessage` the closing line of the last `else if` block before `} catch (err)`:
```javascript
      }
    } catch (err) { console.error('parse error', err); }
```

Insert **before** that closing `}` (i.e., inside the try block, after the last `else if`):
```javascript
      } else if (msg.type === 'branch_tree') {
        const newTreeStr = JSON.stringify(msg.branches || []);
        const oldTreeStr = JSON.stringify(branchTree);
        const newBranchId = msg.current_branch_id ?? 0;
        const branchIdChanged = newBranchId !== currentBranchId;
        branchTree = msg.branches || [];
        currentBranchId = newBranchId;
        if (newTreeStr !== oldTreeStr || branchIdChanged) {
          renderBranchTree();
        }
      } else if (msg.type === 'branch_created') {
        branchTree = msg.branches || [];
        currentBranchId = msg.current_branch_id ?? 0;
        isViewingHistory = false;
        viewingTick = -1;
        viewingBranchId = -1;
        updateHistoryModeBanner();
        renderBranchTree();
        renderAgentList();
        if (selectedAgent && agentsData[selectedAgent]) {
          renderDetail(selectedAgent);
        }
      } else if (msg.type === 'view_tick_ack') {
        if (msg.data) {
          viewingTick = msg.tick;
          viewingBranchId = msg.branch_id;
          isViewingHistory = true;
          const newData = msg.data;
          Object.keys(agentsData).forEach(id => {
            if (!newData[id]) delete agentsData[id];
          });
          if (selectedAgent && newData[selectedAgent]) {
            const snapTick = newData[selectedAgent].current_tick ?? msg.tick;
            viewDays[selectedAgent] = Math.floor(snapTick / 12) + 1;
          }
          applyAgentsData(newData, msg.tick);
          if (selectedAgent) {
            if (agentsData[selectedAgent]) {
              renderDetail(selectedAgent);
            } else {
              const panel = document.getElementById('detailPanel');
              if (panel) panel.innerHTML = '<div class="empty-state"><div class="empty-icon">卷</div><p>该角色在此时间线中尚未出现</p></div>';
            }
          }
          updateHistoryModeBanner();
          renderBranchTree();
        }
```

- [ ] **Step 4: Add branch-tree functions at end of file**

Append the following block to the **very end** of `app.js`:

```javascript

// ── 回溯树函数 ─────────────────────────────────────────────────────────────────

function toggleMemoryTree() {
  memoryTreeOpen = !memoryTreeOpen;
  const overlay = document.getElementById('memoryTreeOverlay');
  if (overlay) overlay.style.display = memoryTreeOpen ? 'flex' : 'none';
  if (memoryTreeOpen) {
    renderBranchTree();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'get_branch_tree' }));
    }
  }
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
  if (tickHistory.length > 0) {
    applyHistoryTick(tickHistory[tickHistory.length - 1]);
  }
  renderBranchTree();
}

function applyAgentsData(data, tick) {
  applyHistoryTick({ tick, data });
}

function updateHistoryModeBanner() {
  const banner = document.getElementById('historyModeBanner');
  const bannerText = document.getElementById('historyModeBannerText');
  const innerBanner = document.getElementById('historyViewBanner');
  const innerText = document.getElementById('historyViewText');
  if (!banner) return;
  if (isViewingHistory && viewingTick !== -1) {
    banner.style.display = 'flex';
    if (bannerText) bannerText.textContent = `⏪ 正在查看 Tick ${viewingTick} · 点击"开始推演"将从此处创建新分支`;
    if (innerBanner) innerBanner.style.display = 'flex';
    if (innerText) innerText.textContent = `正在查看 Tick ${viewingTick}`;
  } else {
    banner.style.display = 'none';
    if (innerBanner) innerBanner.style.display = 'none';
  }
}

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

  const allTicks = [...new Set(branchTree.flatMap(b => b.ticks || []))].sort((a, b) => a - b);
  if (allTicks.length === 0) {
    svg.innerHTML = '<text x="10" y="30" fill="#555" font-size="12">暂无数据</text>';
    return;
  }

  const tickToX = {};
  allTicks.forEach((t, i) => { tickToX[t] = PAD_X + i * H_GAP; });

  const branchToY = {};
  branchTree.forEach((b, i) => { branchToY[b.id] = PAD_Y + i * V_GAP; });

  const svgWidth = PAD_X * 2 + (allTicks.length - 1) * H_GAP;
  const svgHeight = PAD_Y * 2 + (branchTree.length - 1) * V_GAP;
  svg.setAttribute('viewBox', `0 0 ${svgWidth} ${svgHeight}`);
  svg.setAttribute('height', Math.max(svgHeight, 80));

  let html = '';

  branchTree.forEach(branch => {
    const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
    const ticks = (branch.ticks || []).slice().sort((a, b) => a - b);
    const y = branchToY[branch.id];

    if (branch.parent_branch_id !== null && branch.parent_branch_id !== undefined && ticks.length > 0) {
      const parentY = branchToY[branch.parent_branch_id];
      const forkX = tickToX[branch.fork_tick] ?? PAD_X;
      const firstX = tickToX[ticks[0]] ?? forkX;
      html += `<line x1="${forkX}" y1="${parentY}" x2="${firstX}" y2="${y}" stroke="${color}" stroke-width="2" opacity="0.7"/>`;
    }

    if (ticks.length > 1) {
      const x1 = tickToX[ticks[0]];
      const x2 = tickToX[ticks[ticks.length - 1]];
      html += `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${color}" stroke-width="2"/>`;
    }
  });

  branchTree.forEach(branch => {
    const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
    const ticks = (branch.ticks || []).slice().sort((a, b) => a - b);
    const y = branchToY[branch.id];

    const currentBranch = branchTree.find(b => b.id === currentBranchId);
    const lastTickOfCurrentBranch = currentBranch ? Math.max(...(currentBranch.ticks.length ? currentBranch.ticks : [0])) : -1;

    ticks.forEach(tick => {
      const x = tickToX[tick];
      const isViewing = isViewingHistory && tick === viewingTick && branch.id === viewingBranchId;
      const isLiveCurrentTick = branch.id === currentBranchId && tick === lastTickOfCurrentBranch && !isViewingHistory;

      if (isViewing) {
        html += `<circle cx="${x}" cy="${y}" r="${NODE_R + 5}" fill="none" stroke="#a0a0ff" stroke-width="2" stroke-dasharray="4 2" pointer-events="none"/>`;
      }
      if (isLiveCurrentTick) {
        html += `<circle cx="${x}" cy="${y}" r="${NODE_R + 4}" fill="none" stroke="#e94560" stroke-width="2" stroke-dasharray="3 2" opacity="0.8" pointer-events="none"/>`;
      }

      const nodeStroke = isLiveCurrentTick ? '#fff' : 'rgba(255,255,255,0.4)';
      const nodeStrokeW = isLiveCurrentTick ? 2 : 1;
      const nodeFill = isLiveCurrentTick ? '#e94560' : color;
      html += `<circle cx="${x}" cy="${y}" r="${NODE_R}" fill="${nodeFill}" stroke="${nodeStroke}" stroke-width="${nodeStrokeW}" pointer-events="none"/>`;
      html += `<text x="${x}" y="${y + NODE_R + 14}" text-anchor="middle" fill="${color}" font-size="10" pointer-events="none">T${tick}</text>`;
      html += `<circle cx="${x}" cy="${y + 8}" r="${NODE_R + 14}" fill="transparent" style="cursor:pointer" data-bid="${branch.id}" data-t="${tick}"/>`;
    });
  });

  branchTree.forEach(branch => {
    const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
    const ticks = branch.ticks || [];
    if (ticks.length === 0) return;
    const lastTick = Math.max(...ticks);
    const x = tickToX[lastTick] + NODE_R + 8;
    const y = branchToY[branch.id];
    html += `<text x="${x}" y="${y + 4}" fill="${color}" font-size="9" opacity="0.7" pointer-events="none">时间线${branch.id + 1}</text>`;
  });

  svg.innerHTML = html;

  svg.querySelectorAll('[data-bid]').forEach(function(el) {
    el.addEventListener('click', function(e) {
      e.stopPropagation();
      onClickTreeNode(
        parseInt(el.getAttribute('data-bid')),
        parseInt(el.getAttribute('data-t'))
      );
    });
  });

  renderBranchLegend();
}

function onClickTreeNode(branchId, tick) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.warn('回溯树：WS 未连接');
    return;
  }
  console.log('回溯树：跳转到 branch=' + branchId + ' tick=' + tick);
  ws.send(JSON.stringify({ type: 'view_tick', tick: tick, branch_id: branchId }));
  if (memoryTreeOpen) toggleMemoryTree();
}

function renderBranchLegend() {
  const legend = document.getElementById('branchLegend');
  if (!legend || !branchTree) return;
  legend.innerHTML = branchTree.map(branch => {
    const color = BRANCH_COLORS[branch.id % BRANCH_COLORS.length];
    const label = `时间线${branch.id + 1}`;
    const active = branch.id === currentBranchId ? ' (当前)' : '';
    return `<div class="branch-legend-item">
      <div class="branch-legend-dot" style="background:${color}"></div>
      <span>${label}${active}</span>
    </div>`;
  }).join('');
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
git add examples/story/frontend/app.js
git commit -m "feat(story): add branch-tree state vars, WS handlers, and rendering functions"
```

---

### Task 5: Update style.css — add memory-tree CSS

**Files:**
- Modify: `examples/story/frontend/style.css`

- [ ] **Step 1: Append memory-tree CSS at end of file**

Add the following block to the **very end** of `examples/story/frontend/style.css`:

```css
/* ── 回溯树 Memory Tree ───────────────────────────────────────────────────── */

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

.history-mode-banner {
  position: fixed;
  top: 64px;
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

- [ ] **Step 2: Commit**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
git add examples/story/frontend/style.css
git commit -m "feat(story): add branch-tree CSS styles"
```

---

## Self-Review

**Spec coverage:**
- ✅ restore_all_agents — Task 1
- ✅ fork detection + agent restore — Task 2 Step 4
- ✅ score + score_events restore — Task 2 Step 4 (step 3 inside fork block)
- ✅ user_plan:* clearing — Task 2 Step 4 (step 4 inside fork block)
- ✅ branch state reset per session — Task 2 Step 3
- ✅ _first_tick_after_fork offset — Task 2 Step 5
- ✅ score snapshot after each tick — Task 2 Step 6
- ✅ HTML button + modal + banner — Task 3
- ✅ JS state vars — Task 4 Step 1
- ✅ get_branch_tree on connect — Task 4 Step 2
- ✅ branch_tree / branch_created / view_tick_ack handlers — Task 4 Step 3
- ✅ 8 branch-tree functions — Task 4 Step 4
- ✅ CSS — Task 5

**Placeholder scan:** None found.

**Type consistency:**
- `_score_snapshots` key is `(branch_id: int, tick: int)` — consistent throughout Task 2
- `restore_all_agents(snapshot)` parameter is `Dict[str, Any]` — matches `_tick_snapshots` value type
- `applyAgentsData(data, tick)` calls `applyHistoryTick({tick, data})` — `applyHistoryTick` in story expects `msg.tick` and `msg.data`, consistent
- `renderBranchTree()` reads `branchTree`, `currentBranchId`, `viewingTick`, `viewingBranchId`, `isViewingHistory` — all declared in Task 4 Step 1
