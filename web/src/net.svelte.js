// WebSocket link to the server - the only place that talks to the backend.
export const net = $state({
  data: null,
  error: null,
  connected: false,
  role: null,
  rejected: false, // the join was refused (e.g. team name taken) before any state arrived
});

let ws = null;
let gid = null;
let joinMsg = null;
let errTimer = null;
let stopped = false;

export function connect(gameId, join) {
  gid = gameId;
  joinMsg = join;
  net.rejected = false;
  stopped = false;
  open();
}

function open() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${gid}`);
  ws.onopen = () => {
    net.connected = true;
    const token =
      joinMsg.role === 'lecturer'
        ? joinMsg.token
        : sessionStorage.getItem(`emg-token-${gid}`);
    send({ action: 'join', ...joinMsg, token });
  };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === 'welcome') {
      net.role = m.role;
      if (m.role === 'team') sessionStorage.setItem(`emg-token-${gid}`, m.token);
    } else if (m.type === 'state') {
      net.data = m;
      net.rejected = false;
    } else if (m.type === 'error') {
      net.error = m.text;
      clearTimeout(errTimer);
      errTimer = setTimeout(() => (net.error = null), 4000);
      if (!net.data) {
        net.rejected = true; // refused during join, before we ever had state
        stopped = true; // stop reconnecting until the user tries again
        ws.close();
      }
    }
  };
  ws.onclose = () => {
    net.connected = false;
    if (gid && !stopped) setTimeout(open, 1500);
  };
}

export function send(obj) {
  if (ws?.readyState === 1) ws.send(JSON.stringify(obj));
}
