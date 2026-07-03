const output = document.querySelector("#output");
const connectionLine = document.querySelector("#connectionLine");
const chatView = document.querySelector("#chatView");
const statsView = document.querySelector("#statsView");
const chatTabButton = document.querySelector("#chatTabButton");
const statsTabButton = document.querySelector("#statsTabButton");
const tokenButton = document.querySelector("#tokenButton");
const accountButton = document.querySelector("#accountButton");
const chatsButton = document.querySelector("#chatsButton");
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
const statsTableHead = document.querySelector(".stats-table thead");
const statsTableBody = document.querySelector("#statsTableBody");
const workspaceResizers = document.querySelectorAll(".workspace-resizer");

let activeChatId = null;
let activeChat = null;
let activeMessagesResponse = null;
let activeMessagesFingerprint = "";
let activeChatRequestId = 0;
let loadingChatId = null;
let avitoCredentialsReady = false;
let automationBusy = false;
let groupBotControlBusy = false;
let pollingTimer = null;
let currentChats = [];
let currentChatsFingerprint = "";
let currentStatsItems = [];
const chatBotControlByChatId = new Map();
const pendingChatBotControlByChatId = new Map();
const pendingMessagesByChatId = new Map();
const sendingMessageChatIds = new Set();
let chatFoldersInitialized = false;
let lastAutoOpenedActiveChatId = null;
let savedChatListScrollTop = 0;
const openChatFolderKeys = new Set();
const openChatBucketKeys = new Set();
const openStatsRowKeys = new Set();

const POLLING_INTERVAL_MS = 3000;
const MESSAGE_SCROLL_BOTTOM_THRESHOLD = 80;
const MANAGER_PAGE_STATE_KEY = "avito-bot-manager-page-state";
const MANAGER_LAYOUT_STATE_KEY = "avito-bot-manager-layout-state";
const QUALIFIED_BUYING_CHAT_IDS_KEY = "avito-bot-qualified-buying-chat-ids";
const STATS_SORT_KEY = "avito-bot-stats-sort";
const RESIZABLE_LAYOUT_DEFAULTS = {
  chatLeft: 330,
  chatRight: 380,
  statsLeft: 360,
};
const STATS_SORT_FIELDS = new Set(["date", "title", "uniqViews", "uniqContacts", "uniqFavorites"]);
const STATS_NUMERIC_SORT_FIELDS = new Set(["uniqViews", "uniqContacts", "uniqFavorites"]);
const qualifiedBuyingChatIds = loadQualifiedBuyingChatIds();
let statsSort = loadStatsSort();
const BUYING_CHAT_BUCKET = "Согласились купить";
const OTHER_CHAT_BUCKET = "Остальные чаты";
const SERVICE_PURCHASE_TRIGGER_PATTERNS = compileServicePurchaseTriggerPatterns();

document.querySelector("#refreshStatusButton").addEventListener("click", refreshStatus);
tokenButton.addEventListener("click", checkToken);
accountButton.addEventListener("click", loadAccount);
chatsButton.addEventListener("click", loadChats);
chatTabButton.addEventListener("click", () => showView("chats"));
statsTabButton.addEventListener("click", () => showView("stats"));
processUnreadButton.addEventListener("click", () => processUnread({ show: true }));
document.querySelector("#aiPingButton").addEventListener("click", pingAi);
document.querySelector("#webhooksButton").addEventListener("click", loadWebhookEvents);
document.querySelector("#sendForm").addEventListener("submit", sendMessage);
chatList.addEventListener("click", handleChatListClick);
chatList.addEventListener("scroll", () => {
  savedChatListScrollTop = chatList.scrollTop;
});
workspaceResizers.forEach(initializeWorkspaceResizer);
window.addEventListener("beforeunload", saveManagerPageState);
readButton.addEventListener("click", markRead);
draftButton.addEventListener("click", draftReply);
useDraftButton.addEventListener("click", useDraft);
autoProcessInput.addEventListener("change", syncServerAutoReply);
managerTakeoverButton.addEventListener("click", syncChatBotControl);
refreshStatsItemsButton.addEventListener("click", refreshStatsItems);
loadStatsButton.addEventListener("click", loadItemStats);
statsTableBody.addEventListener("click", handleStatsTableClick);
statsTableHead.addEventListener("click", handleStatsHeaderClick);

initialize();

