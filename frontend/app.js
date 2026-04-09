const messagesEl = document.getElementById("messages");
const chipsEl = document.getElementById("chips");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const richContentEl = document.getElementById("rich-content");
const skillsEl = document.getElementById("skills");
const exportButtonEl = document.getElementById("export-pdf");

let sessionId = null;
let activeSkills = [];
let skillCatalog = [];
let conversationHistory = [];
let latestRichContent = {};
let latestMetadata = {};

function renderMessage(role, text, sources = []) {
  conversationHistory.push({ role, text, sources });
  const div = document.createElement("div");
  div.className = `message ${role}`;
  let inner = `<div>${renderMarkdown(text)}</div>`;
  if (sources.length) {
    const links = sources
      .map((item) => `<a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>`)
      .join(" · ");
    inner += `<div class="meta">来源：${links}</div>`;
  }
  div.innerHTML = inner;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(text) {
  const escaped = escapeHtml(text);
  const lines = escaped.split("\n");
  const parts = [];
  let listItems = [];

  function flushList() {
    if (!listItems.length) {
      return;
    }
    parts.push(`<ul>${listItems.map((item) => `<li>${formatInline(item)}</li>`).join("")}</ul>`);
    listItems = [];
  }

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      return;
    }

    if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      listItems.push(trimmed.slice(2));
      return;
    }

    flushList();
    parts.push(`<p>${formatInline(trimmed)}</p>`);
  });

  flushList();
  return parts.join("");
}

function renderChips(actions) {
  chipsEl.innerHTML = "";
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.className = "chip";
    button.type = "button";
    button.textContent = action;
    button.addEventListener("click", () => {
      inputEl.value = action;
      formEl.requestSubmit();
    });
    chipsEl.appendChild(button);
  });
}

function renderSkills(skills) {
  skillCatalog = skills;
  skillsEl.innerHTML = "";
  skills.forEach((skill) => {
    const button = document.createElement("button");
    button.className = "skill-tile";
    button.type = "button";
    button.dataset.skillId = skill.id;
    if (activeSkills.includes(skill.id)) {
      button.classList.add("selected");
    }
    button.innerHTML = `<strong>${escapeHtml(skill.name)}</strong><span>${escapeHtml(skill.tagline)}</span>`;
    button.addEventListener("click", () => {
      toggleSkill(skill.id);
    });
    skillsEl.appendChild(button);
  });
}

function toggleSkill(skillId) {
  if (activeSkills.includes(skillId)) {
    activeSkills = activeSkills.filter((item) => item !== skillId);
  } else {
    activeSkills = [...activeSkills, skillId];
  }
  renderSkills(skillCatalog);
}

