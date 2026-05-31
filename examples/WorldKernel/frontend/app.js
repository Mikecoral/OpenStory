async function submitInput() {
  const input = document.getElementById('worldInput').value.trim();
  if (!input) return;

  setStatus(true, '解析中…');
  hideResult();
  hideError();

  try {
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
    setStatus(true, 'Stage1 完成，正在生成地点…');

    const stage2Resp = await fetch(`/api/stage2/generate/${data.session_id}`, {
      method: 'POST',
    });
    const stage2 = await stage2Resp.json().catch(() => ({}));

    setStatus(false);
    showResult(data, stage2, stage2Resp.ok);
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

function showResult(session, stage2, ok) {
  _currentSessionId = session.session_id;
  const s = document.getElementById('resultSection');
  s.style.display = 'block';
  document.getElementById('sessionId').textContent = 'session: ' + session.session_id;

  let msg = 'Stage1 完成，文件保存在 templates/' + session.session_id + '/';
  if (ok && stage2.locations) {
    const loc = stage2.locations;
    msg += '\n地点生成: ' + loc.count + ' 个';
    if (loc.avg_score != null) msg += ', 质量评分: ' + loc.avg_score;
    if (stage2.errors && stage2.errors.length) {
      msg += '\n警告: ' + stage2.errors.join('; ');
    }
    document.getElementById('spatialBtn').style.display = 'inline-block';
  } else if (stage2 && stage2.detail) {
    msg += '\nStage2 失败: ' + stage2.detail;
  }
  document.getElementById('resultMsg').textContent = msg;
}

async function generateSpatial() {
  if (!_currentSessionId) return;
  const btn = document.getElementById('spatialBtn');
  btn.disabled = true;
  btn.textContent = '生成中…';

  try {
    const resp = await fetch(`/api/spatial/generate/${_currentSessionId}`, { method: 'POST' });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '空间生成失败');
    renderSpatialMap(data);
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '生成空间地图';
  }
}

function renderSpatialMap(data) {
  try {
  const section = document.getElementById('mapSection');
  section.style.display = 'block';

  const grid = data.grid;
  const regions = data.regions;
  const routes = data.routes || [];
  const roadTiles = (data.road_tiles && data.road_tiles.length)
    ? data.road_tiles
    : collectUniqueRouteTiles(routes);
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
    ctx.beginPath();
    ctx.moveTo(x * tilePx, 0);
    ctx.lineTo(x * tilePx, canvasH);
    ctx.stroke();
  }
  for (let y = 0; y <= grid.height; y++) {
    ctx.beginPath();
    ctx.moveTo(0, y * tilePx);
    ctx.lineTo(canvasW, y * tilePx);
    ctx.stroke();
  }

  // 区域着色（先画区域，再画路径，路径在上层）
  const tagColors = {
    core:   'rgba(168,85,247,0.45)',
    major:  'rgba(59,130,246,0.4)',
    minor:  'rgba(34,197,94,0.35)',
    secret: 'rgba(239,68,68,0.4)',
    public: 'rgba(251,191,36,0.3)',
  };

  for (const r of regions) {
    let color = 'rgba(100,116,139,0.35)';
    for (const tag of (r.tags || [])) {
      if (tagColors[tag]) { color = tagColors[tag]; break; }
    }
    ctx.fillStyle = color;
    ctx.fillRect(r.x * tilePx, r.y * tilePx, r.width * tilePx, r.height * tilePx);

    // 边框
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.lineWidth = 1;
    ctx.strokeRect(r.x * tilePx, r.y * tilePx, r.width * tilePx, r.height * tilePx);

    // 标签
    const cx = r.x * tilePx + (r.width * tilePx) / 2;
    const cy = r.y * tilePx + (r.height * tilePx) / 2;
    ctx.fillStyle = '#fff';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(r.name || r.location_id, cx, cy);
  }

  // Draw the merged physical road network once instead of every semantic path.
  ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
  for (const t of roadTiles) {
    ctx.fillRect((t.x - 0.25) * tilePx, (t.y - 0.25) * tilePx, tilePx * 1.5, tilePx * 1.5);
  }
  ctx.fillStyle = '#38bdf8';
  for (const t of roadTiles) {
    ctx.fillRect(t.x * tilePx, t.y * tilePx, tilePx, tilePx);
  }

  // 入口点（在最上层）
  for (const r of regions) {
    ctx.fillStyle = '#fbbf24';
    ctx.beginPath();
    ctx.arc(r.entrance_x * tilePx + tilePx / 2, r.entrance_y * tilePx + tilePx / 2, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  // 调试：画布左上角显示 route 数量
  ctx.fillStyle = '#000';
  ctx.fillRect(4, 4, 200, 20);
  ctx.fillStyle = '#0f0';
  ctx.font = 'bold 14px monospace';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillText('DEBUG routes=' + routes.length + ' roads=' + roadTiles.length + ' regions=' + regions.length, 8, 6);

  // 信息
  document.getElementById('mapInfo').textContent =
    `${regions.length} 个地点, ${routes.length} 条路径, ${roadTiles.length} 个道路格, ${grid.width}×${grid.height} 格`;

  // 警告
  const warns = data.warnings || [];
  const warnDiv = document.getElementById('mapWarnings');
  if (warns.length) {
    warnDiv.style.display = 'block';
    warnDiv.textContent = '警告: ' + warns.map(w => w.message).join('; ');
  } else {
    warnDiv.style.display = 'none';
  }
  } catch (err) {
    console.error('renderSpatialMap error:', err);
  }
}

function collectUniqueRouteTiles(routes) {
  const seen = new Set();
  const tiles = [];
  for (const route of routes || []) {
    for (const t of route.route_tiles || []) {
      const key = `${t.x},${t.y}`;
      if (seen.has(key)) continue;
      seen.add(key);
      tiles.push(t);
    }
  }
  return tiles;
}

document.getElementById('worldInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitInput();
});