async function initialize() {
  restoreManagerPageState();
  restoreWorkspaceLayout();
  initializeStatsDates();
  const status = await refreshStatus();
  await syncQualifiedBuyingChatIdsFromServer();
  if (status.avito_client_id_configured && status.avito_client_secret_configured) {
    try {
      await loadChats();
      await restoreActiveChat();
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
  avitoCredentialsReady = ready;
  const aiProvider = data.ai_provider || "deepseek";
  const aiStatus =
    aiProvider === "codex_app_server"
      ? `Codex App Server: ${data.codex_app_server_configured ? data.codex_app_server_model : "not configured"}`
      : `DeepSeek: ${data.deepseek_api_key_configured ? data.deepseek_model : "not configured"} · Codex fallback: ${data.codex_app_server_configured ? data.codex_app_server_model : "not configured"}`;
  connectionLine.textContent = ready
    ? `Avito: ${data.avito_client_id_preview || "configured"} · ${aiStatus}`
    : "Avito credentials are not configured";
  connectionLine.className = ready ? "" : "error";
  updateAvitoControls(ready);
  return data;
}

async function checkToken() {
  if (!ensureAvitoReady()) return;
  showOutput(await api("/api/avito/token-check", { method: "POST" }));
}

async function loadAccount() {
  if (!ensureAvitoReady()) return;
  showOutput(await api("/api/avito/account"));
}

async function pingAi() {
  showOutput(await api("/api/ai/ping", { method: "POST" }));
}

async function loadChats({ show = true } = {}) {
  if (!ensureAvitoReady({ show })) return;
  const params = new URLSearchParams({
    limit: "20",
    unread_only: unreadOnlyInput.checked ? "true" : "false",
  });
  const data = await api(`/api/avito/chats?${params.toString()}`);
  if (show) showOutput(data);
  mergeQualifiedBuyingChatIds(data.qualified_buying_chat_ids);
  const nextChats = data.chats || [];
  const nextFingerprint = getChatsFingerprint(nextChats);
  currentChats = nextChats;
  if (nextFingerprint !== currentChatsFingerprint) {
    currentChatsFingerprint = nextFingerprint;
    renderChats(currentChats);
    refreshStatsItems();
  }
  await syncVisibleChatBotControls(currentChats);
  restoreChatListScroll();
}

async function loadMessages(
  chatId,
  { resetDraft = true, show = true, chatSummary = null, scrollToLatest = false } = {},
) {
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
  saveManagerPageState();

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
    const renderableMessages = getRenderableMessages(chatId, messages);
    const nextMessagesFingerprint = getMessagesFingerprint(renderableMessages);
    if (!isBackgroundRefresh || nextMessagesFingerprint !== activeMessagesFingerprint) {
      const keepAtLatest = scrollToLatest || isPrimaryLoad || isMessageListNearBottom();
      activeMessagesFingerprint = nextMessagesFingerprint;
      renderMessages(renderableMessages, { scrollToLatest: keepAtLatest });
    } else if (scrollToLatest) {
      scrollMessageListToBottom();
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
  const chatId = activeChatId;
  const text = messageInput.value.trim();
  if (!text) return;
  if (sendingMessageChatIds.has(String(chatId))) return;
  sendingMessageChatIds.add(String(chatId));

  const pendingMessage = addPendingMessage(chatId, text);
  messageInput.value = "";
  sendButton.disabled = true;
  renderActiveMessagesWithPending({ scrollToLatest: true });
  setBotActivity("Sending message to Avito...", "active");

  try {
    const data = await api(`/api/avito/chats/${encodeURIComponent(chatId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    markPendingMessageStatus(chatId, pendingMessage.local_id, "sent");
    showOutput(data);
    setBotActivity("Message sent. Refreshing Avito history.", "active");
  } catch (error) {
    markPendingMessageStatus(chatId, pendingMessage.local_id, "failed", error.message);
    if (String(activeChatId) === String(chatId) && !messageInput.value.trim()) {
      messageInput.value = text;
    }
    showOutput({ error: error.message });
    setBotActivity(`Message was not sent: ${error.message}`, "error");
    return;
  } finally {
    sendingMessageChatIds.delete(String(chatId));
    if (String(activeChatId) === String(chatId)) {
      sendButton.disabled = false;
      messageInput.focus();
    }
  }

  if (String(activeChatId) === String(chatId)) {
    await loadMessages(chatId, { resetDraft: false, show: false, scrollToLatest: true });
  }
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

async function syncVisibleChatBotControls(chats) {
  const chatIds = chats.map((chat) => String(chat.id || "")).filter(Boolean);
  const missingChatIds = chatIds.filter((chatId) => !chatBotControlByChatId.has(chatId));
  if (!missingChatIds.length) return;
  await Promise.all(
    missingChatIds.map((chatId) =>
      loadChatBotControl(chatId, { show: false }).catch(() => null),
    ),
  );
  renderChats(currentChats);
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

async function setChatsBotControl(chatIds, managerTakeover) {
  const uniqueChatIds = [...new Set(chatIds.map((chatId) => String(chatId || "")).filter(Boolean))];
  if (!uniqueChatIds.length || groupBotControlBusy) return;
  groupBotControlBusy = true;
  uniqueChatIds.forEach((chatId) => {
    pendingChatBotControlByChatId.set(chatId, managerTakeover);
    updateChatBotControl(
      { chat_id: chatId, manager_takeover: managerTakeover, bot_enabled: !managerTakeover },
      { source: "local" },
    );
  });
  renderChats(currentChats);
  try {
    const results = await Promise.all(
      uniqueChatIds.map((chatId) =>
        api(`/api/avito/chats/${encodeURIComponent(chatId)}/bot-control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ manager_takeover: managerTakeover }),
          quiet: true,
        }).then((data) => ({ chatId, data })),
      ),
    );
    results.forEach(({ chatId, data }) => {
      pendingChatBotControlByChatId.delete(chatId);
      updateChatBotControl(data, { source: "server" });
    });
    showOutput({
      manager_takeover: managerTakeover,
      updated_count: results.length,
      chat_ids: uniqueChatIds,
    });
  } catch (error) {
    uniqueChatIds.forEach((chatId) => pendingChatBotControlByChatId.delete(chatId));
    showOutput({ error: error.message });
    await syncVisibleChatBotControls(currentChats);
  } finally {
    groupBotControlBusy = false;
    renderChats(currentChats);
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
  if (!ensureAvitoReady({ show })) return;
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
    processUnreadButton.disabled = !avitoCredentialsReady;
  }
}

