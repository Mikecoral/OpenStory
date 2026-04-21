# Return to Main Menu Feature Design

**Date:** 2026-04-21  
**Scope:** examples/deduction and examples/story frontends

## Summary

Add a "主菜单" (Main Menu) button to the in-game header of both free mode (port 8000) and story mode (port 8001). Clicking it resets the current game and returns the user to the initial mode selection screen.

## Files to Change

| File | Change |
|------|--------|
| `examples/deduction/frontend/index.html` | Add button HTML in header toolbar |
| `examples/deduction/frontend/app.js` | Add `returnToMainMenu()` function |
| `examples/story/frontend/index.html` | Add button HTML in header toolbar |
| `examples/story/frontend/app.js` | Add `returnToMainMenu()` function |

## Button Placement

Both buttons go in the header's right-side toolbar (`header-right`), immediately before the existing settings (gear) button. This keeps them visually consistent across both modes.

## Free Mode (port 8000)

### Button HTML

Add before `#settingsBtn` in `#appCoreUI` header:

```html
<button id="returnHomeBtn" class="control-btn" onclick="returnToMainMenu()" title="返回主菜单">🏠</button>
```

### `returnToMainMenu()` in deduction `app.js`

```javascript
async function returnToMainMenu() {
  if (!confirm('确认返回主菜单？\n当前推演进度将重置，所有记忆和状态将清空。')) return;
  try {
    const res = await fetch('http://localhost:8000/api/reset', { method: 'POST' });
    if (!res.ok) { alert('重置失败：' + (await res.text())); return; }
  } catch (e) {
    alert('重置请求发送失败，请检查网络连接');
    return;
  }
  // Close WebSocket
  if (ws) { ws.close(); ws = null; }
  // Return to mode selection
  document.getElementById('appCoreUI').classList.add('hidden');
  document.getElementById('modeSelectionScreen').classList.remove('hidden');
}
window.returnToMainMenu = returnToMainMenu;
```

**Key behaviours:**
- No intermediate "已发送" alert — navigate immediately after success
- WebSocket is closed before hiding the game UI
- Reset failure shows an error alert and does not navigate

## Story Mode (port 8001)

### Button HTML

Add before `#settingsBtn` in `index.html` header:

```html
<button id="returnHomeBtn" class="control-btn" onclick="returnToMainMenu()" title="返回主菜单">🏠</button>
```

### `returnToMainMenu()` in story `app.js`

```javascript
async function returnToMainMenu() {
  if (!confirm('确认返回主菜单？\n当前剧情推演进度将重置。')) return;
  try {
    const res = await fetch('http://localhost:8001/api/reset', { method: 'POST' });
    if (!res.ok) { alert('重置失败：' + (await res.text())); return; }
  } catch (e) {
    alert('重置请求发送失败，请检查网络连接');
    return;
  }
  window.location.href = 'http://localhost:8000/frontend/index.html';
}
window.returnToMainMenu = returnToMainMenu;
```

**Key behaviours:**
- On success: redirect to `http://localhost:8000/frontend/index.html` (deduction mode selection)
- No intermediate alert before navigation
- Reset failure shows error and does not navigate

## What Is Not Changed

- `character_select.html` — already mid-flow, not in-game; no button needed there
- `confirmReset()` — existing function untouched; new function is independent
- Backend reset endpoints — no changes needed
