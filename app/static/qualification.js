// Qualified-buying bucket helpers for Avito chats.
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
