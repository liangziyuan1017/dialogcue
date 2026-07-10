const DEFAULT_REQUEST = {
  customer_utterance: "嗯，好的，我明白了。那您帮我看看，目前有什么还款方案可以申请",
  conversation_context: "您好，请问是李先生吗？我是招商银行信用卡中心。您的信用卡已逾期。 嗯。 今天来电想跟您确认还款事宜。 哦。 您看目前方便处理一下欠款吗？ 最近手头确实紧。",
  conversation_state: {
    branch_key: { facts: ["situational_hardship"] },
    inherited_facts: ["debt_acknowledgment", "situational_hardship"],
    inherited_emotions: [],
    willingness: "conditional"
  },
  context: {
    has_business_loan: false,
    has_mortgage: false,
    has_other_loan: true,
    recent_repayment: false,
    is_high_risk_proxy_complaint: false,
    is_proxy_intermediary_complaint: false,
    has_social_insurance: true,
    has_risk_flag: true,
    has_complaint: false,
    has_vehicle: false,
    education: "college",
    risk_level: 3,
    complaint_score: 0,
    days_delinquent: 30,
    recent_contact_count: 5,
    business_loan_balance: 0,
    mortgage_balance: 0,
    other_loan_balance: 50000,
    wealth_value: 0,
    current_balance: 200000
  }
};

let restEditor = null;
let responseEditor = null;
let sioContextEditor = null;

const DEFAULT_CONTEXT = {
  has_business_loan: false,
  has_mortgage: false,
  has_other_loan: true,
  recent_repayment: false,
  is_high_risk_proxy_complaint: false,
  is_proxy_intermediary_complaint: false,
  has_social_insurance: true,
  has_risk_flag: true,
  has_complaint: false,
  has_vehicle: false,
  education: "college",
  risk_level: 3,
  complaint_score: 0,
  days_delinquent: 30,
  recent_contact_count: 5,
  business_loan_balance: 0,
  mortgage_balance: 0,
  other_loan_balance: 50000,
  wealth_value: 0,
  current_balance: 200000
};

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

  sioContextEditor = CodeMirror.fromTextArea(document.getElementById("sio-context"), {
    mode: "javascript",
    json: true,
    lineNumbers: true,
    tabSize: 2
  });
  sioContextEditor.setValue(JSON.stringify(DEFAULT_CONTEXT, null, 2));

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
    let context = {};
    try {
      context = JSON.parse(sioContextEditor.getValue());
    } catch (e) {
      console.error("Invalid context JSON, using {}:", e);
    }
    const result = await sioEmit("start_session", { context });
    if (result && result.session_id) {
      sioSessionId = result.session_id;
      document.getElementById("sio-session-id").textContent = sioSessionId;
      document.getElementById("sio-customer-btn").disabled = false;
      document.getElementById("sio-collector-btn").disabled = false;
      document.getElementById("sio-end-btn").disabled = false;
      sioContextEditor.setOption("readOnly", true);
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
  sioContextEditor.setOption("readOnly", false);
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