async function refreshLiveView() {
  if (!avitoCredentialsReady) return;
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
  if (!ensureAvitoReady({ show: false })) {
    autoProcessInput.checked = false;
    return;
  }
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

function updateAvitoControls(ready) {
  [tokenButton, accountButton, chatsButton, processUnreadButton, autoProcessInput].forEach((control) => {
    control.disabled = !ready;
  });

  if (ready) return;

  autoProcessInput.checked = false;
  activeChatId = null;
  activeChat = null;
  activeMessagesResponse = null;
  activeMessagesFingerprint = "";
  currentChats = [];
  currentChatsFingerprint = "";
  lastAutoOpenedActiveChatId = null;
  conversationTitle.textContent = "Conversation";
  updateClientProfileLink(null);
  messageInput.disabled = true;
  sendButton.disabled = true;
  readButton.disabled = true;
  draftButton.disabled = true;
  managerTakeoverButton.disabled = true;
  hideDraft();
  chatList.textContent = "Добавьте AVITO_CLIENT_ID и AVITO_CLIENT_SECRET в .env или переменные окружения, затем перезапустите release.";
  messageList.textContent = "Чаты Avito недоступны без настроенных ключей.";
  setAutomationLine("Auto reply off: Avito credentials required");
  setBotActivity("Авито-бот не запущен: нужны AVITO_CLIENT_ID и AVITO_CLIENT_SECRET.", "error");
}

function ensureAvitoReady({ show = true } = {}) {
  if (avitoCredentialsReady) return true;
  const message =
    "AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required. Add them to .env or user environment variables, then restart release.";
  if (show) showOutput({ error: "Avito credentials are not configured", detail: message });
  setAutomationLine("Avito credentials required");
  setBotActivity("Авито-бот не может работать без AVITO_CLIENT_ID и AVITO_CLIENT_SECRET.", "error");
  return false;
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

function showView(view, { save = true } = {}) {
  const showStats = view === "stats";
  chatView.hidden = showStats;
  statsView.hidden = !showStats;
  chatTabButton.classList.toggle("active", !showStats);
  statsTabButton.classList.toggle("active", showStats);
  if (showStats) refreshStatsItems();
  if (save) saveManagerPageState();
}

async function restoreActiveChat() {
  if (!activeChatId) return;
  const chatId = activeChatId;
  const chat = findCurrentChat(chatId);
  if (!chat) {
    activeChatId = null;
    activeChat = null;
    saveManagerPageState();
    renderChats(currentChats);
    return;
  }
  await loadMessages(chatId, { resetDraft: false, show: false, chatSummary: chat, scrollToLatest: true });
}

function restoreManagerPageState() {
  const state = loadManagerPageState();
  openChatFolderKeys.clear();
  openChatBucketKeys.clear();
  state.openChatFolderKeys.forEach((key) => openChatFolderKeys.add(key));
  state.openChatBucketKeys.forEach((key) => openChatBucketKeys.add(key));
  activeChatId = state.activeChatId || null;
  savedChatListScrollTop = state.chatListScrollTop || 0;
  chatFoldersInitialized = Boolean(activeChatId || openChatFolderKeys.size || openChatBucketKeys.size);
  showView(state.view === "stats" ? "stats" : "chats", { save: false });
}

function loadManagerPageState() {
  try {
    const state = JSON.parse(window.localStorage.getItem(MANAGER_PAGE_STATE_KEY) || "{}");
    return {
      view: state.view === "stats" ? "stats" : "chats",
      activeChatId: state.activeChatId ? String(state.activeChatId) : "",
      chatListScrollTop: Number.isFinite(Number(state.chatListScrollTop)) ? Number(state.chatListScrollTop) : 0,
      openChatFolderKeys: Array.isArray(state.openChatFolderKeys) ? state.openChatFolderKeys.map(String) : [],
      openChatBucketKeys: Array.isArray(state.openChatBucketKeys) ? state.openChatBucketKeys.map(String) : [],
    };
  } catch (error) {
    return {
      view: "chats",
      activeChatId: "",
      chatListScrollTop: 0,
      openChatFolderKeys: [],
      openChatBucketKeys: [],
    };
  }
}

function saveManagerPageState() {
  try {
    window.localStorage.setItem(
      MANAGER_PAGE_STATE_KEY,
      JSON.stringify({
        view: statsView.hidden ? "chats" : "stats",
        activeChatId: activeChatId ? String(activeChatId) : "",
        chatListScrollTop: savedChatListScrollTop || chatList.scrollTop || 0,
        openChatFolderKeys: [...openChatFolderKeys],
        openChatBucketKeys: [...openChatBucketKeys],
      }),
    );
  } catch (error) {
    // Non-critical: the UI still works without persisted browser state.
  }
}

function initializeWorkspaceResizer(handle) {
  handle.addEventListener("pointerdown", (event) => startWorkspaceResize(handle, event));
  handle.addEventListener("keydown", (event) => resizeWorkspaceWithKeyboard(handle, event));
}

function restoreWorkspaceLayout() {
  applyWorkspaceLayout(loadWorkspaceLayoutState());
}

function loadWorkspaceLayoutState() {
  try {
    const state = JSON.parse(window.localStorage.getItem(MANAGER_LAYOUT_STATE_KEY) || "{}");
    return {
      chatLeft: normalizeLayoutNumber(state.chatLeft, RESIZABLE_LAYOUT_DEFAULTS.chatLeft),
      chatRight: normalizeLayoutNumber(state.chatRight, RESIZABLE_LAYOUT_DEFAULTS.chatRight),
      statsLeft: normalizeLayoutNumber(state.statsLeft, RESIZABLE_LAYOUT_DEFAULTS.statsLeft),
    };
  } catch (error) {
    return { ...RESIZABLE_LAYOUT_DEFAULTS };
  }
}

function saveWorkspaceLayoutState(state) {
  try {
    window.localStorage.setItem(MANAGER_LAYOUT_STATE_KEY, JSON.stringify(state));
  } catch (error) {
    // Non-critical: panel resizing remains available for this page session.
  }
}

function applyWorkspaceLayout(state) {
  document.documentElement.style.setProperty("--chat-left-width", `${Math.round(state.chatLeft)}px`);
  document.documentElement.style.setProperty("--chat-right-width", `${Math.round(state.chatRight)}px`);
  document.documentElement.style.setProperty("--stats-left-width", `${Math.round(state.statsLeft)}px`);
}

function normalizeLayoutNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function startWorkspaceResize(handle, event) {
  if (event.button !== undefined && event.button !== 0) return;
  const target = handle.dataset.resizeTarget;
  const workspace = getResizeWorkspace(target);
  if (!target || !workspace || window.matchMedia("(max-width: 1180px)").matches) return;

  event.preventDefault();
  handle.setPointerCapture?.(event.pointerId);
  handle.classList.add("active");
  document.body.classList.add("workspace-resizing");

  let nextState = loadWorkspaceLayoutState();
  const onPointerMove = (moveEvent) => {
    nextState = calculateWorkspaceLayout(target, moveEvent.clientX, nextState);
    applyWorkspaceLayout(nextState);
  };
  const onPointerUp = () => {
    handle.classList.remove("active");
    document.body.classList.remove("workspace-resizing");
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerUp);
    saveWorkspaceLayoutState(nextState);
  };

  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("pointercancel", onPointerUp);
}

function resizeWorkspaceWithKeyboard(handle, event) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  const target = handle.dataset.resizeTarget;
  const direction = event.key === "ArrowRight" ? 1 : -1;
  const state = loadWorkspaceLayoutState();
  const delta = 24;

  event.preventDefault();
  if (target === "chat-left") {
    state.chatLeft = clampLayoutWidth(state.chatLeft + direction * delta, 240, 620);
  } else if (target === "chat-right") {
    state.chatRight = clampLayoutWidth(state.chatRight - direction * delta, 280, 620);
  } else if (target === "stats-left") {
    state.statsLeft = clampLayoutWidth(state.statsLeft + direction * delta, 280, 620);
  }
  applyWorkspaceLayout(state);
  saveWorkspaceLayoutState(state);
}

