const output = document.querySelector("#output");
const connectionLine = document.querySelector("#connectionLine");
const chatList = document.querySelector("#chatList");
const messageList = document.querySelector("#messageList");
const conversationTitle = document.querySelector("#conversationTitle");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const readButton = document.querySelector("#readButton");
const draftButton = document.querySelector("#draftButton");
const useDraftButton = document.querySelector("#useDraftButton");
const draftPanel = document.querySelector("#draftPanel");
const draftText = document.querySelector("#draftText");
const unreadOnlyInput = document.querySelector("#unreadOnlyInput");
const processUnreadButton = document.querySelector("#processUnreadButton");
const autoProcessInput = document.querySelector("#autoProcessInput");
const automationLine = document.querySelector("#automationLine");
const botActivity = document.querySelector("#botActivity");

let activeChatId = null;
let activeChat = null;
let activeMessagesResponse = null;
let automationBusy = false;
let pollingTimer = null;

const POLLING_INTERVAL_MS = 3000;

document.querySelector("#refreshStatusButton").addEventListener("click", refreshStatus);
document.querySelector("#tokenButton").addEventListener("click", checkToken);
document.querySelector("#accountButton").addEventListener("click", loadAccount);
document.querySelector("#chatsButton").addEventListener("click", loadChats);
processUnreadButton.addEventListener("click", () => processUnread({ show: true }));
document.querySelector("#aiPingButton").addEventListener("click", pingAi);
document.querySelector("#webhooksButton").addEventListener("click", loadWebhookEvents);
document.querySelector("#sendForm").addEventListener("submit", sendMessage);
readButton.addEventListener("click", markRead);
draftButton.addEventListener("click", draftReply);
useDraftButton.addEventListener("click", useDraft);
autoProcessInput.addEventListener("change", syncServerAutoReply);

initialize();

async function initialize() {
  const status = await refreshStatus();
  if (status.avito_client_id_configured && status.avito_client_secret_configured) {
    try {
      await loadChats();
      await syncServerAutoReply();
      startPolling();
    } catch (error) {
      chatList.textContent = error.message;
    }
  }
}

async function refreshStatus() {
  const data = await api("/api/config/status");
  showOutput(data);
  const ready = data.avito_client_id_configured && data.avito_client_secret_configured;
  connectionLine.textContent = ready
    ? `Avito: ${data.avito_client_id_preview || "configured"} · DeepSeek: ${
        data.deepseek_api_key_configured ? data.deepseek_model : "not configured"
      }`
    : "Avito credentials are not configured";
  connectionLine.className = ready ? "" : "error";
  return data;
}

async function checkToken() {
  showOutput(await api("/api/avito/token-check", { method: "POST" }));
}

async function loadAccount() {
  showOutput(await api("/api/avito/account"));
}

async function pingAi() {
  showOutput(await api("/api/ai/ping", { method: "POST" }));
}

async function loadChats({ show = true } = {}) {
  const params = new URLSearchParams({
    limit: "20",
    unread_only: unreadOnlyInput.checked ? "true" : "false",
  });
  const data = await api(`/api/avito/chats?${params.toString()}`);
  if (show) showOutput(data);
  renderChats(data.chats || []);
}

