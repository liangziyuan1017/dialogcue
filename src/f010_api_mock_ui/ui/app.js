const DEFAULT_REQUEST = {
  customer_utterance: "呃，就因为我们们我们是有两个项目，一个项目可能会拖比较久那另外一个项目我我已经在审核了，就是已经在给拆分了也就是这3个月，它能我们能出，能出那个工存款。",
  conversation_context: "您好。戴女士，招商银行信用卡中心您的个人逾期材料已经还是审核失败了，那后端部门提将通过我们转交到您的逾期材料，后续银行也会通过强制银行清收流程追偿您在我行的一个全额欠款，那我们也不需要函件寄送，以后对您的工作生活证影响以及对您现在一个个人情况，银行也需要简单核实一下，您现在本人是在做生意还是在打工呢？ 呃我们我们自己做工程的 嗯做工程还是在 呃，我们现在现在是做工程，目前是因为工程被欠款，所以我这边才会欠款。 嗯，那那您这个工欠款拖欠了多久了呢？",
  conversation_state: {
    branch_key: { facts: ["expense_pressure"] },
    inherited_facts: ["debt_acknowledgment"],
    inherited_emotions: [],
    willingness: "conditional"
  },
  context: {
    has_auto_loan: false,
    has_mortgage: false,
    has_negotiation_history: true,
    social_insurance_stable: false,
    credit_rating_good: false,
    card_restricted: false,
    is_cash_out_customer: false,
    has_complaint_history: false,
    has_legal_tools: true,
    is_negotiation_brain_customer: false
  }
};

let restEditor = null;
let responseEditor = null;

document.addEventListener("DOMContentLoaded", () => {
  restEditor = CodeMirror.fromTextArea(document.getElementById("rest-request-body"), {
    mode: "javascript",
    json: true,
    lineNumbers: true,
    tabSize: 2
  });
  restEditor.setValue(JSON.stringify(DEFAULT_REQUEST, null, 2));

  responseEditor = CodeMirror.fromTextArea(document.getElementById("rest-response-body"), {
    mode: "javascript",
    json: true,
    lineNumbers: true,
    readOnly: true,
    tabSize: 2
  });

  document.getElementById("rest-send-btn").addEventListener("click", sendRecommend);
  document.getElementById("rest-debug-btn").addEventListener("click", sendDebug);

  document.getElementById("sio-start-btn").addEventListener("click", sioStartSession);
  document.getElementById("sio-customer-btn").addEventListener("click", sioCustomerTurn);
  document.getElementById("sio-collector-btn").addEventListener("click", sioCollectorTurn);
  document.getElementById("sio-end-btn").addEventListener("click", sioEndSession);
});

