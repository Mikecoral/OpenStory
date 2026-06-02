async function submitInput() {
  const input = document.getElementById('worldInput').value.trim();
  if (!input) return;

  setStatus(true, '解析中…');
  hideResult();
  hideError();

  try {
    // Stage 1: 解析意图
    const resp = await fetch('/api/stage1/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || '请求失败');
    }

    const data = await resp.json();
    setStatus(true, 'Stage1 完成，正在生成语义数据 + 空间地图…');

    // Stage 2: 统一执行语义生成 + 空间生成
    const stage2Resp = await fetch(`/api/stage2/run/${data.session_id}`, {
      method: 'POST',
    });
    const stage2 = await stage2Resp.json().catch(() => ({}));

    if (!stage2Resp.ok) {
      throw new Error(stage2.detail || 'Stage2 执行失败');
    }

    setStatus(false);
    showResult(data, stage2);

    // 自动渲染空间地图
    if (stage2.spatial) {
      renderBlueprint(stage2.spatial);
    }
  } catch (e) {
    setStatus(false);
    showError(e.message);
  }
}

function setStatus(loading, text = '') {
  const section = document.getElementById('statusSection');
  const btn = document.getElementById('submitBtn');
  section.style.display = loading ? 'flex' : 'none';
  document.getElementById('statusText').textContent = text;
  btn.disabled = loading;
}

function hideResult() { document.getElementById('resultSection').style.display = 'none'; }
function hideError()  { document.getElementById('errorSection').style.display = 'none'; }

function showError(msg) {
  const s = document.getElementById('errorSection');
  s.style.display = 'block';
  document.getElementById('errorText').textContent = '错误：' + msg;
}

let _currentSessionId = null;

function showResult(session, stage2) {
  _currentSessionId = session.session_id;
  const s = document.getElementById('resultSection');
  s.style.display = 'block';
  document.getElementById('sessionId').textContent = 'session: ' + session.session_id;

  const sem = stage2.semantic || {};
  const sp = stage2.spatial || {};
  const val = sp.validation || {};

  let msg = 'Stage1 完成';
  msg += '\n语义数据: ' + (sem.location_count || 0) + ' 个地点, '
       + (sem.path_count || 0) + ' 条路径, '
       + (sem.character_count || 0) + ' 个角色';
  msg += '\n空间地图: ' + (sp.regions || []).length + ' 个区域, '
       + (sp.routes || []).length + ' 条路线';
  msg += '\n校验: ' + (val.passed ? '通过' : '未通过');
  if (val.issues && val.issues.length) {
    msg += ' (' + val.issues.length + ' 个问题)';
  }

  document.getElementById('resultMsg').textContent = msg;
  // 隐藏旧的独立按钮（统一端点已自动完成空间生成）
  document.getElementById('spatialBtn').style.display = 'none';

  // ================= 新增：配置并显示跳转按钮 =================
  const jumpBtn = document.getElementById('jump-to-viewer-btn');
  if (jumpBtn) {
    // 动态把刚才跑出来的 session_id 拼接到链接里
    jumpBtn.href = `/viewer.html?session_id=${session.session_id}`;
    // 显示按钮（用 inline-block 保持布局美观）
    jumpBtn.style.display = 'inline-block'; 
  }
  // ============================================================
}