async function loadMessages(chatId, { resetDraft = true, show = true } = {}) {
  activeChatId = chatId;
  activeChat = null;
  activeMessagesResponse = null;
  if (resetDraft) hideDraft();
  conversationTitle.textContent = chatId;
  messageInput.disabled = false;
  sendButton.disabled = false;
  readButton.disabled = false;
  draftButton.disabled = true;
  try {
    const chat = await api(`/api/avito/chats/${encodeURIComponent(chatId)}`);
    const data = await api(`/api/avito/chats/${encodeURIComponent(chatId)}/messages?limit=50`);
    activeChat = chat;
    activeMessagesResponse = data;
    if (show) showOutput(data);
    renderMessages(normalizeMessages(data));
    draftButton.disabled = false;
  } catch (error) {
    renderError(error.message);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (!activeChatId) return;
  const text = messageInput.value.trim();
  if (!text) return;
  const data = await api(`/api/avito/chats/${encodeURIComponent(activeChatId)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  messageInput.value = "";
  showOutput(data);
  await loadMessages(activeChatId);
}

async function markRead() {
  if (!activeChatId) return;
  showOutput(await api(`/api/avito/chats/${encodeURIComponent(activeChatId)}/read`, { method: "POST" }));
}

async function processUnread({ show = false } = {}) {
  if (automationBusy) return;
  automationBusy = true;
  processUnreadButton.disabled = true;
  setAutomationLine("Checking unread...");
  setBotActivity("Бот проверяет входящие. Если есть новое сообщение, он принимает его в работу и начинает думать.", "active");
  try {
    const data = await api("/api/avito/process-unread", { method: "POST" });
    if (show || data.sent_count || data.handoff_count) showOutput(data);
    const sent = data.sent_count || 0;
    const handoff = data.handoff_count || 0;
    setAutomationLine(sent || handoff ? `Auto: sent ${sent}, handoff ${handoff}` : "Auto: no unread");
    updateBotActivityFromProcessing(data);
    await refreshLiveView();
  } catch (error) {
    setAutomationLine(`Auto error: ${error.message}`);
    setBotActivity(`Ошибка автоответчика: ${error.message}`, "error");
    if (show) showOutput({ error: error.message });
  } finally {
    automationBusy = false;
    processUnreadButton.disabled = false;
  }
}

async function refreshLiveView() {
  await loadChats({ show: false });
  if (activeChatId) {
    await loadMessages(activeChatId, { resetDraft: false, show: false });
  }
}

function startPolling() {
  if (pollingTimer) return;
  pollingTimer = window.setInterval(async () => {
    if (document.hidden || automationBusy) return;
    try {
      await refreshBotStatus();
      await refreshLiveView();
    } catch (error) {
      setAutomationLine(`Refresh error: ${error.message}`);
    }
  }, POLLING_INTERVAL_MS);
}

async function syncServerAutoReply() {
  const endpoint = autoProcessInput.checked ? "/api/bot/autoreply/start" : "/api/bot/autoreply/stop";
  const status = await api(endpoint, { method: "POST" });
  updateBotStatus(status);
}

async function refreshBotStatus() {
  const status = await api("/api/bot/autoreply/status");
  updateBotStatus(status);
}

function updateBotStatus(status) {
  const state = status.task_state || "stopped";
  if (!status.enabled) {
    setAutomationLine("Auto reply off");
    if (!automationBusy) setBotActivity("Серверный автоответчик выключен");
    return;
  }

  if (state === "running") {
    setAutomationLine("Auto reply: backend thinking");
    setBotActivity("Серверный автоответчик проверяет входящие и отвечает независимо от вкладки браузера.", "active");
    return;
  }

  const result = status.last_result;
  if (result) {
    const sent = result.sent_count || 0;
    const handoff = result.handoff_count || 0;
    setAutomationLine(sent || handoff ? `Auto reply: sent ${sent}, handoff ${handoff}` : "Auto reply: waiting");
    updateBotActivityFromProcessing(result);
    return;
  }

  setAutomationLine("Auto reply: backend on");
  setBotActivity("Серверный автоответчик включен и ждёт входящих сообщений");
}

function setAutomationLine(text) {
  automationLine.textContent = text;
}

function setBotActivity(text, state = "") {
  botActivity.textContent = text;
  botActivity.className = `bot-activity ${state}`.trim();
}

function updateBotActivityFromProcessing(data) {
  const processed = Array.isArray(data.processed) ? data.processed : [];
  if (!processed.length) {
    setBotActivity("Бот ждёт входящих сообщений");
    return;
  }

  const activeResult = processed.find((item) => item.chat_id === activeChatId) || processed[0];
  const estimate = formatSeconds(activeResult.estimate_seconds);
  const duration = formatDuration(activeResult.duration_ms);
  const accepted = formatEpochTime(activeResult.accepted_at);

  if (activeResult.status === "sent") {
    setBotActivity(
      `Бот принял сообщение${accepted ? ` в ${accepted}` : ""}, оценка ${estimate}, отправил ответ за ${duration}`,
      "",
    );
    return;
  }

  if (activeResult.status === "handoff_required") {
    setBotActivity(
      `Бот принял сообщение${accepted ? ` в ${accepted}` : ""}, оценка ${estimate}, но остановил автоответ: нужен менеджер`,
      "active",
    );
    return;
  }

  if (activeResult.status === "failed") {
    setBotActivity(`Бот не смог обработать сообщение: ${extractResultError(activeResult.error)}`, "error");
    return;
  }

  setBotActivity("Бот проверил входящие, отвечать не нужно");
}

function formatSeconds(value) {
  if (!Number.isFinite(Number(value))) return "не задана";
  return `~${Math.round(Number(value))} сек`;
}

function formatDuration(value) {
  if (!Number.isFinite(Number(value))) return "неизвестно";
  const seconds = Number(value) / 1000;
  return seconds < 1 ? `${Math.round(Number(value))} мс` : `${seconds.toFixed(1)} сек`;
}

function formatEpochTime(value) {
  if (!Number.isFinite(Number(value))) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(Number(value) * 1000));
}

function extractResultError(error) {
  if (!error) return "unknown error";
  if (typeof error === "string") return error;
  if (error.error?.message) return error.error.message;
  if (error.message) return error.message;
  return JSON.stringify(error);
}

async function draftReply() {
  if (!activeChatId || !activeChat || !activeMessagesResponse) return;
  draftButton.disabled = true;
  draftText.textContent = "Generating...";
  draftPanel.hidden = false;
  try {
    const data = await api("/api/ai/draft-reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat: activeChat, messages: activeMessagesResponse }),
    });
    showOutput(data);
    draftText.textContent = data.handoff_required
      ? `Handoff required (${data.handoff_reason || "reason unknown"}): ${data.text}`
      : data.text;
  } catch (error) {
    draftText.textContent = error.message;
  } finally {
    draftButton.disabled = false;
  }
}

function useDraft() {
  const text = draftText.textContent.trim();
  if (!text || text === "Generating...") return;
  messageInput.value = text;
  messageInput.focus();
}

async function loadWebhookEvents() {
  showOutput(await api("/api/webhooks/avito/events"));
}

function renderChats(chats) {
  chatList.innerHTML = "";
  if (!chats.length) {
    chatList.textContent = "No chats";
    return;
  }
  chats.forEach((chat) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chat-item ${chat.id === activeChatId ? "active" : ""}`;
    button.addEventListener("click", () => loadMessages(chat.id));

    const title = document.createElement("div");
    title.className = "chat-title";
    title.textContent = chat.context?.value?.title || chat.id;

    const subtitle = document.createElement("div");
    subtitle.className = "chat-subtitle";
    subtitle.textContent = chat.last_message?.content?.text || chat.context?.value?.price_string || "No text";

    button.append(title, subtitle);
    chatList.append(button);
  });
}