function calculateWorkspaceLayout(target, clientX, previousState) {
  const state = { ...previousState };
  const workspace = getResizeWorkspace(target);
  if (!workspace) return state;
  const rect = workspace.getBoundingClientRect();

  if (target === "chat-left") {
    const maxLeft = rect.width - state.chatRight - 460;
    state.chatLeft = clampLayoutWidth(clientX - rect.left, 240, maxLeft);
  } else if (target === "chat-right") {
    const maxRight = rect.width - state.chatLeft - 460;
    state.chatRight = clampLayoutWidth(rect.right - clientX, 280, maxRight);
  } else if (target === "stats-left") {
    state.statsLeft = clampLayoutWidth(clientX - rect.left, 280, rect.width - 560);
  }
  return state;
}

function getResizeWorkspace(target) {
  if (target === "stats-left") return statsView;
  if (target === "chat-left" || target === "chat-right") return chatView;
  return null;
}

function clampLayoutWidth(value, min, max) {
  const safeMax = Math.max(min, max);
  return Math.round(Math.min(Math.max(value, min), safeMax));
}

function restoreChatListScroll() {
  window.requestAnimationFrame(() => {
    chatList.scrollTop = savedChatListScrollTop;
  });
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

  sortStatsRows(rows);
  updateStatsSortHeaders();

  rows.forEach((row) => {
    const rowKey = getStatsRowKey(row);
    const clients = getStatsClientsForRow(row);
    const isExpanded = openStatsRowKeys.has(rowKey);
    const tr = document.createElement("tr");
    tr.className = clients.length ? "stats-data-row expandable" : "stats-data-row";
    tr.dataset.rowKey = rowKey;
    tr.dataset.itemId = row.itemId || "";
    tr.dataset.title = row.title || "";
    tr.dataset.url = row.url || "";
    tr.dataset.date = row.date || "";
    tr.dataset.uniqViews = String(row.uniqViews || 0);
    tr.dataset.uniqContacts = String(row.uniqContacts || 0);
    tr.dataset.uniqFavorites = String(row.uniqFavorites || 0);
    tr.setAttribute("aria-expanded", String(isExpanded));
    tr.append(
      createTableCell(row.date || "-"),
      createStatsItemCell(row, { clients, isExpanded }),
      createTableCell(formatMetric(row.uniqViews)),
      createTableCell(formatMetric(row.uniqContacts)),
      createTableCell(formatMetric(row.uniqFavorites)),
    );
    statsTableBody.append(tr);
    if (isExpanded) {
      statsTableBody.append(createStatsClientsRow(row, clients));
    }
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

function createStatsItemCell(row, { clients = [], isExpanded = false } = {}) {
  const td = document.createElement("td");
  const wrap = document.createElement("div");
  wrap.className = "stats-item-cell";
  if (clients.length) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "stats-row-toggle";
    toggle.dataset.statsToggle = "true";
    toggle.setAttribute("aria-label", isExpanded ? "Скрыть клиентов" : "Показать клиентов");
    toggle.textContent = isExpanded ? "▾" : "▸";
    wrap.append(toggle);
  } else {
    const spacer = document.createElement("span");
    spacer.className = "stats-row-toggle-spacer";
    wrap.append(spacer);
  }
  if (row.url) {
    const link = document.createElement("a");
    link.href = row.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = row.title;
    wrap.append(link);
  } else {
    const title = document.createElement("span");
    title.textContent = row.title;
    wrap.append(title);
  }
  td.append(wrap);
  return td;
}

function createStatsClientsRow(row, clients) {
  const tr = document.createElement("tr");
  tr.className = "stats-clients-row";
  const td = document.createElement("td");
  td.colSpan = 5;

  const panel = document.createElement("div");
  panel.className = "stats-clients-panel";
  const title = document.createElement("div");
  title.className = "stats-clients-title";
  title.textContent = clients.length ? `Клиенты по объявлению: ${clients.length}` : "Клиентов по объявлению пока нет";
  panel.append(title);

  if (!clients.length) {
    const empty = document.createElement("div");
    empty.className = "stats-clients-empty";
    empty.textContent = "Загрузите чаты или проверьте, что у объявления есть переписки.";
    panel.append(empty);
  } else {
    const list = document.createElement("div");
    list.className = "stats-client-list";
    clients.forEach((chat) => list.append(createStatsClientLink(chat)));
    panel.append(list);
  }

  td.append(panel);
  tr.append(td);
  tr.dataset.parentRowKey = getStatsRowKey(row);
  return tr;
}

function createStatsClientLink(chat) {
  const card = document.createElement("div");
  card.className = "stats-client-card";

  const name = document.createElement("div");
  name.className = "stats-client-name";
  name.textContent = getChatDisplayTitle(chat);

  const meta = document.createElement("div");
  meta.className = "stats-client-meta";
  meta.textContent = getChatMeta(chat);

  const actions = document.createElement("div");
  actions.className = "stats-client-actions";
  const profileUrl = getBuyerProfileUrl(chat);
  if (profileUrl) {
    const profile = document.createElement("a");
    profile.href = profileUrl;
    profile.target = "_blank";
    profile.rel = "noreferrer";
    profile.textContent = "Профиль клиента";
    actions.append(profile);
  }
  if (chat.id) {
    const openChat = document.createElement("button");
    openChat.type = "button";
    openChat.className = "stats-client-chat-link";
    openChat.dataset.chatId = String(chat.id);
    openChat.textContent = "Открыть чат";
    actions.append(openChat);
  }

  card.append(name, meta, actions);
  return card;
}

function handleStatsTableClick(event) {
  const chatButton = event.target.closest(".stats-client-chat-link");
  if (chatButton && statsTableBody.contains(chatButton)) {
    const chatId = chatButton.dataset.chatId;
    const chat = findCurrentChat(chatId);
    showView("chats");
    if (chatId) loadMessages(chatId, { chatSummary: chat });
    return;
  }

  const toggle = event.target.closest("[data-stats-toggle]");
  if (!toggle || !statsTableBody.contains(toggle)) return;
  const row = toggle.closest("tr");
  const rowKey = row?.dataset.rowKey;
  if (!rowKey) return;
  if (openStatsRowKeys.has(rowKey)) {
    openStatsRowKeys.delete(rowKey);
  } else {
    openStatsRowKeys.add(rowKey);
  }
  renderItemStats({ items: normalizeStatsRowsFromTable() });
}

function handleStatsHeaderClick(event) {
  const header = event.target.closest("[data-stats-sort]");
  if (!header || !statsTableHead.contains(header)) return;
  const field = header.dataset.statsSort || "";
  if (!STATS_SORT_FIELDS.has(field)) return;
  statsSort = {
    field,
    direction: statsSort.field === field && statsSort.direction === "asc" ? "desc" : "asc",
  };
  saveStatsSort();
  renderItemStats({ items: normalizeStatsRowsFromTable() });
}

function normalizeStatsRowsFromTable() {
  return [...statsTableBody.querySelectorAll(".stats-data-row")].map((row) => ({
    itemId: row.dataset.itemId || "",
    title: row.dataset.title || "",
    url: row.dataset.url || "",
    date: row.dataset.date || "",
    uniqViews: Number(row.dataset.uniqViews || 0),
    uniqContacts: Number(row.dataset.uniqContacts || 0),
    uniqFavorites: Number(row.dataset.uniqFavorites || 0),
  }));
}

function sortStatsRows(rows) {
  const direction = statsSort.direction === "asc" ? 1 : -1;
  rows.sort((left, right) => {
    const missing = compareStatsMissingValues(left, right, statsSort.field);
    if (missing) return missing;
    const primary = compareStatsRows(left, right, statsSort.field);
    if (primary) return primary * direction;
    return compareStatsRows(left, right, "date") || compareStatsRows(left, right, "title") || compareStatsRows(left, right, "itemId");
  });
}

function compareStatsMissingValues(left, right, field) {
  if (STATS_NUMERIC_SORT_FIELDS.has(field)) return 0;
  const leftMissing = !String(left[field] || "");
  const rightMissing = !String(right[field] || "");
  if (leftMissing === rightMissing) return 0;
  return leftMissing ? 1 : -1;
}

function compareStatsRows(left, right, field) {
  if (STATS_NUMERIC_SORT_FIELDS.has(field)) {
    return compareStatsNumbers(left[field], right[field]);
  }
  if (field === "date") {
    return compareStatsDates(left.date, right.date);
  }
  return compareStatsText(left[field], right[field]);
}

function compareStatsNumbers(left, right) {
  const leftNumber = Number(left) || 0;
  const rightNumber = Number(right) || 0;
  return leftNumber - rightNumber;
}

function compareStatsDates(left, right) {
  const leftText = String(left || "");
  const rightText = String(right || "");
  if (!leftText && !rightText) return 0;
  if (!leftText) return 1;
  if (!rightText) return -1;
  return leftText.localeCompare(rightText);
}

function compareStatsText(left, right) {
  return String(left || "").localeCompare(String(right || ""), "ru", { numeric: true, sensitivity: "base" });
}

function updateStatsSortHeaders() {
  statsTableHead.querySelectorAll("[data-stats-sort]").forEach((header) => {
    const field = header.dataset.statsSort || "";
    const button = header.querySelector(".stats-sort-button");
    const active = field === statsSort.field;
    header.setAttribute("aria-sort", active ? (statsSort.direction === "asc" ? "ascending" : "descending") : "none");
    if (button) {
      button.dataset.direction = active ? statsSort.direction : "";
    }
  });
}

function loadStatsSort() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STATS_SORT_KEY) || "{}");
    if (STATS_SORT_FIELDS.has(saved.field) && ["asc", "desc"].includes(saved.direction)) {
      return { field: saved.field, direction: saved.direction };
    }
  } catch {
    // Ignore broken local sort preferences.
  }
  return { field: "date", direction: "desc" };
}

