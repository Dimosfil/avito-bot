// Shared HTTP helpers for the static manager UI.
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

function extractErrorMessage(data, status) {
  const detail = data && data.detail;
  if (detail && detail.error && detail.error.message) return detail.error.message;
  if (detail && typeof detail === "string") return detail;
  return `Request failed: ${status}`;
}