function renderMessages(messages) {
  messageList.innerHTML = "";
  if (!messages.length) {
    messageList.textContent = "No messages";
    return;
  }
  const orderedMessages = orderMessages(messages);
  appendTimelineEdge("Начало переписки");

  let currentDateKey = "";
  orderedMessages.forEach((message, index) => {
    const createdAt = getMessageDate(message);
    const dateKey = createdAt ? createdAt.toDateString() : "unknown";
    if (dateKey !== currentDateKey) {
      currentDateKey = dateKey;
      appendDateSeparator(createdAt);
    }

    const item = document.createElement("article");
    const role = getMessageRole(message);
    item.className = `message ${role.className}`;

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const roleLabel = document.createElement("span");
    roleLabel.className = "message-role";
    roleLabel.textContent = role.label;

    const time = document.createElement("span");
    time.className = "message-time";
    time.textContent = formatMessageTime(createdAt, message.type);

    meta.append(roleLabel, time);

    const content = document.createElement("div");
    content.className = "message-content";
    appendMessageContent(content, message);

    item.append(meta, content);
    messageList.append(item);

    if (index === orderedMessages.length - 1) {
      appendTimelineEdge("Последнее сообщение");
    }
  });
}

function normalizeMessages(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.messages)) return data.messages;
  return [];
}

