"use strict";

const state = {
  payload: null,
  mode: "static",
  config: null,
};

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function renderSummary(payload) {
  const s = payload.summary;
  const cards = [
    {
      value: s.hybrid.recall,
      label: "M1 稀疏融合 recall@3",
      hint: `MRR ${s.hybrid.mrr} · ${s.hybrid.chunks} chunks`,
    },
    {
      value: s.dense.recall,
      label: "M2 dense recall@3",
      hint: `MRR ${s.dense.mrr} · 没赢稀疏融合`,
    },
    {
      value: s.metamorphic.fixed_by_normalizer,
      label: "归一化修复的违规",
      hint: `INVARIANT ${s.metamorphic.invariant_before} → ${s.metamorphic.invariant_after}`,
    },
    {
      value: `${s.metamorphic.desirable_before} → ${s.metamorphic.desirable_after}`,
      label: "DESIRABLE 违规",
      hint: "仍有剩余，不能宣称已解决",
    },
    {
      value: s.rerank.delta_recall,
      label: "bigram 重排 Δrecall",
      hint: `on ${s.rerank.mrr_on} / off ${s.rerank.mrr_off}`,
    },
  ];
  const root = $("summary");
  root.replaceChildren();
  for (const card of cards) {
    const node = el("div", "metric-card");
    node.append(el("span", "metric-value", card.value));
    node.append(el("span", "metric-label", card.label));
    node.append(el("span", "metric-hint", card.hint));
    root.append(node);
  }
}

function renderLayers(payload) {
  const root = $("layers");
  root.replaceChildren();
  for (const layer of payload.layers) {
    const card = el("div", `layer-card tone-${layer.tone || "neutral"}`);
    const head = el("div", "layer-head");
    head.append(el("h2", null, layer.title));
    head.append(el("span", "layer-scope", layer.scope));
    card.append(head);
    const metrics = el("div", "layer-metrics");
    for (const metric of layer.metrics || []) {
      const box = el("div", "layer-metric");
      box.append(el("span", "label", metric.label));
      box.append(el("span", "value", fmt(metric.value)));
      box.append(el("span", "source", metric.source));
      metrics.append(box);
    }
    card.append(metrics);
    card.append(el("p", "layer-verdict", layer.verdict));
    root.append(card);
  }
}

function renderRerank(ablation) {
  const table = el("table", "data-table");
  const thead = el("thead");
  const head = el("tr");
  head.append(el("th", null, "配置"));
  head.append(el("th", null, "recall@3"));
  head.append(el("th", null, "MRR"));
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const row of ablation.rows || []) {
    const tr = el("tr");
    tr.append(el("td", null, row.label));
    tr.append(el("td", null, fmt(row.recall)));
    tr.append(el("td", null, fmt(row.mrr)));
    body.append(tr);
  }
  table.append(body);
  return table;
}

function renderSweep(ablation) {
  const table = el("table", "data-table");
  const thead = el("thead");
  const head = el("tr");
  head.append(el("th", null, "w_cos"));
  head.append(el("th", null, "w_bm25"));
  head.append(el("th", null, "recall@3"));
  head.append(el("th", null, "MRR"));
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const point of ablation.points || []) {
    const tr = el("tr");
    if (point.w_cos === ablation.best.w_cos && point.mrr === ablation.best.mrr) {
      tr.classList.add("is-best");
    }
    if (point.w_cos === ablation.chosen.w_cos && point.mrr === ablation.chosen.mrr) {
      tr.classList.add("is-chosen");
    }
    tr.append(el("td", null, fmt(point.w_cos)));
    tr.append(el("td", null, fmt(point.w_bm25)));
    tr.append(el("td", null, fmt(point.recall_at_3)));
    tr.append(el("td", null, fmt(point.mrr)));
    body.append(tr);
  }
  table.append(body);
  return table;
}

function renderOverlap(ablation) {
  const table = el("table", "data-table");
  const thead = el("thead");
  const head = el("tr");
  head.append(el("th", null, "overlap"));
  head.append(el("th", null, "recall@3"));
  head.append(el("th", null, "MRR"));
  head.append(el("th", null, "chunks"));
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const point of ablation.points || []) {
    const tr = el("tr");
    if (point.overlap === ablation.best.overlap && point.mrr === ablation.best.mrr) {
      tr.classList.add("is-best");
    }
    if (point.overlap === ablation.chosen.overlap && point.mrr === ablation.chosen.mrr) {
      tr.classList.add("is-chosen");
    }
    tr.append(el("td", null, fmt(point.overlap)));
    tr.append(el("td", null, fmt(point.recall_at_3)));
    tr.append(el("td", null, fmt(point.mrr)));
    tr.append(el("td", null, fmt(point.chunks)));
    body.append(tr);
  }
  table.append(body);
  return table;
}

function renderCutoff(ablation) {
  const table = el("table", "data-table");
  const thead = el("thead");
  const head = el("tr");
  head.append(el("th", null, "candidates"));
  head.append(el("th", null, "recall@3"));
  head.append(el("th", null, "MRR"));
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const point of ablation.points || []) {
    const tr = el("tr");
    tr.append(el("td", null, fmt(point.candidates)));
    tr.append(el("td", null, fmt(point.recall_at_3)));
    tr.append(el("td", null, fmt(point.mrr)));
    body.append(tr);
  }
  table.append(body);
  return table;
}

