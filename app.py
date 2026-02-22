from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import os
from datetime import datetime

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active: list[dict] = []

    async def connect(self, ws: WebSocket, username: str):
        await ws.accept()
        self.active.append({"ws": ws, "user": username})
        await self.broadcast(f"🟢 {username} joined the chat", "system")

    def disconnect(self, ws: WebSocket):
        entry = next((c for c in self.active if c["ws"] is ws), None)
        if entry:
            self.active.remove(entry)
            return entry["user"]
        return "Unknown"

    async def broadcast(self, message: str, sender: str):
        ts = datetime.now().strftime("%H:%M")
        payload = {"sender": sender, "message": message, "time": ts}
        for conn in self.active[:]:
            try:
                await conn["ws"].send_json(payload)
            except:
                self.active.remove(conn)

    @property
    def users(self):
        return [c["user"] for c in self.active]


manager = ConnectionManager()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WebSocket Chat</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0f172a;--surface:#1e293b;--border:#334155;--primary:#3b82f6;--text:#e2e8f0;--muted:#94a3b8;--green:#22c55e;--red:#ef4444}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column}
#login-screen{display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px}
#login-screen h1{font-size:2rem;background:linear-gradient(135deg,var(--primary),#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
#login-screen input{padding:12px 20px;border-radius:12px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:1rem;width:280px;outline:none}
#login-screen input:focus{border-color:var(--primary)}
#login-screen button{padding:12px 32px;border-radius:12px;border:none;background:var(--primary);color:#fff;font-size:1rem;cursor:pointer;font-weight:600;transition:.2s}
#login-screen button:hover{opacity:.85}
#chat-screen{display:none;flex-direction:column;height:100vh}
header{padding:12px 20px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
header h2{font-size:1.1rem}
#user-count{font-size:.85rem;color:var(--muted)}
#messages{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:8px}
.msg{max-width:75%;padding:10px 14px;border-radius:14px;font-size:.95rem;line-height:1.4;word-wrap:break-word}
.msg .meta{font-size:.7rem;color:var(--muted);margin-top:4px}
.msg.mine{align-self:flex-end;background:var(--primary);border-bottom-right-radius:4px}
.msg.other{align-self:flex-start;background:var(--surface);border:1px solid var(--border);border-bottom-left-radius:4px}
.msg.other .name{font-size:.75rem;color:var(--primary);font-weight:600;margin-bottom:2px}
.msg.system{align-self:center;background:transparent;color:var(--muted);font-size:.8rem;padding:4px 0}
#input-bar{padding:12px 20px;background:var(--surface);border-top:1px solid var(--border);display:flex;gap:10px}
#input-bar input{flex:1;padding:12px 16px;border-radius:12px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.95rem;outline:none}
#input-bar input:focus{border-color:var(--primary)}
#input-bar button{padding:12px 20px;border-radius:12px;border:none;background:var(--primary);color:#fff;cursor:pointer;font-weight:600;font-size:.95rem;transition:.2s}
#input-bar button:hover{opacity:.85}
#typing-indicator{padding:0 20px 4px;font-size:.75rem;color:var(--muted);height:20px}
</style>
</head>
<body>
<div id="login-screen">
  <h1>💬 WebSocket Chat</h1>
  <input id="username" placeholder="Pick a username..." maxlength="20" autofocus>
  <button onclick="joinChat()">Join Chat</button>
</div>
<div id="chat-screen">
  <header>
    <h2>💬 Chat Room</h2>
    <span id="user-count">0 online</span>
  </header>
  <div id="messages"></div>
  <div id="typing-indicator"></div>
  <div id="input-bar">
    <input id="msg" placeholder="Type a message..." autocomplete="off">
    <button onclick="sendMsg()">Send</button>
  </div>
</div>
<script>
let ws, me, typingTimeout;
const $ = id => document.getElementById(id);

function joinChat() {
  me = $('username').value.trim();
  if (!me) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${encodeURIComponent(me)}`);
  ws.onopen = () => {
    $('login-screen').style.display = 'none';
    $('chat-screen').style.display = 'flex';
    $('msg').focus();
  };
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'typing') { showTyping(d.user); return; }
    if (d.type === 'users') { $('user-count').textContent = d.count + ' online'; return; }
    addMsg(d);
  };
  ws.onclose = () => addMsg({sender:'system', message:'🔴 Disconnected from server', time:''});
}

function addMsg(d) {
  const div = document.createElement('div');
  div.className = 'msg ' + (d.sender === 'system' ? 'system' : d.sender === me ? 'mine' : 'other');
  let html = '';
  if (d.sender !== 'system' && d.sender !== me) html += `<div class="name">${esc(d.sender)}</div>`;
  html += esc(d.message);
  if (d.time) html += `<div class="meta">${d.time}</div>`;
  div.innerHTML = html;
  $('messages').appendChild(div);
  $('messages').scrollTop = $('messages').scrollHeight;
}

function sendMsg() {
  const msg = $('msg').value.trim();
  if (!msg || !ws) return;
  ws.send(JSON.stringify({type: 'message', text: msg}));
  $('msg').value = '';
}

$('msg')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') sendMsg();
  else if (ws?.readyState === 1) ws.send(JSON.stringify({type: 'typing'}));
});
$('username')?.addEventListener('keydown', e => { if (e.key === 'Enter') joinChat(); });

function showTyping(user) {
  if (user === me) return;
  $('typing-indicator').textContent = `${user} is typing...`;
  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => $('typing-indicator').textContent = '', 2000);
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML


@app.websocket("/ws/{username}")
async def websocket_endpoint(ws: WebSocket, username: str):
    await manager.connect(ws, username)
    await broadcast_users()
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "typing":
                for conn in manager.active:
                    if conn["ws"] is not ws:
                        try:
                            await conn["ws"].send_json({"type": "typing", "user": username})
                        except:
                            pass
            elif data.get("type") == "message":
                text = data.get("text", "").strip()
                if text:
                    await manager.broadcast(text, username)
    except WebSocketDisconnect:
        user = manager.disconnect(ws)
        await manager.broadcast(f"🔴 {user} left the chat", "system")
        await broadcast_users()


async def broadcast_users():
    payload = {"type": "users", "count": len(manager.active)}
    for conn in manager.active[:]:
        try:
            await conn["ws"].send_json(payload)
        except:
            manager.active.remove(conn)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
