const notyf = new Notyf({ duration: 2500, ripple: true });
let ws = null;

function logLine(s) {
  const el = document.getElementById("log");
  el.textContent = `[${new Date().toISOString()}] ${s}\n` + el.textContent;
}

function getUserId() {
  return parseInt(document.getElementById("userId").value, 10);
}

async function api(path, method, body) {
  const resp = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const msg = data.detail ? JSON.stringify(data.detail) : JSON.stringify(data);
    throw new Error(`${resp.status}: ${msg}`);
  }
  return data;
}

async function createAccount() {
  try {
    const user_id = getUserId();
    const data = await api("/api/accounts", "POST", { user_id });
    notyf.success("Счет создан");
    logLine(`create account -> ${JSON.stringify(data)}`);
    await refreshBalance();
  } catch (e) {
    notyf.error(e.message);
    logLine(`ERROR: ${e.message}`);
  }
}

async function topUp() {
  try {
    const user_id = getUserId();
    const amount = parseInt(document.getElementById("topupAmount").value, 10);
    const data = await api("/api/accounts/topup", "POST", { user_id, amount });
    notyf.success("Баланс пополнен");
    logLine(`topup -> ${JSON.stringify(data)}`);
    document.getElementById("balance").textContent = data.balance;
  } catch (e) {
    notyf.error(e.message);
    logLine(`ERROR: ${e.message}`);
  }
}

async function refreshBalance() {
  try {
    const user_id = getUserId();
    const data = await api(`/api/accounts/balance?user_id=${encodeURIComponent(user_id)}`, "GET");
    document.getElementById("balance").textContent = data.balance;
    logLine(`balance -> ${JSON.stringify(data)}`);
  } catch (e) {
    document.getElementById("balance").textContent = "—";
    logLine(`balance ERROR: ${e.message}`);
  }
}

function closeWs() {
  if (ws) {
    ws.close();
    ws = null;
  }
}

function openWs(orderId) {
  closeWs();
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${window.location.host}/ws/orders/${orderId}`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    logLine(`WS open -> ${url}`);
  };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "order.status") {
        document.getElementById("currentStatus").textContent = msg.status;
        notyf.success(`Статус заказа: ${msg.status}`);
      }
      logLine(`WS message -> ${ev.data}`);
    } catch (e) {
      logLine(`WS parse error -> ${ev.data}`);
    }
  };
  ws.onclose = () => logLine("WS closed");
  ws.onerror = (e) => logLine("WS error");
}

async function createOrder() {
  try {
    const user_id = getUserId();
    const amount = parseInt(document.getElementById("orderAmount").value, 10);
    const description = document.getElementById("orderDesc").value;
    const data = await api("/api/orders", "POST", { user_id, amount, description });
    const orderId = data.id;
    document.getElementById("currentOrder").textContent = orderId;
    document.getElementById("currentStatus").textContent = data.status;
    notyf.success("Заказ создан, ожидаем оплату...");
    logLine(`create order -> ${JSON.stringify(data)}`);
    openWs(orderId);
  } catch (e) {
    notyf.error(e.message);
    logLine(`ERROR: ${e.message}`);
  }
}

window.createAccount = createAccount;
window.topUp = topUp;
window.refreshBalance = refreshBalance;
window.createOrder = createOrder;