async function sendRecommend() {
  clearTraceAndPool();
  try {
    const body = JSON.parse(restEditor.getValue());
    const resp = await fetch("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    responseEditor.setValue(JSON.stringify(data, null, 2));
  } catch (e) {
    responseEditor.setValue("Error: " + e.message);
  }
}

async function sendDebug() {
  clearTraceAndPool();
  try {
    const body = JSON.parse(restEditor.getValue());
    const resp = await fetch("/recommend/debug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    responseEditor.setValue(JSON.stringify(data, null, 2));
    renderTrace(data.trace || []);
    renderSentencePool(data.candidates || [], data.recommendation);
  } catch (e) {
    responseEditor.setValue("Error: " + e.message);
  }
}

function clearTraceAndPool() {
  document.getElementById("trace-steps").innerHTML = "";
  document.getElementById("sentence-pool-body").innerHTML = "";
}

function renderTrace(steps) {
  const container = document.getElementById("trace-steps");
  container.innerHTML = "";
  steps.forEach((step, i) => {
    const card = document.createElement("div");
    card.className = "bg-gray-800 rounded p-3 border border-gray-700";
    const header = document.createElement("div");
    header.className = "flex justify-between items-center cursor-pointer";
    header.innerHTML = `
      <span class="text-sm font-mono text-blue-300">${i + 1}. ${step.step}</span>
      <span class="text-xs text-gray-500">${step.latency_ms}ms</span>
    `;
    const body = document.createElement("pre");
    body.className = "text-xs text-gray-300 mt-2 overflow-auto max-h-32 font-mono hidden";
    body.textContent = JSON.stringify({ input: step.input, output: step.output }, null, 2);
    header.addEventListener("click", () => body.classList.toggle("hidden"));
    card.appendChild(header);
    card.appendChild(body);
    container.appendChild(card);
  });
}

function renderSentencePool(candidates, rec) {
  const tbody = document.getElementById("sentence-pool-body");
  tbody.innerHTML = "";
  const renderRow = (c, i) => {
    const row = document.createElement("tr");
    const highlight = (i === 0) ? "bg-green-900/30" : "border-b border-gray-800";
    const bm = c.bitmask_score != null ? c.bitmask_score : 1.0;
    const bmColor = bm >= 1.0 ? "text-green-400" : bm >= 0.5 ? "text-amber-400" : "text-red-400";
    row.className = highlight;
    row.innerHTML = `
      <td class="py-1 px-2 font-mono text-blue-300">${c.script_id || "—"}</td>
      <td class="py-1 px-2 truncate max-w-xs">${c.script_text || "—"}</td>
      <td class="py-1 px-2 text-right">${(c.final_score || 0).toFixed(4)}</td>
      <td class="py-1 px-2 text-right ${bmColor}">${bm.toFixed(2)}</td>
      <td class="py-1 px-2 text-right">${(c.win_rate || 0).toFixed(3)}</td>
      <td class="py-1 px-2 text-right">${(c.sas || 0).toFixed(3)}</td>
      <td class="py-1 px-2 text-right">${(c.vec_score || 0).toFixed(3)}</td>
    `;
    tbody.appendChild(row);
  };
  if (candidates && candidates.length > 0) {
    candidates.forEach((c, i) => renderRow(c, i));
  } else if (rec) {
    renderRow(rec, 0);
  }
}

let sioSocket = null;
let sioSessionId = null;

function sioEmit(event, data) {
  return new Promise((resolve, reject) => {
    const socket = sioConnect();
    socket.emit(event, data, (response) => {
      if (response && response.error) {
        reject(new Error(response.error));
      } else {
        resolve(response);
      }
    });
  });
}

function sioConnect() {
  if (!sioSocket || !sioSocket.connected) {
    sioSocket = io("/", { path: "/socket.io" });
    sioSocket.on("connect_error", (err) => {
      console.error("Socket.IO connect error:", err);
    });
    sioSocket.on("recommendation", (data) => {
      if (data.conversation_state) {
        updateSioState(data.conversation_state);
      }
    });
  }
  return sioSocket;
}

async function sioStartSession() {
  try {
    const result = await sioEmit("start_session", { context: {} });
    if (result && result.session_id) {
      sioSessionId = result.session_id;
      document.getElementById("sio-session-id").textContent = sioSessionId;
      document.getElementById("sio-customer-btn").disabled = false;
      document.getElementById("sio-collector-btn").disabled = false;
      document.getElementById("sio-end-btn").disabled = false;
      updateSioState(result.conversation_state);
      addTranscriptEntry("system", "Session started: " + sioSessionId, null);
    }
  } catch (e) {
    console.error("start_session error:", e);
  }
}

async function sioCustomerTurn() {
  if (!sioSessionId) return;
  const utterance = document.getElementById("sio-utterance").value;
  if (!utterance) return;
  try {
    const result = await sioEmit("customer_turn", {
      session_id: sioSessionId,
      utterance: utterance,
      conversation_context: utterance
    });
    updateSioState(result.conversation_state);
    addTranscriptEntry("customer", utterance, result);
    document.getElementById("sio-utterance").value = "";
  } catch (e) {
    console.error("customer_turn error:", e);
  }
}

async function sioCollectorTurn() {
  if (!sioSessionId) return;
  const utterance = document.getElementById("sio-utterance").value;
  if (!utterance) return;
  try {
    const result = await sioEmit("collector_turn", {
      session_id: sioSessionId,
      utterance: utterance
    });
    updateSioState(result.conversation_state);
    addTranscriptEntry("collector", utterance, result);
    document.getElementById("sio-utterance").value = "";
  } catch (e) {
    console.error("collector_turn error:", e);
  }
}

async function sioEndSession() {
  if (!sioSessionId) return;
  try {
    const result = await sioEmit("end_session", { session_id: sioSessionId });
    addTranscriptEntry("system", "Session ended", null);
  } catch (e) {
    console.error("end_session error:", e);
  }
  document.getElementById("sio-customer-btn").disabled = true;
  document.getElementById("sio-collector-btn").disabled = true;
  document.getElementById("sio-end-btn").disabled = true;
  sioSessionId = null;
  document.getElementById("sio-session-id").textContent = "—";
}

function updateSioState(state) {
  document.getElementById("sio-state").textContent = JSON.stringify(state, null, 2);
}

function addTranscriptEntry(role, utterance, result) {
  const container = document.getElementById("sio-transcript");
  const entry = document.createElement("div");
  if (role === "customer") {
    entry.innerHTML = `<span class="text-blue-300">[customer]</span> ${utterance}`;
  } else if (role === "collector") {
    entry.innerHTML = `<span class="text-purple-300">[collector]</span> ${utterance}`;
  } else {
    entry.innerHTML = `<span class="text-gray-400">[${role}]</span> ${utterance}`;
  }
  if (result && result.script_text) {
    entry.innerHTML += `<br><span class="text-green-300">→ ${result.script_text}</span> <span class="text-gray-500">(score: ${(result.final_score || 0).toFixed(3)})</span>`;
  }
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
}