function saveStatsSort() {
  window.localStorage.setItem(STATS_SORT_KEY, JSON.stringify(statsSort));
}

function getStatsRowKey(row) {
  return `${row.date || ""}::${row.itemId || ""}`;
}

function getStatsClientsForRow(row) {
  return currentChats.filter((chat) => {
    if (!isStatsChatForRowDate(row, chat)) return false;
    const item = getChatItemContext(chat);
    const itemId = getItemId(item, chat);
    if (row.itemId && itemId && String(itemId) === String(row.itemId)) return true;
    const itemUrl = getItemUrl(item, chat);
    if (row.url && itemUrl && String(itemUrl) === String(row.url)) return true;
    return row.title && getItemTitle(item, chat) === row.title;
  });
}

function isStatsChatForRowDate(row, chat) {
  if (!row.date) return true;
  return getChatStatsDate(chat) === row.date;
}

function getChatStatsDate(chat) {
  const candidates = [
    chat.created,
    chat.created_at,
    chat.createdAt,
    chat.last_message?.created,
    chat.last_message?.created_at,
    chat.last_message?.createdAt,
    chat.updated,
    chat.updated_at,
    chat.updatedAt,
  ];
  return candidates.map(normalizeStatsDateValue).find(Boolean) || "";
}

function normalizeStatsDateValue(value) {
  if (!value) return "";
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "";
    const dateOnly = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
    if (dateOnly) return dateOnly[1];
    if (/^\d+$/.test(trimmed)) return normalizeStatsTimestamp(Number(trimmed));
    const parsed = new Date(trimmed);
    return Number.isNaN(parsed.getTime()) ? "" : formatLocalDateInput(parsed);
  }
  if (typeof value === "number") {
    return normalizeStatsTimestamp(value);
  }
  return "";
}

function normalizeStatsTimestamp(value) {
  if (!Number.isFinite(value) || value <= 0) return "";
  const milliseconds = value < 1000000000000 ? value * 1000 : value;
  return formatLocalDateInput(new Date(milliseconds));
}

function formatLocalDateInput(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
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
      updated: chat.updated || chat.updated_at || chat.updatedAt,
      activity: getChatActivityTimestamp(chat),
    })),
  );
}