function renderBlueprint(spatial) {
  try {
    const section = document.getElementById('mapSection');
    section.style.display = 'block';

    const grid = spatial.grid;
    const regions = spatial.regions || [];
    const routes = spatial.routes || [];
    const roadTiles = spatial.road_tiles || [];
    const spawns = spatial.spawn_points || [];
    const tilePx = 4;
    const canvasW = grid.width * tilePx;
    const canvasH = grid.height * tilePx;

    const canvas = document.getElementById('mapCanvas');
    canvas.width = canvasW;
    canvas.height = canvasH;
    const ctx = canvas.getContext('2d');

    // 背景
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, canvasW, canvasH);

    // 网格线
    ctx.strokeStyle = '#2a2a4a';
    ctx.lineWidth = 0.5;
    for (let x = 0; x <= grid.width; x++) {
      ctx.beginPath(); ctx.moveTo(x * tilePx, 0); ctx.lineTo(x * tilePx, canvasH); ctx.stroke();
    }
    for (let y = 0; y <= grid.height; y++) {
      ctx.beginPath(); ctx.moveTo(0, y * tilePx); ctx.lineTo(canvasW, y * tilePx); ctx.stroke();
    }

    // 区域着色
    const tagColors = {
      core: 'rgba(168,85,247,0.45)', major: 'rgba(59,130,246,0.4)',
      minor: 'rgba(34,197,94,0.35)', secret: 'rgba(239,68,68,0.4)',
      public: 'rgba(251,191,36,0.3)',
    };
    for (const r of regions) {
      const b = r.bounds;
      let color = 'rgba(100,116,139,0.35)';
      for (const tag of (r.tags || [])) { if (tagColors[tag]) { color = tagColors[tag]; break; } }
      ctx.fillStyle = color;
      ctx.fillRect(b.x * tilePx, b.y * tilePx, b.w * tilePx, b.h * tilePx);
      ctx.strokeStyle = 'rgba(255,255,255,0.2)';
      ctx.lineWidth = 1;
      ctx.strokeRect(b.x * tilePx, b.y * tilePx, b.w * tilePx, b.h * tilePx);
      // 标签
      ctx.fillStyle = '#fff';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(r.name || r.location_id, (b.x + b.w / 2) * tilePx, (b.y + b.h / 2) * tilePx);
    }

    // 道路
    ctx.fillStyle = '#38bdf8';
    for (const t of roadTiles) { ctx.fillRect(t.x * tilePx, t.y * tilePx, tilePx, tilePx); }

    // 路线中心线
    ctx.strokeStyle = 'rgba(56,189,248,0.5)';
    ctx.lineWidth = 1;
    for (const route of routes) {
      const cl = route.centerline || [];
      if (cl.length < 2) continue;
      ctx.beginPath();
      ctx.moveTo(cl[0].x * tilePx + tilePx / 2, cl[0].y * tilePx + tilePx / 2);
      for (let i = 1; i < cl.length; i++) {
        ctx.lineTo(cl[i].x * tilePx + tilePx / 2, cl[i].y * tilePx + tilePx / 2);
      }
      ctx.stroke();
    }

    // 入口点
    for (const r of regions) {
      const e = r.entrance;
      ctx.fillStyle = '#fbbf24';
      ctx.beginPath();
      ctx.arc(e.x * tilePx + tilePx / 2, e.y * tilePx + tilePx / 2, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#000'; ctx.lineWidth = 0.5; ctx.stroke();
    }

    // Spawn 点（只显示位置标记，不显示人名）
    for (const sp of spawns) {
      const [sx, sy] = sp.position;
      ctx.fillStyle = '#34d399';
      ctx.beginPath();
      ctx.arc(sx * tilePx + tilePx / 2, sy * tilePx + tilePx / 2, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.stroke();
    }

    // 信息
    const val = spatial.validation || {};
    document.getElementById('mapInfo').textContent =
      `${regions.length} 地点, ${routes.length} 路线, ${roadTiles.length} 道路格, ` +
      `${spawns.length} 角色, ${grid.width}×${grid.height} 格, 校验: ${val.passed ? '通过' : '未通过'}`;

    // 警告
    const issues = (val.issues || []);
    const warnDiv = document.getElementById('mapWarnings');
    if (issues.length) {
      warnDiv.style.display = 'block';
      warnDiv.textContent = '校验问题: ' + issues.map(i => `[${i.severity}] ${i.message}`).join('; ');
    } else {
      warnDiv.style.display = 'none';
    }
  } catch (err) {
    console.error('renderBlueprint error:', err);
  }
}

document.getElementById('worldInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitInput();
});