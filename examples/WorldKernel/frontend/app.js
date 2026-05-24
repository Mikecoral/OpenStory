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

function showResult(session, stage2, ok) {
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
  } else if (stage2 && stage2.detail) {
    msg += '\nStage2 失败: ' + stage2.detail;
  }
  document.getElementById('resultMsg').textContent = msg;
}

document.getElementById('worldInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitInput();
});