function getMessagesFingerprint(messages) {
  return JSON.stringify(
    messages.map((message) => ({
      id: message.id || message.message_id,
      local_id: message.local_id,
      created: message.created || message.created_at,
      author_id: getMessageAuthorId(message),
      direction: message.direction,
      type: message.type,
      text: getMessageText(message),
      delivery_status: message.delivery_status,
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

    const folderHeader = document.createElement("div");
    folderHeader.className = "chat-folder-header";

    const folderButton = document.createElement("button");
    folderButton.type = "button";
    folderButton.className = "chat-folder-button";
    folderButton.setAttribute("aria-expanded", String(openChatFolderKeys.has(group.key)));
    folderButton.addEventListener("click", () => toggleChatFolder(group.key));

    const icon = document.createElement("span");
    icon.className = "chat-folder-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.classList.toggle("open", openChatFolderKeys.has(group.key));

    const title = document.createElement("span");
    title.className = "chat-folder-title";
    title.textContent = group.title;

    const count = document.createElement("span");
    count.className = "chat-folder-count";
    count.textContent = String(group.chats.length);

    folderButton.append(icon, title, count);
    folderHeader.append(folderButton, createBotControlScopeButton(group.chats, "chat-folder-mode-button"));
    folder.append(folderHeader);

    const nestedList = document.createElement("div");
    nestedList.className = "chat-folder-list";
    nestedList.hidden = !openChatFolderKeys.has(group.key);

    const buckets = splitChatsByBuyingIntent(group.chats);
    nestedList.append(createChatBucket(group.key, "buying", BUYING_CHAT_BUCKET, buckets.buying, { highlighted: true }));
    nestedList.append(createChatBucket(group.key, "other", OTHER_CHAT_BUCKET, buckets.other));

    folder.append(nestedList);
    chatList.append(folder);
  });
  restoreChatListScroll();
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

  const headerRow = document.createElement("div");
  headerRow.className = "chat-bucket-header-row";

  const header = document.createElement("button");
  header.type = "button";
  header.className = "chat-bucket-header";
  header.setAttribute("aria-expanded", String(isOpen));
  header.addEventListener("click", () => toggleChatBucket(key));

  const icon = document.createElement("span");
  icon.className = "chat-bucket-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.classList.toggle("open", isOpen);

  const name = document.createElement("span");
  name.className = "chat-bucket-title";
  name.textContent = title;

  const count = document.createElement("span");
  count.className = "chat-bucket-count";
  count.textContent = String(chats.length);

  header.append(icon, name, count);
  headerRow.append(header, createBotControlScopeButton(chats, "chat-bucket-mode-button"));
  bucket.append(headerRow);

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

  sortChatsByActivityDesc(chats).forEach((chat) => {
    body.append(createChatButton(chat));
  });
  bucket.append(body);
  return bucket;
}

function createBotControlScopeButton(chats, className) {
  const chatIds = chats.map((chat) => String(chat.id || "")).filter(Boolean);
  const state = getBotControlScopeState(chatIds);
  const button = document.createElement("button");
  button.type = "button";
  button.className = `chat-control-toggle scope-control ${className}`;
  button.disabled = !chatIds.length || groupBotControlBusy;
  button.setAttribute("aria-pressed", String(state.allManual));
  button.classList.toggle("active", state.allManual);
  button.classList.toggle("partial", state.partialManual);
  button.textContent = getBotControlScopeButtonText(state);
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    setChatsBotControl(chatIds, !state.allManual);
  });
  return button;
}

function getBotControlScopeState(chatIds) {
  const controls = chatIds.map((chatId) => getCachedChatBotControl(chatId));
  const manualCount = controls.filter((control) => control.manager_takeover === true).length;
  return {
    total: controls.length,
    manualCount,
    allManual: Boolean(controls.length && manualCount === controls.length),
    partialManual: manualCount > 0 && manualCount < controls.length,
  };
}

function getBotControlScopeButtonText(state) {
  if (!state.total) return "Ручной режим";
  if (state.allManual) return "Ручной режим включен";
  if (state.partialManual) return "Ручной режим частично";
  return "Включить ручной режим";
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

  const titleSide = document.createElement("span");
  titleSide.className = "chat-title-side";

  if (isBuyingChat(chat)) {
    const badge = document.createElement("span");
    badge.className = "chat-deal-badge";
    badge.textContent = "покупает";
    titleSide.append(badge);
  }

  const activityTime = formatChatActivityTime(chat);
  if (activityTime.label) {
    const time = document.createElement("span");
    time.className = "chat-activity-time";
    time.textContent = activityTime.label;
    if (activityTime.full) time.title = activityTime.full;
    titleSide.append(time);
  }

  titleRow.append(title, titleSide);

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

function sortChatsByActivityDesc(chats) {
  return [...chats].sort((left, right) => {
    const timeDiff = getChatActivityTimestamp(right) - getChatActivityTimestamp(left);
    if (timeDiff) return timeDiff;
    return getChatDisplayTitle(left).localeCompare(getChatDisplayTitle(right), "ru", {
      numeric: true,
      sensitivity: "base",
    });
  });
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

  const hasPreviewSignal = getLastMessageDirection(chat) === "in" && hasBuyingIntent(getChatPreviewText(chat));
  if (hasPreviewSignal && chat.id) {
    qualifiedBuyingChatIds.add(String(chat.id));
    saveQualifiedBuyingChatIds();
  }
  return hasPreviewSignal;
}

function markBuyingChatFromMessages(chatId, messages) {
  if (!chatId || qualifiedBuyingChatIds.has(String(chatId))) return false;
  const text = messages.filter(isClientMessage).map(getMessageText).filter(Boolean).join("\n");
  if (!text || !hasBuyingIntent(text)) return false;
  qualifiedBuyingChatIds.add(String(chatId));
  saveQualifiedBuyingChatIds();
  return true;
}

function isClientMessage(message) {
  return message?.direction === "in";
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
  return (
    message.content?.text ||
    message.content?.link?.text ||
    message.message?.text ||
    message.text ||
    getMessageAttachmentSearchText(message) ||
    ""
  );
}

function getMessageAttachmentSearchText(message) {
  const content = message.content || {};
  if (content.video || message.type === "video") return "видео video";
  if (content.image || message.type === "image") return "фото image";
  if (content.voice || message.type === "voice") return "голос voice";
  if (content.file || message.type === "file") return "файл file";
  return "";
}

function loadQualifiedBuyingChatIds() {
  try {
    return new Set(JSON.parse(window.localStorage.getItem(QUALIFIED_BUYING_CHAT_IDS_KEY) || "[]").map(String));
  } catch (error) {
    return new Set();
  }
}

function saveQualifiedBuyingChatIds() {
  writeQualifiedBuyingChatIdsCache();
  persistQualifiedBuyingChatIdsToServer();
}

function writeQualifiedBuyingChatIdsCache() {
  try {
    window.localStorage.setItem(QUALIFIED_BUYING_CHAT_IDS_KEY, JSON.stringify([...qualifiedBuyingChatIds]));
  } catch (error) {
    // Non-critical: classification still works for the current render.
  }
}

async function syncQualifiedBuyingChatIdsFromServer() {
  const localChatIds = new Set(qualifiedBuyingChatIds);
  try {
    const data = await api("/api/avito/qualified-buying-chats", { quiet: true });
    const serverChatIds = new Set((data.chat_ids || []).map(String));
    serverChatIds.forEach((chatId) => qualifiedBuyingChatIds.add(chatId));
    writeQualifiedBuyingChatIdsCache();
    const hasLocalOnlyIds = [...localChatIds].some((chatId) => !serverChatIds.has(chatId));
    if (hasLocalOnlyIds) {
      await persistQualifiedBuyingChatIdsToServer();
    }
  } catch (error) {
    // Non-critical: local classification still works while the backend catches up.
  }
}

function mergeQualifiedBuyingChatIds(chatIds) {
  if (!Array.isArray(chatIds)) return false;
  let changed = false;
  chatIds.map(String).filter(Boolean).forEach((chatId) => {
    if (qualifiedBuyingChatIds.has(chatId)) return;
    qualifiedBuyingChatIds.add(chatId);
    changed = true;
  });
  if (changed) writeQualifiedBuyingChatIdsCache();
  return changed;
}

async function persistQualifiedBuyingChatIdsToServer() {
  try {
    await api("/api/avito/qualified-buying-chats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_ids: [...qualifiedBuyingChatIds] }),
      quiet: true,
    });
  } catch (error) {
    // Non-critical: keep the browser cache and retry on the next page load/change.
  }
}

