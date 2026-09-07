function setHidden(el, hidden) {
  if (el) el.hidden = hidden;
}

function siteOrigin() {
  return window.location.origin.replace(/\/$/, "");
}

function badgeSlug(value) {
  let raw = String(value || "").trim();
  if (!raw) return "owner/repository";
  raw = raw.replace(/\.git$/, "");
  if (raw.startsWith("github.com/")) raw = `https://${raw}`;
  if ((raw.match(/\//g) || []).length === 1 && !raw.includes("://")) {
    raw = `https://github.com/${raw}`;
  }
  try {
    const parsed = new URL(raw);
    if (parsed.hostname === "github.com") {
      const parts = parsed.pathname.split("/").filter(Boolean);
      if (parts.length >= 2) return `${parts[0]}/${parts[1].replace(/\.git$/, "")}`;
    }
  } catch {
    const parts = raw.split("/").filter(Boolean);
    if (parts.length >= 2) return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
  }
  return "owner/repository";
}

function badgeMarkdown(slug) {
  const origin = siteOrigin();
  return `[![Lean Report Card](${origin}/badge/${slug}.svg)](${origin}/?repo=${slug})`;
}

function refreshBadgeSnippet() {
  const input = document.getElementById("badge-repository");
  const snippet = document.getElementById("badge-snippet");
  const note = document.getElementById("badge-localhost");
  if (!snippet) return;
  snippet.value = badgeMarkdown(badgeSlug(input && input.value));
  if (note) {
    const host = window.location.hostname;
    setHidden(note, host !== "localhost" && host !== "127.0.0.1");
  }
}

function closeModals() {
  setHidden(document.getElementById("contact-panel"), true);
  setHidden(document.getElementById("badge-panel"), true);
  setHidden(document.getElementById("modal-backdrop"), true);
  const contactOpen = document.getElementById("contact-open");
  const badgeOpen = document.getElementById("badge-open");
  if (contactOpen) contactOpen.setAttribute("aria-expanded", "false");
  if (badgeOpen) badgeOpen.setAttribute("aria-expanded", "false");
}

function openPanel(panelId, buttonId) {
  closeModals();
  setHidden(document.getElementById(panelId), false);
  setHidden(document.getElementById("modal-backdrop"), false);
  const button = document.getElementById(buttonId);
  if (button) button.setAttribute("aria-expanded", "true");
  if (panelId === "badge-panel") {
    refreshBadgeSnippet();
    const input = document.getElementById("badge-repository");
    if (input) input.focus();
  }
}

async function copyBadgeSnippet() {
  const snippet = document.getElementById("badge-snippet");
  const button = document.getElementById("badge-copy");
  if (!snippet) return;
  try {
    await navigator.clipboard.writeText(snippet.value);
  } catch {
    snippet.select();
    document.execCommand("copy");
  }
  if (button) {
    const previous = button.textContent;
    button.textContent = "Copied";
    window.setTimeout(() => {
      button.textContent = previous;
    }, 1600);
  }
}

async function onContactSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  if (window.posthog && typeof window.posthog.capture === "function") {
    window.posthog.capture("contact_submitted", {
      $process_person_profile: false,
      email: String(data.get("email") || "").trim(),
      message: String(data.get("message") || "").trim(),
    });
  }
  form.hidden = true;
  setHidden(document.getElementById("contact-queued"), false);
}

function bindSiteChrome() {
  const contactOpen = document.getElementById("contact-open");
  const contactClose = document.getElementById("contact-close");
  const badgeOpen = document.getElementById("badge-open");
  const badgeClose = document.getElementById("badge-close");
  const backdrop = document.getElementById("modal-backdrop");
  const contactForm = document.getElementById("contact-form");
  const badgeInput = document.getElementById("badge-repository");
  const badgeCopy = document.getElementById("badge-copy");
  if (contactOpen) contactOpen.addEventListener("click", () => openPanel("contact-panel", "contact-open"));
  if (contactClose) contactClose.addEventListener("click", closeModals);
  if (badgeOpen) badgeOpen.addEventListener("click", () => openPanel("badge-panel", "badge-open"));
  if (badgeClose) badgeClose.addEventListener("click", closeModals);
  if (backdrop) backdrop.addEventListener("click", closeModals);
  if (contactForm) contactForm.addEventListener("submit", onContactSubmit);
  if (badgeInput) badgeInput.addEventListener("input", refreshBadgeSnippet);
  if (badgeCopy) badgeCopy.addEventListener("click", copyBadgeSnippet);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeModals();
  });
}

bindSiteChrome();