function renderRichContent(richContent = {}) {
  latestRichContent = richContent;
  const hotels = richContent.hotels || [];
  const attractions = richContent.attractions || [];
  const attractionImages = richContent.attraction_images || [];
  const meals = richContent.meals || [];
  const route = richContent.route || {};

  if (!hotels.length && !attractions.length && !attractionImages.length && !meals.length && !route.map_url) {
    richContentEl.classList.add("hidden");
    richContentEl.innerHTML = "";
    return;
  }

  const hotelHtml = hotels.length
    ? `
      <section class="rich-card">
        <h3>酒店推荐</h3>
        <div class="hotel-grid">
          ${hotels
            .map(
              (hotel) => `
                <article class="hotel-card">
                  <h4>${escapeHtml(hotel.name || "酒店")}</h4>
                  <p>${escapeHtml(hotel.description || "可进一步查看位置、交通和房型。")}</p>
                  <a href="${hotel.booking_url || "#"}" target="_blank" rel="noreferrer">查看详情</a>
                </article>
              `,
            )
            .join("")}
        </div>
      </section>
    `
    : "";

  const attractionHtml = attractions.length
    ? `
      <section class="rich-card">
        <h3>热门景点推荐</h3>
        <div class="attraction-list">
          ${attractions
            .map(
              (attraction) => `
                <article class="attraction-card">
                  <div>
                    <h4>${escapeHtml(attraction.name || "景点")}</h4>
                    <p>${escapeHtml(attraction.description || "适合进一步查看详情与开放信息。")}</p>
                  </div>
                  <a href="${attraction.detail_url || "#"}" target="_blank" rel="noreferrer">查看攻略</a>
                </article>
              `,
            )
            .join("")}
        </div>
      </section>
    `
    : "";

  const imageHtml = attractionImages.length
    ? `
      <section class="rich-card">
        <h3>景点图片参考</h3>
        <div class="image-grid">
          ${attractionImages
            .map(
              (image) => `
                <a class="image-tile" href="${image.source_url || image.image_url}" target="_blank" rel="noreferrer">
                  <img src="${image.thumbnail_url || image.image_url}" alt="${escapeHtml(image.title || "景点图片")}" />
                  <span>${escapeHtml(image.title || "景点图片")}</span>
                </a>
              `,
            )
            .join("")}
        </div>
      </section>
    `
    : "";

  const mealHtml = meals.length
    ? `
      <section class="rich-card">
        <h3>用餐建议</h3>
        <div class="meal-list">
          ${meals
            .map(
              (meal) => `
                <article class="meal-card">
                  <div>
                    <p class="meal-type">${escapeHtml(meal.meal_type || "用餐")}</p>
                    <h4>${escapeHtml(meal.name || "推荐餐厅")}</h4>
                    <p>${escapeHtml(meal.description || "适合作为行程中的用餐点。")}</p>
                  </div>
                  <a href="${meal.detail_url || "#"}" target="_blank" rel="noreferrer">查看位置</a>
                </article>
              `,
            )
            .join("")}
        </div>
      </section>
    `
    : "";

  const steps = (route.steps || [])
    .map(
      (step) => `
        <li>
          <span>${escapeHtml(step.instruction || "继续前进")}</span>
          <small>${step.distance_m ?? "-"} 米 · ${step.duration_s ?? "-"} 秒</small>
        </li>
      `,
    )
    .join("");

  const routeHtml = route.map_url
    ? `
      <section class="rich-card">
        <h3>地图路线引导</h3>
        <p class="route-summary">
          ${escapeHtml(route.origin?.name || route.origin?.city || "起点")} →
          ${escapeHtml(route.destination?.name || route.destination?.city || "终点")}
        </p>
        <p class="route-summary">约 ${route.distance_km ?? "-"} 公里，约 ${route.duration_min ?? "-"} 分钟</p>
        <ol class="route-steps">${steps}</ol>
        <a class="route-link" href="${route.map_url}" target="_blank" rel="noreferrer">打开地图查看完整路线</a>
      </section>
    `
    : "";

  richContentEl.classList.remove("hidden");
  richContentEl.innerHTML = `${hotelHtml}${attractionHtml}${imageHtml}${mealHtml}${routeHtml}`;
}