function syncOpenChatFolders(groups) {
  const knownKeys = new Set(groups.map((group) => group.key));
  let changed = false;
  [...openChatFolderKeys].forEach((key) => {
    if (!knownKeys.has(key)) {
      openChatFolderKeys.delete(key);
      changed = true;
    }
  });
  const knownBucketKeys = new Set();
  groups.forEach((group) => {
    knownBucketKeys.add(getChatBucketKey(group.key, "buying"));
    knownBucketKeys.add(getChatBucketKey(group.key, "other"));
  });
  [...openChatBucketKeys].forEach((key) => {
    if (!knownBucketKeys.has(key)) {
      openChatBucketKeys.delete(key);
      changed = true;
    }
  });

  const activeChatKey = activeChatId ? String(activeChatId) : "";
  const activeGroup = groups.find((group) => group.chats.some((chat) => String(chat.id) === activeChatKey));
  if (activeGroup && activeChatKey && activeChatKey !== lastAutoOpenedActiveChatId) {
    openChatFolderKeys.add(activeGroup.key);
    const activeBucket = isBuyingChat(activeGroup.chats.find((chat) => String(chat.id) === activeChatKey))
      ? "buying"
      : "other";
    openChatBucketKeys.add(getChatBucketKey(activeGroup.key, activeBucket));
    lastAutoOpenedActiveChatId = activeChatKey;
    changed = true;
  }

  if (!chatFoldersInitialized) {
    const firstGroup = activeGroup || groups[0];
    if (firstGroup) {
      openChatFolderKeys.add(firstGroup.key);
      const buckets = splitChatsByBuyingIntent(firstGroup.chats);
      openChatBucketKeys.add(getChatBucketKey(firstGroup.key, buckets.buying.length ? "buying" : "other"));
      changed = true;
    }
    chatFoldersInitialized = true;
  }
  if (changed) saveManagerPageState();
}

function toggleChatFolder(key) {
  if (openChatFolderKeys.has(key)) {
    openChatFolderKeys.delete(key);
  } else {
    openChatFolderKeys.add(key);
  }
  saveManagerPageState();
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
  saveManagerPageState();
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
  return [...groupsByKey.values()]
    .map((group) => ({
      ...group,
      chats: sortChatsByActivityDesc(group.chats),
      latestActivity: Math.max(...group.chats.map(getChatActivityTimestamp), 0),
    }))
    .sort((left, right) => {
      const timeDiff = right.latestActivity - left.latestActivity;
      if (timeDiff) return timeDiff;
      return left.title.localeCompare(right.title, "ru", { numeric: true, sensitivity: "base" });
    });
}

function getChatActivityTimestamp(chat) {
  const candidates = [
    chat.last_message?.created,
    chat.last_message?.created_at,
    chat.last_message?.createdAt,
    chat.last_message?.timestamp,
    chat.updated,
    chat.updated_at,
    chat.updatedAt,
    chat.created,
    chat.created_at,
    chat.createdAt,
  ];
  return candidates.map(normalizeTimestampMs).find((timestamp) => timestamp > 0) || 0;
}

function normalizeTimestampMs(value) {
  if (value === null || value === undefined || value === "") return 0;
  if (typeof value === "number") {
    if (!Number.isFinite(value) || value <= 0) return 0;
    return value < 1000000000000 ? value * 1000 : value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return 0;
    if (/^\d+(\.\d+)?$/.test(trimmed)) return normalizeTimestampMs(Number(trimmed));
    const parsed = Date.parse(trimmed);
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  return 0;
}

function formatChatActivityTime(chat) {
  const timestamp = getChatActivityTimestamp(chat);
  if (!timestamp) return { label: "", full: "" };
  const date = new Date(timestamp);
  const now = new Date();
  const time = new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
  const full = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);

  const dateLabel = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: "2-digit" }),
  }).format(date);
  return { label: `${dateLabel} ${time}`, full };
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
  const lastMessageText = chat.last_message ? getMessageText(chat.last_message) : "";
  return (
    lastMessageText ||
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

function appendMessageRoleLabel(container, message, label) {
  const clientProfileUrl = getMessageClientProfileUrl(message);
  if (!clientProfileUrl) {
    container.textContent = label;
    return;
  }

  const prefix = getMessageRolePrefix(label);
  if (prefix) {
    const prefixNode = document.createElement("span");
    prefixNode.textContent = `${prefix}: `;
    container.append(prefixNode);
  }

  const link = document.createElement("a");
  link.href = clientProfileUrl;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = getMessageClientLinkText(message, label);
  container.append(link);

  const reference = getMessageAuthorReference(message);
  if (reference) {
    const suffix = document.createElement("span");
    suffix.textContent = ` В· ${reference}`;
    container.append(suffix);
  }
}

function getMessageClientProfileUrl(message) {
  if (message.direction !== "in") return "";
  return (
    message.author?.profile_url ||
    message.author?.url ||
    message.from?.profile_url ||
    message.from?.url ||
    message.sender?.profile_url ||
    message.sender?.url ||
    message.user?.profile_url ||
    message.user?.url ||
    message.public_user_profile?.url ||
    getBuyerProfileUrl(activeChat || {})
  );
}

function getMessageClientLinkText(message, fallbackLabel) {
  return (
    getMessageAuthorName(message) ||
    getChatParticipantNameById(activeChat || {}, getMessageAuthorId(message)) ||
    getBuyerName(activeChat || {}) ||
    stripMessageRolePrefix(fallbackLabel) ||
    "РџСЂРѕС„РёР»СЊ РєР»РёРµРЅС‚Р°"
  );
}

function getMessageRolePrefix(label) {
  const delimiterIndex = label.indexOf(":");
  return delimiterIndex >= 0 ? label.slice(0, delimiterIndex) : "";
}

function stripMessageRolePrefix(label) {
  const delimiterIndex = label.indexOf(":");
  return (delimiterIndex >= 0 ? label.slice(delimiterIndex + 1) : label).split("В·")[0].trim();
}

function renderMessages(messages, { scrollToLatest = false } = {}) {
  messageList.innerHTML = "";
  if (!messages.length) {
    messageList.textContent = "No messages";
    if (scrollToLatest) scrollMessageListToBottom();
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
    if (message.delivery_status) {
      item.classList.add(`delivery-${message.delivery_status}`);
    }

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const roleLabel = document.createElement("span");
    roleLabel.className = "message-role";
    appendMessageRoleLabel(roleLabel, message, role.label);

    const time = document.createElement("span");
    time.className = "message-time";
    const statusText = getDeliveryStatusText(message);
    time.textContent = statusText
      ? `${formatMessageTime(createdAt, message.type)} - ${statusText}`
      : formatMessageTime(createdAt, message.type);

    const metaActions = document.createElement("span");
    metaActions.className = "message-meta-actions";
    metaActions.append(time);

    meta.append(roleLabel, metaActions);

    const content = document.createElement("div");
    content.className = "message-content";
    appendMessageContent(content, message);

    item.append(meta, content);
    messageList.append(item);

    if (index === orderedMessages.length - 1) {
      appendTimelineEdge("Последнее сообщение");
    }
  });
  if (scrollToLatest) scrollMessageListToBottom();
}