function orderMessages(messages) {
  return [...messages].sort((left, right) => {
    const leftTime = Number(left.created || left.created_at || 0);
    const rightTime = Number(right.created || right.created_at || 0);
    return leftTime - rightTime;
  });
}

function getMessageDate(message) {
  const timestamp = Number(message.created || message.created_at || 0);
  if (!timestamp) return null;
  return new Date(timestamp * 1000);
}

function appendDateSeparator(date) {
  const separator = document.createElement("div");
  separator.className = "date-separator";
  separator.textContent = date
    ? new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      }).format(date)
    : "Дата неизвестна";
  messageList.append(separator);
}

function appendTimelineEdge(text) {
  const edge = document.createElement("div");
  edge.className = "timeline-edge";
  edge.textContent = text;
  messageList.append(edge);
}

function getMessageRole(message) {
  const text = message.content?.text || "";
  const isSystem =
    message.type === "system" ||
    message.author_id === 1 ||
    (typeof text === "string" && text.includes("[Системное сообщение]"));

  if (isSystem) {
    return { label: "Система Avito", className: "system" };
  }
  if (message.direction === "out") {
    return { label: "Менеджер", className: "out" };
  }
  return { label: "Клиент", className: "in" };
}

function formatMessageTime(date, type) {
  const typeLabel = getMessageTypeLabel(type);
  if (!date) return typeLabel;
  const time = new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
  return `${time} · ${typeLabel}`;
}

function getMessageTypeLabel(type) {
  const labels = {
    text: "текст",
    image: "фото",
    voice: "голос",
    system: "системное",
    link: "ссылка",
    item: "объявление",
    file: "файл",
    location: "гео",
  };
  return labels[type] || type || "сообщение";
}

function appendMessageContent(container, message) {
  const content = message.content || {};
  const text = content.text || content.link?.text;

  if (typeof text === "string" && text.trim()) {
    container.textContent = cleanSystemText(text);
    return;
  }

  if (content.image) {
    const imageUrl = pickImageUrl(content.image);
    if (imageUrl) {
      const link = document.createElement("a");
      link.href = imageUrl;
      link.target = "_blank";
      link.rel = "noreferrer";

      const image = document.createElement("img");
      image.className = "message-image";
      image.src = imageUrl;
      image.alt = "Фото из переписки";

      link.append(image);
      container.append(link);
      return;
    }
    container.textContent = "Фото";
    return;
  }

  if (content.link?.url) {
    const link = document.createElement("a");
    link.href = content.link.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = content.link.title || content.link.url;
    container.append(link);
    return;
  }

  container.textContent = getMessageTypeLabel(message.type);
}

function pickImageUrl(image) {
  if (typeof image === "string") return image;
  if (!image || typeof image !== "object") return "";
  const sizes = image.sizes || image;
  return (
    sizes["640x480"] ||
    sizes["320x240"] ||
    sizes["140x105"] ||
    image.url ||
    Object.values(sizes).find((value) => typeof value === "string") ||
    ""
  );
}

function cleanSystemText(text) {
  return text.replace(/\[Системное сообщение\]\s*/g, "").trim();
}

function renderError(text) {
  messageList.innerHTML = "";
  const item = document.createElement("article");
  item.className = "message";

  const meta = document.createElement("div");
  meta.className = "message-meta error";
  meta.textContent = "Access error";

  const body = document.createElement("div");
  body.textContent = text;

  item.append(meta, body);
  messageList.append(item);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    showOutput({ status: response.status, error: data });
    throw new Error(extractErrorMessage(data, response.status));
  }
  return data;
}

function showOutput(data) {
  output.textContent = JSON.stringify(data, null, 2);
}

function hideDraft() {
  draftPanel.hidden = true;
  draftText.textContent = "";
}

function extractErrorMessage(data, status) {
  const detail = data && data.detail;
  if (detail && detail.error && detail.error.message) return detail.error.message;
  if (detail && typeof detail === "string") return detail;
  return `Request failed: ${status}`;
}