function buildPrintDocument() {
  const selectedSkillNames = activeSkills
    .map((skillId) => skillCatalog.find((item) => item.id === skillId)?.name)
    .filter(Boolean);
  const todayLabel = new Date().toLocaleDateString("zh-CN");
  const route = latestRichContent.route || {};
  const inferredDestination =
    route.destination?.city ||
    route.destination?.name ||
    latestMetadata.trip_summary?.match(/目的地：([^|]+)/)?.[1]?.trim() ||
    latestRichContent.attractions?.[0]?.business_area ||
    latestRichContent.hotels?.[0]?.area_hint ||
    "定制旅行";
  const coverTitle = `${escapeHtml(inferredDestination)}旅行计划书`;

  const messageHtml = conversationHistory
    .map(
      (item) => `
        <section class="print-message ${item.role}">
          <p class="print-role">${item.role === "user" ? "用户" : "旅行助手"}</p>
          <div class="print-content">${renderMarkdown(item.text)}</div>
          ${
            item.sources?.length
              ? `<p class="print-sources">来源：${item.sources.map((source) => escapeHtml(source.title)).join(" · ")}</p>`
              : ""
          }
        </section>
      `,
    )
    .join("");

  const hotels = (latestRichContent.hotels || [])
    .map(
      (hotel) => `
        <article class="summary-card">
          <p class="card-tag">酒店推荐</p>
          <h3>${escapeHtml(hotel.name || "酒店")}</h3>
          <p>${escapeHtml(hotel.description || "适合进一步查看位置与房型。")}</p>
        </article>
      `,
    )
    .join("");
  const attractions = (latestRichContent.attractions || [])
    .map(
      (item) => `
        <article class="summary-card">
          <p class="card-tag">景点推荐</p>
          <h3>${escapeHtml(item.name || "景点")}</h3>
          <p>${escapeHtml(item.description || "适合安排进本次行程。")}</p>
        </article>
      `,
    )
    .join("");
  const meals = (latestRichContent.meals || [])
    .map(
      (item) => `
        <article class="summary-card">
          <p class="card-tag">${escapeHtml(item.meal_type || "用餐建议")}</p>
          <h3>${escapeHtml(item.name || "推荐餐厅")}</h3>
          <p>${escapeHtml(item.description || "适合作为行程中的用餐点。")}</p>
        </article>
      `,
    )
    .join("");
  const routeSteps = (latestRichContent.route?.steps || [])
    .map((step) => `<li>${escapeHtml(step.instruction || "继续前进")}</li>`)
    .join("");
  const tripSummary = latestMetadata.trip_summary || "当前暂无摘要，建议继续补充出发地、天数和预算。";

  return `
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="UTF-8" />
        <title>${coverTitle}</title>
        <style>
          @page { margin: 18mm 14mm; }
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #1f2937; background: #f8fafc; }
          h1, h2, h3, p { margin: 0; }
          .page { page-break-after: always; padding: 24px; }
          .page:last-child { page-break-after: auto; }
          .cover {
            min-height: 92vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            background:
              radial-gradient(circle at top right, rgba(16, 163, 127, 0.14), transparent 30%),
              linear-gradient(145deg, #ffffff, #f0fdf7 46%, #fff7ed);
            border: 1px solid #dbe4df;
            border-radius: 28px;
          }
          .cover-top { display: grid; gap: 16px; }
          .cover-kicker { color: #0f766e; font-size: 13px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; }
          .cover-title { font-size: 42px; line-height: 1.05; letter-spacing: -0.04em; max-width: 620px; }
          .cover-subtitle { max-width: 560px; color: #4b5563; font-size: 17px; line-height: 1.7; }
          .cover-meta { display: flex; flex-wrap: wrap; gap: 10px; }
          .pill { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #ecfdf5; color: #0f766e; font-size: 12px; font-weight: 700; }
          .cover-footer { color: #6b7280; font-size: 14px; }
          .section { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 24px; margin-top: 18px; padding: 22px; }
          .section h2 { font-size: 20px; margin-bottom: 14px; }
          .lead { color: #4b5563; margin-bottom: 24px; }
          .summary-grid { display: grid; gap: 14px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .summary-card { border: 1px solid #e5e7eb; border-radius: 18px; padding: 16px; background: #fcfcfd; }
          .summary-card h3 { margin: 0 0 8px; font-size: 16px; }
          .summary-card p { color: #4b5563; line-height: 1.6; }
          .card-tag { margin-bottom: 8px; color: #0f766e; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
          .summary-text { color: #374151; line-height: 1.8; font-size: 15px; }
          .print-message { border: 1px solid #e5e7eb; border-radius: 14px; padding: 14px 16px; margin-bottom: 12px; background: #ffffff; }
          .print-message.user { background: #f0fdf4; }
          .print-role { margin: 0 0 8px; font-size: 12px; font-weight: 700; color: #0f766e; text-transform: uppercase; letter-spacing: 0.08em; }
          .print-content p { margin: 0 0 8px; line-height: 1.7; }
          .print-content ul { margin: 0; padding-left: 20px; }
          .print-content li { margin-bottom: 6px; }
          .print-sources { margin: 10px 0 0; color: #6b7280; font-size: 12px; }
          .route-box { border: 1px dashed #cbd5e1; border-radius: 16px; padding: 16px; background: #f8fafc; }
          ol { margin: 10px 0 0; padding-left: 20px; }
          li { line-height: 1.7; }
        </style>
      </head>
      <body>
        <section class="page cover">
          <div class="cover-top">
            <p class="cover-kicker">Travel Assistant</p>
            <h1 class="cover-title">${coverTitle}</h1>
            <p class="cover-subtitle">把对话里的灵感、偏好和实时信息整理成一份更便于查看、保存和分享的旅行计划书。</p>
            <div class="cover-meta">
              <span class="pill">导出日期 · ${todayLabel}</span>
              <span class="pill">会话 · ${escapeHtml(sessionId || "未生成")}</span>
              ${selectedSkillNames.map((name) => `<span class="pill">${escapeHtml(name)}</span>`).join("")}
            </div>
          </div>
          <p class="cover-footer">目的地标题会根据当前会话的目的地、路线或摘要自动生成。</p>
        </section>
        <section class="page">
          <section class="section">
            <h2>行程摘要</h2>
            <p class="summary-text">${escapeHtml(tripSummary)}</p>
          </section>
          ${
            hotels || attractions || meals
              ? `
            <section class="section">
              <h2>推荐卡片</h2>
              <div class="summary-grid">
                ${hotels}
                ${attractions}
                ${meals}
              </div>
            </section>
          `
              : ""
          }
          ${
            routeSteps
              ? `
            <section class="section">
              <h2>路线概览</h2>
              <div class="route-box">
                <p class="summary-text">${escapeHtml(route.origin?.name || route.origin?.city || "起点")} → ${escapeHtml(route.destination?.name || route.destination?.city || "终点")}</p>
                <p class="summary-text">约 ${route.distance_km ?? "-"} 公里，约 ${route.duration_min ?? "-"} 分钟</p>
                <ol>${routeSteps}</ol>
              </div>
            </section>
          `
              : ""
          }
        </section>
        <section class="page">
          <section class="section">
          <h2>对话记录</h2>
          ${messageHtml || "<p>当前还没有可导出的对话内容。</p>"}
          </section>
        </section>
      </body>
    </html>
  `;
}