function renderAblations(payload) {
  const root = $("ablations");
  root.replaceChildren();
  for (const ablation of payload.ablations || []) {
    const card = el("div", "ablation");
    const head = el("div", "ablation-head");
    head.append(el("h3", "ablation-title", ablation.title));
    if (ablation.id === "rerank") {
      head.append(el("span", "tag tag-chosen", `Δrecall=${ablation.delta_recall}`));
    }
    card.append(head);
    if (ablation.id === "rerank") card.append(renderRerank(ablation));
    if (ablation.id === "sweep") card.append(renderSweep(ablation));
    if (ablation.id === "overlap") card.append(renderOverlap(ablation));
    if (ablation.id === "cutoff") card.append(renderCutoff(ablation));
    card.append(el("p", "ablation-note", ablation.note));
    card.append(el("p", "ablation-source", ablation.source));
    root.append(card);
  }
}

function renderQueryResults(results) {
  const root = $("query-results");
  root.replaceChildren();
  for (const [index, result] of (results || []).entries()) {
    const card = el("div", "query-result");
    const head = el("div", "query-head");
    head.append(el("span", "chunk", `${index + 1}. ${result.chunk_id} · ${result.title}`));
    head.append(el("span", "score", `score=${result.score}`));
    card.append(head);
    card.append(el("p", "text", result.text));
    root.append(card);
  }
  if (!results || !results.length) {
    root.append(el("p", "muted", "没有命中。"));
  }
}

function renderFindings(payload) {
  const findings = $("findings");
  findings.replaceChildren();
  for (const item of payload.findings || []) {
    findings.append(el("li", null, item));
  }
  const refutes = $("refutes");
  refutes.replaceChildren();
  for (const item of payload.refutes || []) {
    refutes.append(el("li", null, item));
  }
}

function renderMeta(payload) {
  const meta = payload.meta || {};
  const verification = payload.verification || {};
  const rows = [
    ["仓库", meta.repo],
    ["Demo", meta.demo],
    ["提交", meta.commit],
    ["工作区", meta.worktree_dirty ? "有未提交改动" : "干净（results.json 除外）"],
    ["生成时间 (UTC)", meta.generated_at],
    ["模式", meta.mode],
    ["Python", meta.python],
    ["断言", `${verification.status || "—"} (${(verification.checks || []).length} checks)`],
    ["hybrid 源", payload.sources ? payload.sources.hybrid : "—"],
    ["dense 源", payload.sources ? payload.sources.dense : "—"],
    ["metamorphic 源", payload.sources ? payload.sources.metamorphic : "—"],
    ["baseline 源", payload.sources ? payload.sources.baseline : "—"],
  ];
  if (meta.dirty_paths && meta.dirty_paths.length) {
    rows.push(["未提交路径", meta.dirty_paths.join(", ")]);
  }
  const dl = $("meta");
  dl.replaceChildren();
  for (const [key, value] of rows) {
    dl.append(el("dt", null, key));
    dl.append(el("dd", null, value === undefined || value === null ? "—" : value));
  }
}

function renderMode() {
  const badge = $("mode-badge");
  badge.className = "badge " + (state.mode === "live" ? "badge-live" : "badge-static");
  badge.textContent = state.mode === "live" ? "本地实时" : "静态回放";
  $("mode-note").textContent =
    state.mode === "live"
      ? "结果面板是回放；/api/query 会实时跑冻结基线。"
      : "这是提交进仓库的结果回放。运行 python3 demo/server.py 可交互查询冻结基线。";
  $("rerun").disabled = state.mode !== "live";

  const input = $("query-input");
  const button = $("query-button");
  const live = state.mode === "live";
  input.disabled = !live;
  button.disabled = !live;
  $("query-note").textContent = live
    ? "只在冻结基线上检索，不碰私有语料。"
    : "静态回放不支持查询；本地运行 python3 demo/server.py 后可交互。";
}

function renderAll() {
  renderSummary(state.payload);
  renderLayers(state.payload);
  renderAblations(state.payload);
  renderFindings(state.payload);
  renderMeta(state.payload);
  renderMode();
  $("query-scope").textContent = state.payload.baseline_query.scope;
  $("query-input").placeholder = `例如：${state.payload.baseline_query.example}`;
}

async function loadConfig() {
  try {
    const response = await fetch("./config.json", { cache: "no-store" });
    if (response.ok) return await response.json();
  } catch (error) {
    // file:// or a static host without config.json: stay in replay mode.
  }
  return { mode: "static" };
}

async function rerun() {
  const button = $("rerun");
  const status = $("rerun-status");
  button.disabled = true;
  status.textContent = "正在重建结果回放…";
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.payload = await response.json();
    renderAll();
    status.textContent = `重建完成 · ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    status.textContent = `重建失败：${error.message}`;
  } finally {
    button.disabled = state.mode !== "live";
  }
}

async function queryBaseline(event) {
  event.preventDefault();
  if (state.mode !== "live") return;
  const query = $("query-input").value.trim();
  if (!query) return;
  const root = $("query-results");
  root.replaceChildren(el("p", "muted", "检索中…"));
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderQueryResults(data.results);
  } catch (error) {
    root.replaceChildren(el("p", "muted", `检索失败：${error.message}`));
  }
}

async function init() {
  try {
    state.config = await loadConfig();
    state.mode = state.config.mode === "live" ? "live" : "static";
    const response = await fetch("./results.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`results.json HTTP ${response.status}`);
    state.payload = await response.json();
    renderAll();

    $("rerun").addEventListener("click", rerun);
    $("query-form").addEventListener("submit", queryBaseline);
  } catch (error) {
    const box = $("error");
    box.hidden = false;
    box.textContent =
      `加载失败：${error.message}。如果你在用 file:// 打开页面，` +
      "请运行 python3 demo/server.py 或 python3 -m http.server -d demo/public。";
  }
}

document.addEventListener("DOMContentLoaded", init);
