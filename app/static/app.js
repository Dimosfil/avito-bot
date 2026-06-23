const output = document.querySelector("#output");
const connectionLine = document.querySelector("#connectionLine");
const chatView = document.querySelector("#chatView");
const statsView = document.querySelector("#statsView");
const chatTabButton = document.querySelector("#chatTabButton");
const statsTabButton = document.querySelector("#statsTabButton");
const chatList = document.querySelector("#chatList");
const messageList = document.querySelector("#messageList");
const conversationTitle = document.querySelector("#conversationTitle");
const clientProfileLink = document.querySelector("#clientProfileLink");
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
const managerTakeoverButton = document.querySelector("#managerTakeoverButton");
const automationLine = document.querySelector("#automationLine");
const botActivity = document.querySelector("#botActivity");
const refreshStatsItemsButton = document.querySelector("#refreshStatsItemsButton");
const loadStatsButton = document.querySelector("#loadStatsButton");
const statsDateFrom = document.querySelector("#statsDateFrom");
const statsDateTo = document.querySelector("#statsDateTo");
const statsItemIdsInput = document.querySelector("#statsItemIdsInput");
const statsViewsInput = document.querySelector("#statsViewsInput");
const statsContactsInput = document.querySelector("#statsContactsInput");
const statsFavoritesInput = document.querySelector("#statsFavoritesInput");
const statsItemList = document.querySelector("#statsItemList");
const statsStatusLine = document.querySelector("#statsStatusLine");
const statsSummary = document.querySelector("#statsSummary");
const statsTableBody = document.querySelector("#statsTableBody");

let activeChatId = null;
let activeChat = null;
let activeMessagesResponse = null;
let activeMessagesFingerprint = "";
let activeChatRequestId = 0;
let loadingChatId = null;
let automationBusy = false;
let pollingTimer = null;
let currentChats = [];
let currentChatsFingerprint = "";
let currentStatsItems = [];
const chatBotControlByChatId = new Map();
const pendingChatBotControlByChatId = new Map();
let chatFoldersInitialized = false;
const openChatFolderKeys = new Set();
const openChatBucketKeys = new Set();

const POLLING_INTERVAL_MS = 3000;
const QUALIFIED_BUYING_CHAT_IDS_KEY = "avito-bot-qualified-buying-chat-ids";
const qualifiedBuyingChatIds = loadQualifiedBuyingChatIds();
const BUYING_CHAT_BUCKET = "Согласились купить";
const OTHER_CHAT_BUCKET = "Остальные чаты";
const SERVICE_PURCHASE_TRIGGER_PATTERNS = compileServicePurchaseTriggerPatterns();

document.querySelector("#refreshStatusButton").addEventListener("click", refreshStatus);
document.querySelector("#tokenButton").addEventListener("click", checkToken);
document.querySelector("#accountButton").addEventListener("click", loadAccount);
document.querySelector("#chatsButton").addEventListener("click", loadChats);
chatTabButton.addEventListener("click", () => showView("chats"));
statsTabButton.addEventListener("click", () => showView("stats"));
processUnreadButton.addEventListener("click", () => processUnread({ show: true }));
document.querySelector("#aiPingButton").addEventListener("click", pingAi);
document.querySelector("#webhooksButton").addEventListener("click", loadWebhookEvents);
document.querySelector("#sendForm").addEventListener("submit", sendMessage);
chatList.addEventListener("click", handleChatListClick);
readButton.addEventListener("click", markRead);
draftButton.addEventListener("click", draftReply);
useDraftButton.addEventListener("click", useDraft);
autoProcessInput.addEventListener("change", syncServerAutoReply);
managerTakeoverButton.addEventListener("click", syncChatBotControl);
refreshStatsItemsButton.addEventListener("click", refreshStatsItems);
loadStatsButton.addEventListener("click", loadItemStats);

initialize();