function exportToPdf() {
  const iframe = document.createElement("iframe");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.setAttribute("aria-hidden", "true");
  document.body.appendChild(iframe);

  const printDocument = iframe.contentWindow?.document;
  if (!printDocument || !iframe.contentWindow) {
    iframe.remove();
    return;
  }

  printDocument.open();
  printDocument.write(buildPrintDocument());
  printDocument.close();

  const cleanup = () => {
    window.setTimeout(() => iframe.remove(), 500);
  };

  iframe.onload = () => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    cleanup();
  };

  window.setTimeout(() => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    cleanup();
  }, 250);
}

async function sendMessage(message) {
  renderMessage("user", message);
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: "demo-user",
      message,
      session_id: sessionId,
      skills: activeSkills,
    }),
  });
  const payload = await response.json();
  if (!response.ok) {
    renderMessage("assistant", payload.detail || "请求失败，请稍后再试。");
    return;
  }
  sessionId = payload.session_id;
  latestMetadata = payload.metadata || {};
  renderMessage("assistant", payload.response, payload.sources || []);
  renderRichContent(payload.metadata?.rich_content || {});
  renderChips(payload.suggested_actions || []);
}

async function loadSkills() {
  try {
    const response = await fetch("/api/skills");
    const payload = await response.json();
    renderSkills(payload.skills || []);
  } catch (error) {
    skillsEl.innerHTML = "";
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) {
    return;
  }
  inputEl.value = "";
  await sendMessage(message);
});

exportButtonEl.addEventListener("click", () => {
  exportToPdf();
});

renderMessage("assistant", "告诉我你的目的地、时间或预算，我可以先帮你判断是否值得去，再逐步细化成行程建议。你也可以先在左侧点选想要的旅行技能。");
loadSkills();