function isMessageListNearBottom() {
  return messageList.scrollHeight - messageList.clientHeight - messageList.scrollTop <= MESSAGE_SCROLL_BOTTOM_THRESHOLD;
}

function scrollMessageListToBottom() {
  window.requestAnimationFrame(() => {
    messageList.scrollTop = messageList.scrollHeight;
  });
}

function normalizeMessages(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.messages)) return data.messages;
  return [];
}

function renderActiveMessagesWithPending({ scrollToLatest = false } = {}) {
  if (!activeChatId) return;
  const serverMessages = normalizeMessages(activeMessagesResponse);
  renderMessages(getRenderableMessages(activeChatId, serverMessages), { scrollToLatest });
  activeMessagesFingerprint = getMessagesFingerprint(getRenderableMessages(activeChatId, serverMessages));
}

function getRenderableMessages(chatId, serverMessages) {
  reconcilePendingMessages(chatId, serverMessages);
  return [...serverMessages, ...getPendingMessages(chatId)];
}

function getPendingMessages(chatId) {
  return pendingMessagesByChatId.get(String(chatId)) || [];
}

function addPendingMessage(chatId, text) {
  const key = String(chatId);
  const pendingMessages = getPendingMessages(key);
  const pendingMessage = {
    local_id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    created: Date.now() / 1000,
    direction: "out",
    type: "text",
    content: { text },
    delivery_status: "sending",
  };
  pendingMessagesByChatId.set(key, [...pendingMessages, pendingMessage]);
  return pendingMessage;
}

function markPendingMessageStatus(chatId, localId, status, error = "") {
  const key = String(chatId);
  const pendingMessages = getPendingMessages(key).map((message) => {
    if (message.local_id !== localId) return message;
    return { ...message, delivery_status: status, delivery_error: error };
  });
  pendingMessagesByChatId.set(key, pendingMessages);
  if (String(activeChatId) === key) {
    renderActiveMessagesWithPending({ scrollToLatest: true });
  }
}

function reconcilePendingMessages(chatId, serverMessages) {
  const key = String(chatId);
  const pendingMessages = getPendingMessages(key);
  if (!pendingMessages.length) return;

  const remaining = pendingMessages.filter((pendingMessage) => {
    if (pendingMessage.delivery_status !== "sent") return true;
    return !serverMessages.some((serverMessage) => isServerCopyOfPendingMessage(serverMessage, pendingMessage));
  });
  if (remaining.length) {
    pendingMessagesByChatId.set(key, remaining);
  } else {
    pendingMessagesByChatId.delete(key);
  }
}

function isServerCopyOfPendingMessage(serverMessage, pendingMessage) {
  return serverMessage.direction === "out" && getMessageText(serverMessage).trim() === getMessageText(pendingMessage).trim();
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
    video: "видео",
    voice: "голос",
    system: "системное",
    link: "ссылка",
    item: "объявление",
    file: "файл",
    location: "гео",
  };
  return labels[type] || type || "сообщение";
}

function getDeliveryStatusText(message) {
  const status = message.delivery_status || "";
  if (status === "sending") return "sending";
  if (status === "sent") return "sent";
  if (status === "failed") return "failed";
  return "";
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

  if (content.video) {
    const videoUrl = pickVideoUrl(content.video);
    if (videoUrl) {
      const video = document.createElement("video");
      video.className = "message-video";
      video.src = videoUrl;
      video.controls = true;
      video.preload = "metadata";
      video.textContent = "Видео недоступно в этом браузере";

      const posterUrl = pickVideoPosterUrl(content.video);
      if (posterUrl) {
        video.poster = posterUrl;
      }

      container.append(video);
      return;
    }
    container.textContent = "Видео";
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

function pickVideoUrl(video) {
  if (typeof video === "string") return video;
  if (!video || typeof video !== "object") return "";
  const candidates = [
    video.url,
    video.video_url,
    video.file_url,
    video.download_url,
    video.href,
    video.src,
    video.player_url,
    video.mp4,
    video.files?.mp4,
    video.files?.url,
    video.sources?.mp4,
    ...(Array.isArray(video.sources) ? video.sources : []),
  ];
  return candidates.map(pickUrlValue).find(Boolean) || "";
}

function pickVideoPosterUrl(video) {
  if (!video || typeof video !== "object") return "";
  return (
    pickImageUrl(video.preview) ||
    pickImageUrl(video.preview_image) ||
    pickImageUrl(video.thumbnail) ||
    pickImageUrl(video.cover) ||
    pickImageUrl(video.image) ||
    ""
  );
}

function pickUrlValue(value) {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return "";
  return value.url || value.href || value.src || "";
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