async function initialize() {
  initializeStatsDates();
  const status = await refreshStatus();
  if (status.avito_client_id_configured && status.avito_client_secret_configured) {
    try {
      await loadChats();
      refreshStatsItems();
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
  const nextChats = data.chats || [];
  const nextFingerprint = getChatsFingerprint(nextChats);
  currentChats = nextChats;
  if (nextFingerprint !== currentChatsFingerprint) {
    currentChatsFingerprint = nextFingerprint;
    renderChats(currentChats);
    refreshStatsItems();
  }
}

async function loadMessages(chatId, { resetDraft = true, show = true, chatSummary = null } = {}) {
  if (loadingChatId && String(loadingChatId) === String(chatId) && resetDraft === false && show === false) {
    return;
  }
  const requestId = ++activeChatRequestId;
  const isSameActiveChat = String(activeChatId) === String(chatId);
  const isBackgroundRefresh =
    isSameActiveChat && activeMessagesResponse && resetDraft === false && show === false;
  const isPrimaryLoad = !isBackgroundRefresh;

  activeChatId = chatId;
  activeChat = chatSummary || findCurrentChat(chatId) || (isSameActiveChat ? activeChat : null);

  if (isPrimaryLoad) {
    loadingChatId = String(chatId);
    activeMessagesResponse = null;
    activeMessagesFingerprint = "";
    if (resetDraft) hideDraft();
    conversationTitle.textContent = chatId;
    updateClientProfileLink(activeChat);
    messageInput.disabled = false;
    sendButton.disabled = false;
    readButton.disabled = false;
    applyChatBotControlState(getCachedChatBotControl(chatId), { setActivity: false });
    managerTakeoverButton.disabled = false;
    draftButton.disabled = true;
    renderChats(currentChats);
    renderMessagesLoading();
  }

  try {
    const chat = await api(`/api/avito/chats/${encodeURIComponent(chatId)}`);
    const data = await api(`/api/avito/chats/${encodeURIComponent(chatId)}/messages?limit=50`);
    if (requestId !== activeChatRequestId || String(activeChatId) !== String(chatId)) return;
    activeChat = mergeChatDetails(activeChat, chat);
    updateClientProfileLink(activeChat);
    activeMessagesResponse = data;
    if (show) showOutput(data);
    const messages = normalizeMessages(data);
    const buyingStatusChanged = markBuyingChatFromMessages(chatId, messages);
    const nextMessagesFingerprint = getMessagesFingerprint(messages);
    if (!isBackgroundRefresh || nextMessagesFingerprint !== activeMessagesFingerprint) {
      activeMessagesFingerprint = nextMessagesFingerprint;
      renderMessages(messages);
    }
    if (!isBackgroundRefresh || buyingStatusChanged) {
      renderChats(currentChats);
    }
    try {
      await loadChatBotControl(chatId, { show: false });
    } catch (error) {
      disableChatBotControl(error.message);
    }
    draftButton.disabled = false;
  } catch (error) {
    if (requestId !== activeChatRequestId || String(activeChatId) !== String(chatId)) return;
    renderError(error.message);
  } finally {
    if (requestId === activeChatRequestId && String(loadingChatId) === String(chatId)) {
      loadingChatId = null;
    }
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

async function loadChatBotControl(chatId, { show = false } = {}) {
  const data = await api(`/api/avito/chats/${encodeURIComponent(chatId)}/bot-control`, { quiet: true });
  if (show) showOutput(data);
  updateChatBotControl(data, { source: "server" });
  return data;
}

async function syncChatBotControl() {
  if (!activeChatId) return;
  const chatId = activeChatId;
  const previousControl = getCachedChatBotControl(chatId);
  const requestedManagerTakeover = !isManagerTakeoverPressed();
  pendingChatBotControlByChatId.set(String(chatId), requestedManagerTakeover);
  updateChatBotControl(
    { chat_id: chatId, manager_takeover: requestedManagerTakeover, bot_enabled: !requestedManagerTakeover },
    { source: "local" },
  );
  managerTakeoverButton.disabled = true;
  try {
    const data = await api(`/api/avito/chats/${encodeURIComponent(chatId)}/bot-control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manager_takeover: requestedManagerTakeover }),
      quiet: true,
    });
    showOutput(data);
    pendingChatBotControlByChatId.delete(String(chatId));
    updateChatBotControl(data, { source: "server" });
  } catch (error) {
    pendingChatBotControlByChatId.delete(String(chatId));
    updateChatBotControl(previousControl, { source: "local" });
    if (/404|not found/i.test(error.message)) {
      disableChatBotControl(error.message);
    } else {
      showOutput({ error: error.message });
    }
  } finally {
    managerTakeoverButton.disabled = !activeChatId;
  }
}

function updateChatBotControl(data, { source = "server" } = {}) {
  const dataChatId = data.chat_id ? String(data.chat_id) : "";
  const pendingValue = dataChatId ? pendingChatBotControlByChatId.get(dataChatId) : undefined;
  if (source === "server" && pendingValue !== undefined && data.manager_takeover !== pendingValue) {
    return;
  }
  if (dataChatId) {
    chatBotControlByChatId.set(dataChatId, data);
  }
  if (dataChatId && activeChatId && dataChatId !== String(activeChatId)) {
    return;
  }
  applyChatBotControlState(data);
}

function getCachedChatBotControl(chatId) {
  return chatBotControlByChatId.get(String(chatId)) || {
    chat_id: String(chatId),
    manager_takeover: false,
    bot_enabled: true,
  };
}

function applyChatBotControlState(data, { setActivity = true } = {}) {
  setManagerTakeoverPressed(data.manager_takeover === true);
  managerTakeoverButton.disabled = !activeChatId;
  if (!setActivity) return;
  if (data.manager_takeover) {
    setBotActivity("Ручной режим: бот выключен только в этом чате, отвечает оператор.", "active");
  } else {
    setBotActivity("Бот отвечает в этом чате. Оператор может включить ручной режим в любой момент.");
  }
}

function disableChatBotControl(reason) {
  setManagerTakeoverPressed(false);
  managerTakeoverButton.disabled = !activeChatId;
}

function isManagerTakeoverPressed() {
  return managerTakeoverButton.getAttribute("aria-pressed") === "true";
}

function setManagerTakeoverPressed(pressed) {
  managerTakeoverButton.setAttribute("aria-pressed", String(pressed));
  managerTakeoverButton.classList.toggle("active", pressed);
  managerTakeoverButton.textContent = pressed ? "Ручной режим включен" : "Включить ручной режим";
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

  if (activeResult.status === "manager_active") {
    setBotActivity("Ручной режим: бот пропустил этот чат, отвечает менеджер", "active");
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

function showView(view) {
  const showStats = view === "stats";
  chatView.hidden = showStats;
  statsView.hidden = !showStats;
  chatTabButton.classList.toggle("active", !showStats);
  statsTabButton.classList.toggle("active", showStats);
  if (showStats) refreshStatsItems();
}

function initializeStatsDates() {
  const today = new Date();
  const from = new Date(today);
  from.setDate(today.getDate() - 30);
  statsDateFrom.value = formatDateInput(from);
  statsDateTo.value = formatDateInput(today);
}

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

function refreshStatsItems() {
  const previousSelectedIds = new Set(getCheckedStatsItemIds().map(String));
  currentStatsItems = getStatsItemsFromChats(currentChats);
  renderStatsItemList(previousSelectedIds);
}

function getStatsItemsFromChats(chats) {
  const itemsById = new Map();
  chats.forEach((chat) => {
    const item = getChatItemContext(chat);
    const itemId = getItemId(item, chat);
    if (!itemId || itemsById.has(itemId)) return;
    itemsById.set(itemId, {
      id: itemId,
      title: getItemTitle(item, chat),
      url: getItemUrl(item, chat),
      chatCount: 0,
    });
  });
  chats.forEach((chat) => {
    const itemId = getItemId(getChatItemContext(chat), chat);
    const item = itemsById.get(itemId);
    if (item) item.chatCount += 1;
  });
  return [...itemsById.values()].sort((left, right) => left.title.localeCompare(right.title));
}

function renderStatsItemList(previousSelectedIds) {
  statsItemList.innerHTML = "";
  if (!currentStatsItems.length) {
    statsItemList.textContent = "Сначала загрузите чаты: из них берутся ID объявлений.";
    return;
  }

  const shouldSelectAll = !previousSelectedIds.size;
  currentStatsItems.forEach((item) => {
    const label = document.createElement("label");
    label.className = "stats-item-option";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "stats-item-checkbox";
    checkbox.value = item.id;
    checkbox.checked = shouldSelectAll || previousSelectedIds.has(String(item.id));

    const body = document.createElement("span");
    const title = document.createElement("span");
    title.className = "stats-item-title";
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "stats-item-meta";
    meta.textContent = `ID ${item.id} · чатов ${item.chatCount}`;
    body.append(title, meta);

    label.append(checkbox, body);
    statsItemList.append(label);
  });
}

async function loadItemStats() {
  const itemIds = getSelectedStatsItemIds();
  if (!itemIds.length) {
    setStatsStatus("Выберите объявления или введите ID вручную", true);
    return;
  }
  if (!statsDateFrom.value || !statsDateTo.value) {
    setStatsStatus("Укажите диапазон дат", true);
    return;
  }

  const fields = getSelectedStatsFields();
  loadStatsButton.disabled = true;
  setStatsStatus("Загружаю статистику...");
  try {
    const data = await api("/api/avito/item-stats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_ids: itemIds,
        date_from: statsDateFrom.value,
        date_to: statsDateTo.value,
        period_grouping: "day",
        fields,
      }),
    });
    showOutput(data);
    renderItemStats(data);
  } catch (error) {
    setStatsStatus(error.message, true);
  } finally {
    loadStatsButton.disabled = false;
  }
}

function getCheckedStatsItemIds() {
  return [...statsItemList.querySelectorAll(".stats-item-checkbox:checked")].map((input) => input.value);
}

function getSelectedStatsItemIds() {
  const manualIds = statsItemIdsInput.value
    .split(/[,\s]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  const ids = [...getCheckedStatsItemIds(), ...manualIds]
    .filter((value) => /^\d+$/.test(String(value)))
    .map((value) => Number(value));
  return [...new Set(ids)];
}

function getSelectedStatsFields() {
  const fields = [];
  if (statsViewsInput.checked) fields.push("uniqViews");
  if (statsContactsInput.checked) fields.push("uniqContacts");
  if (statsFavoritesInput.checked) fields.push("uniqFavorites");
  return fields.length ? fields : ["uniqViews"];
}

function renderItemStats(data) {
  const rows = normalizeStatsRows(data);
  statsTableBody.innerHTML = "";
  if (!rows.length) {
    statsSummary.innerHTML = "";
    setStatsStatus("Avito вернул пустую статистику");
    return;
  }

  rows.sort((left, right) => {
    const dateCompare = String(left.date).localeCompare(String(right.date));
    return dateCompare || String(left.itemId).localeCompare(String(right.itemId));
  });

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.append(
      createTableCell(row.date || "-"),
      createStatsItemCell(row),
      createTableCell(formatMetric(row.uniqViews)),
      createTableCell(formatMetric(row.uniqContacts)),
      createTableCell(formatMetric(row.uniqFavorites)),
    );
    statsTableBody.append(tr);
  });

  renderStatsSummary(rows);
  setStatsStatus(`Строк: ${rows.length}`);
}

function normalizeStatsRows(data) {
  const items = unwrapStatsItems(data);
  return items.flatMap((item) => {
    const itemId = String(item.itemId || item.item_id || item.id || "");
    const itemInfo = findStatsItem(itemId);
    const periods = item.stats || item.days || item.values || item.statistics || item.data || [];
    if (!Array.isArray(periods) || !periods.length) {
      return [
        {
          itemId,
          title: itemInfo?.title || item.title || `ID ${itemId}`,
          url: itemInfo?.url || item.url || "",
          date: item.date || "",
          uniqViews: pickMetric(item, "uniqViews"),
          uniqContacts: pickMetric(item, "uniqContacts"),
          uniqFavorites: pickMetric(item, "uniqFavorites"),
        },
      ];
    }
    return periods.map((period) => ({
      itemId,
      title: itemInfo?.title || item.title || `ID ${itemId}`,
      url: itemInfo?.url || item.url || "",
      date: period.date || period.day || period.period || "",
      uniqViews: pickMetric(period, "uniqViews"),
      uniqContacts: pickMetric(period, "uniqContacts"),
      uniqFavorites: pickMetric(period, "uniqFavorites"),
    }));
  });
}

function unwrapStatsItems(data) {
  const candidates = [
    data?.result?.items,
    data?.result?.stats,
    data?.items,
    data?.stats,
    data?.result,
    data,
  ];
  const found = candidates.find((value) => Array.isArray(value));
  return found || [];
}

function pickMetric(source, field) {
  const value = source?.[field] ?? source?.counters?.[field] ?? source?.metrics?.[field];
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function findStatsItem(itemId) {
  return currentStatsItems.find((item) => String(item.id) === String(itemId));
}

function createTableCell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function createStatsItemCell(row) {
  const td = document.createElement("td");
  if (row.url) {
    const link = document.createElement("a");
    link.href = row.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = row.title;
    td.append(link);
  } else {
    td.textContent = row.title;
  }
  return td;
}

function formatMetric(value) {
  return new Intl.NumberFormat("ru-RU").format(Number(value) || 0);
}

function renderStatsSummary(rows) {
  const totals = rows.reduce(
    (sum, row) => ({
      uniqViews: sum.uniqViews + row.uniqViews,
      uniqContacts: sum.uniqContacts + row.uniqContacts,
      uniqFavorites: sum.uniqFavorites + row.uniqFavorites,
    }),
    { uniqViews: 0, uniqContacts: 0, uniqFavorites: 0 },
  );
  statsSummary.innerHTML = "";
  statsSummary.append(
    createSummaryItem("Просмотры", totals.uniqViews),
    createSummaryItem("Контакты", totals.uniqContacts),
    createSummaryItem("Избранное", totals.uniqFavorites),
  );
}

function createSummaryItem(label, value) {
  const item = document.createElement("div");
  item.className = "stats-summary-item";
  const number = document.createElement("span");
  number.className = "stats-summary-value";
  number.textContent = formatMetric(value);
  const caption = document.createElement("span");
  caption.className = "stats-summary-label";
  caption.textContent = label;
  item.append(number, caption);
  return item;
}

function setStatsStatus(text, isError = false) {
  statsStatusLine.textContent = text;
  statsStatusLine.className = `panel-status ${isError ? "error" : ""}`.trim();
}

function getChatsFingerprint(chats) {
  return JSON.stringify(
    chats.map((chat) => ({
      id: chat.id,
      last_message: chat.last_message,
      status: chat.status,
      state: chat.state,
      handoff_required: chat.handoff_required,
      unread_count: chat.unread_count,
      updated: chat.updated || chat.updated_at,
    })),
  );
}

function getMessagesFingerprint(messages) {
  return JSON.stringify(
    messages.map((message) => ({
      id: message.id || message.message_id,
      created: message.created || message.created_at,
      author_id: getMessageAuthorId(message),
      direction: message.direction,
      type: message.type,
      text: getMessageText(message),
    })),
  );
}

function renderChats(chats) {
  chatList.innerHTML = "";
  if (!chats.length) {
    chatList.textContent = "No chats";
    return;
  }
  const groups = groupChatsByItem(chats);
  syncOpenChatFolders(groups);
  groups.forEach((group) => {
    const folder = document.createElement("section");
    folder.className = "chat-folder";

    const folderButton = document.createElement("button");
    folderButton.type = "button";
    folderButton.className = "chat-folder-button";
    folderButton.setAttribute("aria-expanded", String(openChatFolderKeys.has(group.key)));
    folderButton.addEventListener("click", () => toggleChatFolder(group.key));

    const icon = document.createElement("span");
    icon.className = "chat-folder-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = openChatFolderKeys.has(group.key) ? "▾" : "›";

    const title = document.createElement("span");
    title.className = "chat-folder-title";
    title.textContent = group.title;

    const count = document.createElement("span");
    count.className = "chat-folder-count";
    count.textContent = String(group.chats.length);

    folderButton.append(icon, title, count);
    folder.append(folderButton);

    const nestedList = document.createElement("div");
    nestedList.className = "chat-folder-list";
    nestedList.hidden = !openChatFolderKeys.has(group.key);

    const buckets = splitChatsByBuyingIntent(group.chats);
    nestedList.append(createChatBucket(group.key, "buying", BUYING_CHAT_BUCKET, buckets.buying, { highlighted: true }));
    nestedList.append(createChatBucket(group.key, "other", OTHER_CHAT_BUCKET, buckets.other));

    folder.append(nestedList);
    chatList.append(folder);
  });
}

function handleChatListClick(event) {
  const button = event.target.closest(".chat-item");
  if (!button || !chatList.contains(button)) return;
  const chatId = button.dataset.chatId;
  if (!chatId) return;
  const chat = findCurrentChat(chatId);
  loadMessages(chatId, { chatSummary: chat });
}

function createChatBucket(groupKey, bucketKey, title, chats, { highlighted = false } = {}) {
  const key = getChatBucketKey(groupKey, bucketKey);
  const isOpen = openChatBucketKeys.has(key);
  const bucket = document.createElement("section");
  bucket.className = `chat-bucket ${highlighted ? "buying" : ""}`.trim();

  const header = document.createElement("button");
  header.type = "button";
  header.className = "chat-bucket-header";
  header.setAttribute("aria-expanded", String(isOpen));
  header.addEventListener("click", () => toggleChatBucket(key));

  const icon = document.createElement("span");
  icon.className = "chat-bucket-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = isOpen ? "v" : ">";

  const name = document.createElement("span");
  name.className = "chat-bucket-title";
  name.textContent = title;

  const count = document.createElement("span");
  count.className = "chat-bucket-count";
  count.textContent = String(chats.length);

  header.append(icon, name, count);
  bucket.append(header);

  const body = document.createElement("div");
  body.className = "chat-bucket-body";
  body.hidden = !isOpen;

  if (!chats.length) {
    const empty = document.createElement("div");
    empty.className = "chat-bucket-empty";
    empty.textContent = "Пока нет";
    body.append(empty);
    bucket.append(body);
    return bucket;
  }

  chats.forEach((chat) => {
    body.append(createChatButton(chat));
  });
  bucket.append(body);
  return bucket;
}

function createChatButton(chat) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `chat-item ${String(chat.id) === String(activeChatId) ? "active" : ""}`;
  button.dataset.chatId = String(chat.id || "");

  const titleRow = document.createElement("div");
  titleRow.className = "chat-title-row";

  const title = document.createElement("span");
  title.className = "chat-title";
  title.textContent = getChatDisplayTitle(chat);

  titleRow.append(title);

  if (isBuyingChat(chat)) {
    const badge = document.createElement("span");
    badge.className = "chat-deal-badge";
    badge.textContent = "покупает";
    titleRow.append(badge);
  }

  const meta = document.createElement("div");
  meta.className = "chat-meta";
  meta.textContent = getChatMeta(chat);

  const subtitle = document.createElement("div");
  subtitle.className = "chat-subtitle";
  subtitle.textContent = getChatPreviewText(chat);

  button.append(titleRow, meta, subtitle);
  return button;
}

function splitChatsByBuyingIntent(chats) {
  const buying = [];
  const other = [];
  chats.forEach((chat) => {
    if (isBuyingChat(chat)) {
      buying.push(chat);
    } else {
      other.push(chat);
    }
  });
  return { buying, other };
}

function isBuyingChat(chat) {
  if (qualifiedBuyingChatIds.has(String(chat.id))) {
    return true;
  }

  const statusSignals = [
    chat.status,
    chat.state,
    chat.handoff_reason,
    chat.handoff_status,
    chat.deal_status,
    chat.order_status,
    ...(Array.isArray(chat.tags) ? chat.tags : []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (
    chat.handoff_required ||
    statusSignals.includes("handoff") ||
    statusSignals.includes("deal") ||
    statusSignals.includes("buy") ||
    statusSignals.includes("order") ||
    statusSignals.includes("покуп") ||
    statusSignals.includes("сделк")
  ) {
    return true;
  }

  const hasPreviewSignal = hasBuyingIntent(getChatPreviewText(chat));
  if (hasPreviewSignal && chat.id) {
    qualifiedBuyingChatIds.add(String(chat.id));
    saveQualifiedBuyingChatIds();
  }
  return hasPreviewSignal;
}

function markBuyingChatFromMessages(chatId, messages) {
  if (!chatId || qualifiedBuyingChatIds.has(String(chatId))) return false;
  const text = messages.map(getMessageText).filter(Boolean).join("\n");
  if (!text || !hasBuyingIntent(text)) return false;
  qualifiedBuyingChatIds.add(String(chatId));
  saveQualifiedBuyingChatIds();
  return true;
}

function hasBuyingIntent(text) {
  return SERVICE_PURCHASE_TRIGGER_PATTERNS.some((pattern) => pattern.test(text));
}

function compileServicePurchaseTriggerPatterns() {
  const triggerGroups = window.AVITO_BOT_RULES?.servicePurchaseTriggers || {};
  return Object.values(triggerGroups)
    .flatMap((group) => (Array.isArray(group) ? group : []))
    .map((source) => {
      try {
        return new RegExp(source, "i");
      } catch (error) {
        return null;
      }
    })
    .filter(Boolean);
}

function getMessageText(message) {
  return message.content?.text || message.content?.link?.text || message.message?.text || message.text || "";
}

function loadQualifiedBuyingChatIds() {
  try {
    return new Set(JSON.parse(window.localStorage.getItem(QUALIFIED_BUYING_CHAT_IDS_KEY) || "[]").map(String));
  } catch (error) {
    return new Set();
  }
}

function saveQualifiedBuyingChatIds() {
  try {
    window.localStorage.setItem(QUALIFIED_BUYING_CHAT_IDS_KEY, JSON.stringify([...qualifiedBuyingChatIds]));
  } catch (error) {
    // Non-critical: classification still works for the current render.
  }
}

function syncOpenChatFolders(groups) {
  const knownKeys = new Set(groups.map((group) => group.key));
  [...openChatFolderKeys].forEach((key) => {
    if (!knownKeys.has(key)) openChatFolderKeys.delete(key);
  });
  const knownBucketKeys = new Set();
  groups.forEach((group) => {
    knownBucketKeys.add(getChatBucketKey(group.key, "buying"));
    knownBucketKeys.add(getChatBucketKey(group.key, "other"));
  });
  [...openChatBucketKeys].forEach((key) => {
    if (!knownBucketKeys.has(key)) openChatBucketKeys.delete(key);
  });

  const activeGroup = groups.find((group) => group.chats.some((chat) => String(chat.id) === String(activeChatId)));
  if (activeGroup) {
    openChatFolderKeys.add(activeGroup.key);
    const activeBucket = isBuyingChat(activeGroup.chats.find((chat) => String(chat.id) === String(activeChatId)))
      ? "buying"
      : "other";
    openChatBucketKeys.add(getChatBucketKey(activeGroup.key, activeBucket));
  }

  if (!chatFoldersInitialized) {
    const firstGroup = activeGroup || groups[0];
    if (firstGroup) {
      openChatFolderKeys.add(firstGroup.key);
      const buckets = splitChatsByBuyingIntent(firstGroup.chats);
      openChatBucketKeys.add(getChatBucketKey(firstGroup.key, buckets.buying.length ? "buying" : "other"));
    }
    chatFoldersInitialized = true;
  }
}

function toggleChatFolder(key) {
  if (openChatFolderKeys.has(key)) {
    openChatFolderKeys.delete(key);
  } else {
    openChatFolderKeys.add(key);
  }
  renderChats(currentChats);
}

function getChatBucketKey(groupKey, bucketKey) {
  return `${groupKey}::${bucketKey}`;
}

function toggleChatBucket(key) {
  if (openChatBucketKeys.has(key)) {
    openChatBucketKeys.delete(key);
  } else {
    openChatBucketKeys.add(key);
  }
  renderChats(currentChats);
}

function findCurrentChat(chatId) {
  return currentChats.find((chat) => String(chat.id) === String(chatId)) || null;
}

function mergeChatDetails(summary, details) {
  if (!summary) return details || {};
  if (!details) return summary;
  return {
    ...details,
    title: details.title || summary.title,
    name: details.name || summary.name,
    display_name: details.display_name || summary.display_name,
    chat_title: details.chat_title || summary.chat_title,
    thread_title: details.thread_title || summary.thread_title,
    last_message: details.last_message || summary.last_message,
    users: details.users || summary.users,
    participants: details.participants || summary.participants,
    members: details.members || summary.members,
  };
}

function groupChatsByItem(chats) {
  const groupsByKey = new Map();
  chats.forEach((chat) => {
    const item = getChatItemContext(chat);
    const title = getItemTitle(item, chat);
    const key = getItemKey(item, title);
    if (!groupsByKey.has(key)) {
      groupsByKey.set(key, { key, title, chats: [] });
    }
    groupsByKey.get(key).chats.push(chat);
  });
  return [...groupsByKey.values()];
}

function getChatItemContext(chat) {
  return chat.context?.value || chat.item || {};
}

function getItemId(item, chat = {}) {
  const value =
    item.id ||
    item.item_id ||
    item.avito_id ||
    chat.item_id ||
    chat.itemId ||
    chat.context?.value?.id ||
    chat.context?.value?.item_id;
  return value ? String(value) : "";
}

function getItemKey(item, title) {
  return String(item.id || item.item_id || item.url || `${title}|${item.price_string || ""}` || "unknown-item");
}

function getItemTitle(item, chat) {
  return item.title || chat.context?.title || "Объявление без названия";
}

function getItemUrl(item, chat = {}) {
  return (
    item.url ||
    item.uri ||
    item.link ||
    item.external_url ||
    chat.item_url ||
    chat.context?.value?.url ||
    chat.context?.value?.uri ||
    ""
  );
}

function getChatDisplayTitle(chat) {
  return getBuyerName(chat) || "Клиент без имени";
}

function getChatMeta(chat) {
  const profile = getBuyerProfileLabel(chat);
  const chatId = chat.id ? `чат ${chat.id}` : "чат без ID";
  return profile ? `${profile} · ${chatId}` : chatId;
}

function updateClientProfileLink(chat) {
  const url = getBuyerProfileUrl(chat || {});
  if (!url) {
    clientProfileLink.hidden = true;
    clientProfileLink.removeAttribute("href");
    return;
  }
  clientProfileLink.hidden = false;
  clientProfileLink.href = url;
  clientProfileLink.textContent = "Профиль клиента на Avito";
}

function getChatPreviewText(chat) {
  return (
    chat.last_message?.content?.text ||
    chat.last_message?.message?.text ||
    chat.last_message?.text ||
    chat.context?.value?.price_string ||
    "Нет текста"
  );
}

function getBuyerName(chat) {
  const chatTitleName = getChatClientTitle(chat);
  if (chatTitleName) return chatTitleName;

  const directName = pickPersonName(chat.buyer || chat.client || chat.customer || chat.sender);
  if (directName) return directName;

  const users = getChatUsers(chat);
  const authorId = getLastMessageDirection(chat) === "in" ? getLastMessageAuthorId(chat) : "";
  if (authorId) {
    const author = users.find((user) => String(user.id || user.user_id || user.author_id) === String(authorId));
    const authorName = pickPersonName(author);
    if (authorName) return authorName;
  }

  const visibleUser = users.find((user) => !isSellerUser(chat, user));
  const visibleName = pickPersonName(visibleUser);
  if (visibleName) return visibleName;

  return chat.last_message?.author_name || pickPersonName(chat.last_message?.author || chat.last_message?.from);
}

function getChatClientTitle(chat) {
  const itemTitle = getItemTitle(getChatItemContext(chat), chat);
  const candidates = [chat.title, chat.name, chat.display_name, chat.chat_title, chat.thread_title];
  return candidates.map(cleanClientNameCandidate).find((name) => name && name !== itemTitle) || "";
}

function cleanClientNameCandidate(value) {
  if (typeof value !== "string") return "";
  const text = value.trim();
  if (!text || /^https?:\/\//i.test(text)) return "";
  return text;
}

function getBuyerProfileLabel(chat) {
  return getBuyerProfileUrl(chat);
}

function getBuyerProfileUrl(chat) {
  const directProfile =
    chat.buyer?.profile_url ||
    chat.buyer?.url ||
    chat.client?.profile_url ||
    chat.client?.url ||
    chat.user?.profile_url ||
    chat.user?.url;
  if (directProfile) return directProfile;

  const users = getChatUsers(chat);
  const authorId = getLastMessageDirection(chat) === "in" ? getLastMessageAuthorId(chat) : "";
  const user =
    users.find((candidate) => String(candidate.id || candidate.user_id || candidate.author_id) === String(authorId)) ||
    users.find((candidate) => !isSellerUser(chat, candidate));
  return user?.profile_url || user?.url || user?.public_user_profile?.url || "";
}

function getChatUsers(chat) {
  const sources = [chat.users, chat.participants, chat.members, chat.context?.users];
  return sources.flatMap((value) => (Array.isArray(value) ? value : []));
}

function getLastMessageAuthorId(chat) {
  return chat.last_message?.author_id || chat.last_message?.user_id || chat.last_message?.sender_id || "";
}

function getLastMessageDirection(chat) {
  return chat.last_message?.direction || "";
}

function pickPersonName(person) {
  if (typeof person === "string") return person.trim();
  if (!person || typeof person !== "object") return "";
  return (
    person.name ||
    person.display_name ||
    person.public_name ||
    person.profile?.name ||
    person.public_user_profile?.name ||
    person.title ||
    ""
  );
}

function isSellerUser(chat, user) {
  const sellerId = getChatSellerId(chat);
  const userId = user?.id || user?.user_id || user?.author_id || user?.public_user_profile?.user_id;
  if (sellerId && userId && String(sellerId) === String(userId)) return true;
  const role = String(user?.role || user?.type || "").toLowerCase();
  return role.includes("seller") || role.includes("manager") || role.includes("owner") || role.includes("business");
}

function renderMessagesLoading() {
  messageList.innerHTML = "";
  const loader = document.createElement("div");
  loader.className = "message-loading";

  const spinner = document.createElement("span");
  spinner.className = "message-loading-spinner";
  spinner.setAttribute("aria-hidden", "true");

  const text = document.createElement("span");
  text.textContent = "Загружаю переписку...";

  loader.append(spinner, text);
  messageList.append(loader);
}

function getChatSellerId(chat) {
  const item = getChatItemContext(chat);
  return item.user_id || chat.seller_id || chat.owner_id || chat.account_id || "";
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
    return { label: getOutgoingMessageLabel(message), className: "out" };
  }
  return { label: getIncomingMessageLabel(message), className: "in" };
}

function getIncomingMessageLabel(message) {
  const chat = activeChat || {};
  const name =
    getChatClientTitle(chat) ||
    getChatParticipantNameById(chat, getMessageAuthorId(message)) ||
    getMessageAuthorName(message) ||
    getBuyerName(chat);
  const reference = getMessageAuthorReference(message) || (activeChatId ? `чат ${activeChatId}` : "");
  if (name && reference) return `Клиент: ${name} · ${reference}`;
  if (name) return `Клиент: ${name}`;
  if (reference) return `Клиент · ${reference}`;
  return "Клиент";
}

function getOutgoingMessageLabel(message) {
  const name = getMessageAuthorName(message) || getChatParticipantNameById(activeChat || {}, getMessageAuthorId(message));
  const reference = getMessageAuthorReference(message);
  if (name && reference) return `Менеджер: ${name} · ${reference}`;
  if (name) return `Менеджер: ${name}`;
  if (reference) return `Менеджер · ${reference}`;
  return "Менеджер";
}

function getMessageAuthorName(message) {
  return (
    message.author_name ||
    message.user_name ||
    message.sender_name ||
    pickPersonName(message.author || message.from || message.sender || message.user)
  );
}

function getMessageAuthorReference(message) {
  const authorId = getMessageAuthorId(message);
  return authorId ? `id ${authorId}` : "";
}

function getMessageAuthorId(message) {
  return message.author_id || message.user_id || message.sender_id || message.from_id || "";
}

function getChatParticipantNameById(chat, authorId) {
  if (!authorId) return "";
  const participant = getChatUsers(chat).find((user) => {
    const userId = user?.id || user?.user_id || user?.author_id || user?.public_user_profile?.user_id;
    return String(userId) === String(authorId);
  });
  return pickPersonName(participant);
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
  const { quiet = false, ...fetchOptions } = options;
  const response = await fetch(url, fetchOptions);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    if (!quiet) showOutput({ status: response.status, error: data });
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
