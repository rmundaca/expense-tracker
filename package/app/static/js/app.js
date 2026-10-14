"use strict";

// =============================================================================
// Helpers
// =============================================================================

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ESCAPES[c]);

// Line icons (24×24, stroked). Category/account icon names come from the database.
const BANKNOTE = '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><circle cx="12" cy="12" r="2.5"/><path d="M6 9.5v5M18 9.5v5"/>';
const DOLLAR = '<circle cx="12" cy="12" r="8.5"/><path d="M14.6 9.3c-.4-.9-1.4-1.5-2.6-1.5-1.5 0-2.6.8-2.6 2s1 1.7 2.6 2 2.6.8 2.6 2.1-1.2 2.1-2.6 2.1c-1.2 0-2.2-.6-2.6-1.5M12 6.2v1.6M12 16v1.8"/>';
const TAG = '<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3-8.7 8.7z"/><circle cx="8" cy="8" r="1.2"/>';
const ICONS = {
    // Categories and accounts
    "basket-shopping": '<path d="M3 4h2.2l2.3 11h10.3L20 7.5H6.3"/><circle cx="9" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/>',
    "utensils": '<path d="M7 3v18M4.5 3v5a2.5 2.5 0 0 0 5 0V3M17 21V3c-2 1-3.5 3.3-3.5 6.5S15 14 17 14"/>',
    "car": '<path d="M5 15.5V11l2-5h10l2 5v4.5"/><path d="M3.5 15.5h17V19h-3v-1.5h-11V19h-3z"/><path d="M7.5 12.5h.01M16.5 12.5h.01"/>',
    "house": '<path d="M4 11l8-6.5 8 6.5v9H4z"/><path d="M10 20v-5h4v5"/>',
    "heart-pulse": '<path d="M12 20s-7.5-4.6-7.5-10.2A4.2 4.2 0 0 1 12 7.3a4.2 4.2 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z"/>',
    "gamepad": '<path d="M7.5 6.5h9a4.5 4.5 0 0 1 4.4 5.4l-.8 4.3a2.3 2.3 0 0 1-3.9 1.1L14 15h-4l-2.2 2.3a2.3 2.3 0 0 1-3.9-1.1l-.8-4.3a4.5 4.5 0 0 1 4.4-5.4z"/><path d="M8 9.5v3M6.5 11h3M15.5 10.5h.01M17 12h.01"/>',
    "bag-shopping": '<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
    "graduation-cap": '<path d="M2.5 9.5 12 5l9.5 4.5L12 14z"/><path d="M6.5 11.5V16c1.5 1.4 3.5 2 5.5 2s4-.6 5.5-2v-4.5M21.5 9.5V15"/>',
    "tags": TAG,
    "tag": TAG,
    "money-check-dollar": BANKNOTE,
    "money-bill-wave": BANKNOTE,
    "briefcase": '<rect x="3.5" y="7.5" width="17" height="12" rx="2.5"/><path d="M9 7.5V5.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3.5 12.5h17"/>',
    "arrow-trend-up": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "chart-line": '<path d="M4 4v16h16"/><path d="M7.5 14.5l3.5-4 3 3 5-6"/>',
    "arrows-rotate": '<path d="M4 8h15l-3.5-3.5M20 16H5l3.5 3.5"/>',
    "circle-dollar-to-slot": DOLLAR,
    "dollar-sign": DOLLAR,
    "sliders": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    "gift": '<rect x="3.5" y="8.5" width="17" height="4" rx="1"/><path d="M5 12.5V20h14v-7.5M12 8.5V20M12 8.5S10.5 4 8 4.5s-1.5 4 4 4zM12 8.5s1.5-4.5 4-4 1.5 4-4 4z"/>',
    "plane": '<path d="M21 4.5 3 11l7 2.5L12.5 21z"/><path d="M10 13.5 21 4.5"/>',
    "paw": '<circle cx="6" cy="11" r="1.8"/><circle cx="9.5" cy="6.5" r="1.8"/><circle cx="14.5" cy="6.5" r="1.8"/><circle cx="18" cy="11" r="1.8"/><path d="M12 12c-2.5 0-5 3-5 5.5 0 1.5 1.2 2.5 2.5 2.5 1 0 1.5-.5 2.5-.5s1.5.5 2.5.5c1.3 0 2.5-1 2.5-2.5 0-2.5-2.5-5.5-5-5.5z"/>',
    "baby": '<circle cx="12" cy="12" r="8.5"/><path d="M9 11h.01M15 11h.01M9.5 15a3.5 3.5 0 0 0 5 0M12 3.5c-1 1.5-.5 3 1 3"/>',
    "dumbbell": '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11"/>',
    "shirt": '<path d="M8.5 3.5 3 6.5l2 4.5 2-1v10.5h10V10l2 1 2-4.5-5.5-3a3.5 3.5 0 0 1-7 0z"/>',
    "bolt": '<path d="M13 3 5 13.5h6.5l-1 7.5 8-10.5H12z"/>',
    "phone": '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "film": '<rect x="3" y="5" width="18" height="14" rx="3.5"/><path d="M10.5 9.5v5l4.2-2.5z"/>',
    "wallet": '<path d="M19 8V6.5A1.5 1.5 0 0 0 17.5 5H5.5A2.5 2.5 0 0 0 3 7.5v9A2.5 2.5 0 0 0 5.5 19h13a1.5 1.5 0 0 0 1.5-1.5V15"/><path d="M21 9.5h-5a2.5 2.5 0 0 0 0 5h5z"/>',
    "credit-card": '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M3 10h18M7 14.5h4"/>',
    "id-card": '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><circle cx="8.5" cy="11" r="2"/><path d="M5.5 16c.5-1.5 1.5-2.2 3-2.2s2.5.7 3 2.2M14.5 10h4M14.5 13.5h3"/>',
    "building-columns": '<path d="M3 10h18L12 4z"/><path d="M5.5 10v7.5M10 10v7.5M14 10v7.5M18.5 10v7.5M3 20h18"/>',
    "piggy-bank": '<path d="M19 10.5c0-3-3.1-5.5-7-5.5-1.3 0-2.6.3-3.6.8L6 4.5v3.2A5.3 5.3 0 0 0 4.3 10H3v4h1.8c.6 1.2 1.6 2.2 2.7 2.9V20h3v-2h3v2h3v-3.2c1.9-1.1 3-2.9 3-4.8z"/><path d="M15.5 10h.01"/>',
    // Interface
    "question": '<circle cx="12" cy="12" r="8.5"/><path d="M9.8 9.5a2.3 2.3 0 0 1 4.4.8c0 1.5-2.2 2-2.2 3.2M12 16.5h.01"/>',
    "chevron-right": '<path d="M9.5 6l6 6-6 6"/>',
    "chevron-down": '<path d="M7 10l5 5 5-5"/>',
    "xmark": '<path d="M7 7l10 10M17 7 7 17"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "warning": '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5M12 17h.01"/>',
    "tray": '<path d="M3.5 13.5h5l1.5 3h4l1.5-3h5"/><path d="M6 5h12l2.5 8.5V19a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1v-5.5z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 6.5 12 13l8.5-6.5"/>',
    "backup": '<path d="M12 3.5v11M7.5 10.5l4.5 4.5 4.5-4.5M4 16.5v3h16v-3"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "user": '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20c.9-3.6 3.8-5.5 7.5-5.5s6.6 1.9 7.5 5.5"/>',
    "users": '<circle cx="9" cy="8.5" r="3.3"/><path d="M2.8 19.5c.8-3.2 3.2-5 6.2-5s5.4 1.8 6.2 5"/><path d="M15.5 5.5a3.3 3.3 0 0 1 0 6.3M17.5 14.8c2 .6 3.3 2.3 3.8 4.7"/>',
    "repeat": '<path d="M16.5 3.5 20 7l-3.5 3.5"/><path d="M4 12v-1a4 4 0 0 1 4-4h12M7.5 20.5 4 17l3.5-3.5"/><path d="M20 12v1a4 4 0 0 1-4 4H4"/>',
    "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "arrow-down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "target": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12h.01"/>',
};
const CATEGORY_ICON_CHOICES = [
    "basket-shopping", "utensils", "car", "house", "heart-pulse", "gamepad", "bag-shopping", "graduation-cap",
    "gift", "plane", "paw", "baby", "dumbbell", "shirt", "bolt", "phone", "film", "tags",
    "money-check-dollar", "briefcase", "arrow-trend-up", "arrows-rotate", "circle-dollar-to-slot", "piggy-bank",
];
const icon = (name, cls = "i") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || TAG}</svg>`;
const chevron = () => icon("chevron-right", "i chevron");

// Codes are stored in the database (Spanish names of Chilean account products); labels come from the catalogs
const ACCOUNT_TYPES = [
    ["corriente", "building-columns"],
    ["vista", "id-card"],
    ["credito", "credit-card"],
    ["ahorro", "piggy-bank"],
    ["inversiones", "chart-line"],
    ["afp", "piggy-bank"],
    ["efectivo", "money-bill-wave"],
];
// Older databases use English type codes
const ACCOUNT_TYPE_ALIASES = { checking: "corriente", sight: "vista", credit: "credito", savings: "ahorro", investment: "inversiones", pension: "afp", cash: "efectivo" };
const accountType = (code) => ACCOUNT_TYPES.find(([key]) => key === (ACCOUNT_TYPE_ALIASES[code] || code));
const accountTypeLabel = (code) => accountType(code) ? t(`account_type.${accountType(code)[0]}`) : code || t("account.fallback");

const CURRENCIES = ["CLP", "USD", "EUR", "UF"];
const MONTHS = t("date.months");
const WEEKDAYS = t("date.weekdays");
const typeLabel = (type) => t(`type.${type}`);
const sourceLabel = (source) => ["rule", "memory", "ml"].includes(source) ? t(`source.${source}`) : "";
const ORIGINS = ["manual", "email", "recurring", "csv_import"];

/** The warning for a movement that looks recorded twice (`duplicate_of` from the movement lists). */
function duplicateNote(tx) {
    const d = tx.duplicate_of;
    if (!d) return "";
    const origin = ORIGINS.includes(d.source) ? t("tx.duplicate_origin", { origin: t(`origin.${d.source}`) }) : "";
    const details = origin + (d.status === "pending_review" ? t("tx.duplicate_pending") : "");
    return t("tx.duplicate_note", { merchant: d.merchant || t("tx.fallback_name"), date: dayMonth(d.date), amount: money(d.amount, d.currency), details });
}

function money(amount, currency = "CLP") {
    const n = Number(amount) || 0;
    const fmt = (digits) => Math.abs(n).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
    const sign = n < 0 ? "−" : "";
    switch ((currency || "CLP").toUpperCase()) {
        case "USD": return `${sign}US$ ${fmt(2)}`;
        case "EUR": return `${sign}€ ${fmt(2)}`;
        case "UF": return `${sign}UF ${fmt(2)}`;
        default: return `${sign}$${fmt(0)}`;
    }
}

const CURRENCY_SYMBOLS = { CLP: "$", USD: "US$", EUR: "€", UF: "UF" };

const COMPACT = new Intl.NumberFormat(LOCALE, { notation: "compact", maximumFractionDigits: 1 });
/** CLP for chart axes: $1,2 M (es) or $1.2M (en) */
const compactMoney = (n) => `${n < 0 ? "−" : ""}$${COMPACT.format(Math.abs(n))}`;

function signedMoney(tx) {
    const value = money(Math.abs(tx.amount), tx.currency);
    if (tx.type === "income") return `+${value}`;
    if (tx.type === "expense") return `−${value}`;
    if (tx.type === "adjustment") return tx.amount >= 0 ? `+${value}` : `−${value}`;
    return value;
}

/** Income reads green; expenses stay in the text color so the screen isn't a wall of red. */
const amountClass = (tx) => tx.type === "income" || (tx.type === "adjustment" && tx.amount > 0) ? "income" : "";

// Separators of the language's number format: es-CL writes 1.250,75 and en-US 1,250.75
const DECIMAL_SEPARATOR = (1.5).toLocaleString(LOCALE).charAt(1);
const GROUP_SEPARATOR = DECIMAL_SEPARATOR === "," ? "." : ",";

/**
 * Parses an amount typed in the language's notation: "12.500", "12500", "12,5" or "1.250,75" in Spanish,
 * "12,500", "12.5" or "1,250.75" in English. A group separator followed by groups of three digits
 * ("12.500" in Spanish) is a thousands separator; any other lone separator is the decimal point.
 * Magnitude only: callers that allow negatives (account balances) read the sign themselves.
 */
function parseAmount(text) {
    let s = String(text || "").replace(/[^\d.,]/g, "");
    const group = new RegExp(`\\${GROUP_SEPARATOR}`, "g");
    if (s.includes(DECIMAL_SEPARATOR)) s = s.replace(group, "").replace(DECIMAL_SEPARATOR, ".");
    else if (new RegExp(`^\\d{1,3}(\\${GROUP_SEPARATOR}\\d{3})+$`).test(s)) s = s.replace(group, "");
    else s = s.replace(GROUP_SEPARATOR, ".");  // any other lone separator is the decimal point ("12,5" / "12.5")
    const n = parseFloat(s);
    return isNaN(n) ? 0 : n;
}

function formatAmountInput(n, currency) {
    if (!n) return "";
    const decimals = currency === "CLP" ? 0 : 2;
    return Number(n).toLocaleString(LOCALE, { minimumFractionDigits: 0, maximumFractionDigits: decimals });
}

function isoDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const todayISO = () => isoDate(new Date());

function friendlyDate(iso) {
    const day = (iso || "").slice(0, 10);
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (day === todayISO()) return t("date.today");
    if (day === isoDate(yesterday)) return t("date.yesterday");
    const d = new Date(`${day}T12:00:00`);
    if (isNaN(d)) return day;
    const sameYear = d.getFullYear() === new Date().getFullYear();
    return t(sameYear ? "date.friendly" : "date.friendly_year",
        { weekday: WEEKDAYS[d.getDay()], day: d.getDate(), month: MONTHS[d.getMonth()].slice(0, 3), year: d.getFullYear() });
}

function monthLabel(ym) {
    const [y, m] = ym.split("-").map(Number);
    const label = MONTHS[m - 1];
    return t("date.month_year", { month: `${label.charAt(0).toUpperCase()}${label.slice(1)}`, year: y });
}

function shiftMonth(ym, step) {
    const [y, m] = ym.split("-").map(Number);
    return isoDate(new Date(y, m - 1 + step, 1)).slice(0, 7);
}

/** "5 oct" / "Oct 5", with the year when it isn't the current one */
function dayMonth(iso) {
    const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
    const sameYear = d.getFullYear() === new Date().getFullYear();
    return t(sameYear ? "date.day_month" : "date.day_month_year", { day: d.getDate(), month: MONTHS[d.getMonth()].slice(0, 3), year: d.getFullYear() });
}

function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function storage(key, value) {
    try {
        if (value === undefined) return localStorage.getItem(key);
        localStorage.setItem(key, value);
    } catch (e) { /* private mode or blocked storage */ }
    return null;
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
/** "#12994F" + alpha → "#12994F80" (canvas colors can't use color-mix) */
const withAlpha = (hex, alpha) => `${hex.slice(0, 7)}${Math.round(alpha * 255).toString(16).padStart(2, "0")}`;

// Charts of the current view; render() destroys them before replacing the view
const charts = [];
function makeChart(canvas, config) {
    Chart.defaults.font.family = cssVar("--font");
    Chart.defaults.color = cssVar("--text-2");
    if (reducedMotion()) config.options = { ...config.options, animation: false };
    charts.push(new Chart(canvas, config));
}
const destroyCharts = () => charts.splice(0).forEach(c => c.destroy());

let toastTimer;
function toast(message, isError = false) {
    let el = $("#toast");
    if (!el) {
        el = document.createElement("div");
        el.id = "toast";
        el.setAttribute("role", "status");
        el.setAttribute("aria-live", "polite");
        document.body.appendChild(el);
        el.getBoundingClientRect();  // commit the hidden state so the first toast animates in
    }
    el.className = `toast show${isError ? " error" : ""}`;
    el.innerHTML = `${icon(isError ? "warning" : "check")}<span>${esc(message)}</span>`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), isError ? 5000 : 2400);
}

// Segmented control: a capsule track with a thumb that slides to the selected option
function segmented(items, active, attr, id = "") {
    const index = Math.max(0, items.findIndex(([value]) => value === active));
    return `
        <div class="seg" ${id ? `id="${id}"` : ""} role="tablist" style="--n:${items.length};--i:${index}">
            <span class="seg-thumb"></span>
            ${items.map(([value, label]) => `<button type="button" class="seg-btn" role="tab" ${attr}="${esc(value)}" aria-selected="${value === active}">${esc(label)}</button>`).join("")}
        </div>`;
}

function selectSegment(btn) {
    const seg = btn?.closest(".seg");
    if (!seg) return;
    const buttons = $$(".seg-btn", seg);
    seg.style.setProperty("--i", String(buttons.indexOf(btn)));
    buttons.forEach(b => b.setAttribute("aria-selected", String(b === btn)));
}

/** Runs an async action and reports errors as a toast. Returns the result, or undefined on error. */
async function attempt(fn, successMessage) {
    try {
        const result = await fn();
        if (successMessage) toast(typeof successMessage === "function" ? successMessage(result) : successMessage);
        return result;
    } catch (err) {
        toast(err.message || t("error.unexpected"), true);
        return undefined;
    }
}

// =============================================================================
// Sheets & dialogs
// =============================================================================

/** Adds a backdrop to the page, animates it in, and returns a function that animates it out and removes it. */
function presentBackdrop(backdrop, exitMs) {
    const lastFocus = document.activeElement;
    document.body.appendChild(backdrop);
    document.body.style.overflow = "hidden";
    backdrop.getBoundingClientRect();  // commit the closed state so the transition runs
    backdrop.classList.add("open");
    let dismissed = false;
    return () => {
        if (dismissed) return;
        dismissed = true;
        backdrop.classList.remove("open", "dragging");
        const finish = () => {
            backdrop.remove();
            if (!$(".sheet-backdrop")) document.body.style.overflow = "";
            if (lastFocus && document.body.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
        };
        if (reducedMotion()) finish(); else setTimeout(finish, exitMs);
    };
}

/** Lets the user drag a sheet down by its grabber/header to dismiss it. */
function enableSwipeToClose(handle, sheet, backdrop, close) {
    let drag = null;
    handle.addEventListener("pointerdown", (e) => {
        if (e.target.closest("button") || e.button > 0) return;
        drag = { startY: e.clientY, dy: 0, lastY: e.clientY, lastT: performance.now(), velocity: 0 };
        backdrop.classList.add("dragging");
        handle.setPointerCapture(e.pointerId);
    });
    handle.addEventListener("pointermove", (e) => {
        if (!drag) return;
        const raw = e.clientY - drag.startY;
        drag.dy = raw < 0 ? raw / 5 : raw;  // resist dragging upwards
        const now = performance.now();
        drag.velocity = (e.clientY - drag.lastY) / Math.max(1, now - drag.lastT);
        drag.lastY = e.clientY;
        drag.lastT = now;
        sheet.style.transform = `translateY(${drag.dy}px)`;
        backdrop.style.setProperty("--scrim-o", String(Math.max(0, 1 - Math.max(0, drag.dy) / sheet.offsetHeight)));
    });
    const end = () => {
        if (!drag) return;
        const { dy, velocity } = drag;
        drag = null;
        backdrop.classList.remove("dragging");
        backdrop.style.removeProperty("--scrim-o");
        sheet.style.transform = "";
        if (dy > sheet.offsetHeight * 0.28 || velocity > 0.55) close();
    };
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
}

function openSheet(title, bodyHtml) {
    const backdrop = document.createElement("div");
    backdrop.className = "sheet-backdrop";
    backdrop.innerHTML = `
        <div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}">
            <div class="sheet-grab">
                <div class="grabber"></div>
                <div class="sheet-head">
                    <span><button class="circle-btn" data-close aria-label="${esc(t("common.close"))}">${icon("xmark")}</button></span>
                    <h2>${esc(title)}</h2>
                    <span></span>
                </div>
            </div>
            <div class="sheet-body">${bodyHtml}</div>
        </div>`;
    const sheet = $(".sheet", backdrop);
    const close = presentBackdrop(backdrop, 300);
    backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop || e.target.closest("[data-close]")) close();
    });
    enableSwipeToClose($(".sheet-grab", backdrop), sheet, backdrop, close);
    return { el: sheet, close };
}

function confirmDialog(title, message, okLabel = t("common.confirm"), danger = false) {
    return new Promise((resolve) => {
        const backdrop = document.createElement("div");
        backdrop.className = "sheet-backdrop center";
        backdrop.innerHTML = `
            <div class="dialog" role="alertdialog" aria-modal="true" aria-label="${esc(title)}">
                <h2>${esc(title)}</h2>
                <p class="muted">${esc(message)}</p>
                <div class="btn-row">
                    <button class="btn" data-answer="no">${esc(t("common.cancel"))}</button>
                    <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-answer="yes">${esc(okLabel)}</button>
                </div>
            </div>`;
        const close = presentBackdrop(backdrop, 200);
        backdrop.addEventListener("click", (e) => {
            const answer = e.target.closest("[data-answer]")?.dataset.answer;
            if (answer || e.target === backdrop) {
                close();
                resolve(answer === "yes");
            }
        });
        $("[data-answer='yes']", backdrop).focus({ preventScroll: true });
    });
}

// =============================================================================
// State & reference data
// =============================================================================

const state = {
    user: null,           // logged-in user: { id, username, display_name, is_admin }
    month: todayISO().slice(0, 7),
    accounts: [],         // includes archived ones, so history can still show their names (no balances)
    categories: [],       // same: archived ones label old movements but are never offered as a choice
    breakdownType: "expense",
    showAllAccounts: false,
    showAllCategories: false,
    planMetric: "balance",
    filters: { search: "", account_id: "", category: "" },
};
const PAGE_SIZE = 50;

const activeAccounts = () => state.accounts.filter(a => a.is_active);
/** An account's or category's name, marked when archived. */
const archivedName = (item) => item.is_active ? item.name : t("common.archived_suffix", { name: item.name });
const accountById = (id) => state.accounts.find(a => a.id === id);
const categoryById = (id) => state.categories.find(c => c.id === id);
/** Categories offered for `type`; `keepId` keeps an archived one visible while editing a movement that uses it. */
const categoryChoices = (type, keepId) => state.categories.filter(c => c.type === type && (c.is_active || c.id === keepId));

async function loadReferenceData() {
    const [accounts, categories] = await Promise.all([api.accounts(true, false), api.categories(true)]);
    state.accounts = accounts;
    state.categories = categories;
}

function setReviewBadge(count) {
    const badge = $("#reviewBadge");
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = !count;
}

async function refreshBadge() {
    const pending = await api.pendingCount().catch(() => null);
    if (pending) setReviewBadge(pending.count);
}

// =============================================================================
// Routing (hash based, so the Android back gesture works)
// =============================================================================

const VIEWS = {
    home: { title: t("view.home"), render: renderHome, month: true, fab: true },
    movements: { title: t("view.movements"), render: renderMovements, month: true, fab: true },
    review: { title: t("view.review"), render: renderReview, parent: "movements" },
    plan: { title: t("view.plan"), render: renderPlan, month: true },
    budgets: { title: t("view.budgets"), render: renderBudgets },
    settings: { title: t("view.settings"), render: renderSettings },
};

function currentRoute() {
    const [view, sub] = location.hash.replace(/^#\/?/, "").split("/");
    return { view: VIEWS[view] ? view : "home", sub: sub || null };
}

function go(view, sub) {
    const hash = sub ? `#/${view}/${sub}` : `#/${view}`;
    if (location.hash === hash) render();
    else location.hash = hash;
}

async function render() {
    const { view, sub } = currentRoute();
    const def = VIEWS[view];
    const title = sub ? settingsPages().find(([key]) => key === sub)?.[1].title || def.title : def.title;
    $("#viewTitle").textContent = title;
    $("#navTitle").textContent = title;
    document.title = `${title} · ${t("app.short_name")}`;
    $("#monthSwitch").hidden = !def.month;
    $("#monthLabel").textContent = monthLabel(state.month);
    $("#addBtn").hidden = !def.fab;
    // Settings pages go back to Settings; child views (Review) to their parent
    const back = sub ? view : def.parent;
    const backBtn = $("#backBtn");
    backBtn.hidden = !back;
    if (back) {
        backBtn.dataset.back = back;
        backBtn.setAttribute("aria-label", t("nav.back_to", { view: VIEWS[back].title }));
    }
    const tab = def.parent || view;
    $$(".tab").forEach(b => {
        b.classList.toggle("active", b.dataset.nav === tab);
        if (b.dataset.nav === tab) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    });
    // Replace the container so listeners from the previous view are dropped
    destroyCharts();
    const old = $("#view");
    const container = old.cloneNode(false);
    old.replaceWith(container);
    container.innerHTML = `<div class="empty">${esc(t("common.loading"))}</div>`;
    try {
        await def.render(container, sub);
    } catch (err) {
        container.innerHTML = `<div class="empty">${esc(t("common.load_failed", { error: err.message }))}</div>`;
    }
    updateNavbar();
    fitHeroValue();
}

// Shrinks the net worth until it fits on one line, whatever its length
function fitHeroValue() {
    const el = $(".hero-value");
    if (!el) return;
    el.style.fontSize = "";
    for (let i = 0; i < 3 && el.scrollWidth > el.clientWidth; i++) {
        const size = parseFloat(getComputedStyle(el).fontSize);
        el.style.fontSize = `${Math.floor(size * el.clientWidth / el.scrollWidth * 10) / 10}px`;
    }
}

// The navigation bar is transparent at the top, turns solid with a hairline once content
// scrolls under it, and shows the inline title once the large title has scrolled away.
function updateNavbar() {
    const navbar = $("#navbar");
    const barBottom = navbar.getBoundingClientRect().bottom;
    navbar.classList.toggle("solid", window.scrollY > 2);
    navbar.classList.toggle("collapsed", $("#viewTitle").getBoundingClientRect().bottom < barBottom);
}

// =============================================================================
// Movement rows
// =============================================================================

function txVisual(tx) {
    if (tx.type === "transfer") return { icon: "arrows-rotate", color: "#7A8499", label: typeLabel("transfer") };
    if (tx.type === "adjustment") return { icon: "sliders", color: "#7A8499", label: typeLabel("adjustment") };
    const cat = categoryById(tx.category_id);  // archived ones included, so history keeps its label
    return cat ? { icon: cat.icon, color: cat.color, label: cat.name } : { icon: "question", color: "#7A8499", label: t("common.uncategorized") };
}

const avatar = (iconName, color) => `<span class="avatar" ${color ? `style="--c:${esc(color)}"` : ""}>${icon(iconName)}</span>`;

function txAccountsLabel(tx) {
    const from = accountById(tx.account_id)?.name || t("account.fallback");
    if (tx.type !== "transfer") return from;
    const to = tx.destination_account_id ? accountById(tx.destination_account_id)?.name || t("account.fallback") : t("tx.outside_app");
    return `${from} → ${to}`;
}

/** A movement row. withDate: for lists that aren't grouped by day. */
function txRow(tx, { withDate = false } = {}) {
    const v = txVisual(tx);
    const foreign = tx.currency !== "CLP" ? `<span class="sub-amount">≈ ${esc(money(tx.base_amount))}</span>` : "";
    const pending = tx.status === "pending_review" ? `<span class="pill">${esc(t("tx.pending_pill"))}</span>` : "";
    const duplicate = tx.duplicate_of ? `<span class="pill pill-warn" title="${esc(duplicateNote(tx))}">${esc(t("tx.duplicate_pill"))}</span>` : "";
    return `
        <button class="row" data-tx="${tx.id}">
            ${avatar(v.icon, v.color)}
            <span class="row-main">
                <span class="row-title">${esc(tx.type === "adjustment" ? v.label : tx.merchant || v.label)}</span>
                <span class="row-sub">${tx.recurring_id ? icon("repeat") : ""}${withDate ? `${esc(dayMonth(tx.date))} · ` : ""}${esc(v.label)} · ${esc(txAccountsLabel(tx))}</span>
            </span>
            <span class="row-end">
                <span class="amount ${amountClass(tx)}">${esc(signedMoney(tx))}</span>
                ${foreign}${pending}${duplicate}
            </span>
        </button>`;
}

function dayGroupsHtml(items) {
    const groups = new Map();
    items.forEach(tx => {
        const day = tx.date.slice(0, 10);
        if (!groups.has(day)) groups.set(day, []);
        groups.get(day).push(tx);
    });
    return Array.from(groups.entries()).map(([day, txs]) => {
        const net = txs.reduce((sum, tx) => sum + (tx.status !== "confirmed" ? 0
            : tx.type === "income" ? tx.base_amount : tx.type === "expense" ? -tx.base_amount : 0), 0);
        const label = friendlyDate(day);
        return `
            <section class="day">
                <div class="day-head"><span>${esc(label.charAt(0).toUpperCase() + label.slice(1))}</span><span class="${net > 0 ? "income" : ""}">${net ? `${net > 0 ? "+" : ""}${esc(money(net))}` : ""}</span></div>
                <div class="card list">${txs.map(tx => txRow(tx)).join("")}</div>
            </section>`;
    }).join("");
}

// =============================================================================
// Home
// =============================================================================

// Home cards in their default order; each user can hide and reorder them (saved on the server).
// render(data) returns the card's HTML; mount(el, data) runs once it is in the page (charts).
const HOME_CARDS = {
    summary: { title: t("home.card_summary"), wide: true, render: summaryCard },
    categories: { title: t("home.card_categories"), render: categoriesCard },
    expensePie: { title: t("home.card_expense_pie"), render: (d) => pieCard(d, "expense"), mount: (el, d) => mountPie(el, d, "expense") },
    incomePie: { title: t("home.card_income_pie"), render: (d) => pieCard(d, "income"), mount: (el, d) => mountPie(el, d, "income") },
    accounts: { title: t("home.card_accounts"), render: accountsCard },
    budgets: { title: t("home.card_budgets"), render: budgetsCard },
};

/** The saved layout, plus the cards it doesn't know yet (added in a later version) at the end. */
function homeLayout(saved) {
    const known = saved.filter(c => HOME_CARDS[c.id]);
    const added = Object.keys(HOME_CARDS).filter(id => !known.some(c => c.id === id)).map(id => ({ id, visible: true }));
    return [...known, ...added];
}

function showMovements(filters) {
    state.filters = { search: "", account_id: "", category: "", ...filters };
    go("movements");
}

const reviewBanner = (count) => count ? `
    <button class="card banner" data-go="review">
        <span class="tile">${icon("tray")}</span>
        <span class="row-main"><span class="row-title">${esc(t("review.to_review", { count }))}</span><span class="row-sub">${esc(t("review.tap_to_approve"))}</span></span>
        ${chevron()}
    </button>` : "";

function summaryCard({ stats }) {
    const spent = stats.total_income > 0 ? Math.round(stats.total_expense / stats.total_income * 100) : null;
    const foreign = stats.accounts.filter(a => a.currency !== "CLP" && a.balance);
    const count = stats.accounts.length;
    return `
        <section class="card hero" aria-label="${esc(t("home.summary_aria"))}">
            <div class="hero-label">${esc(t("home.card_summary"))}</div>
            <div class="hero-value">${esc(money(stats.net_worth))}</div>
            <div class="hero-note">${esc(t("home.in_accounts", { count }))}${foreign.length
                ? esc(t("home.includes", { list: foreign.map(a => money(a.balance, a.currency)).join(", ") })) : ""}</div>
            <div class="hero-split">
                <div><div class="k">${esc(t("common.income"))}</div><div class="v income">+${esc(money(stats.total_income))}</div></div>
                <div><div class="k">${esc(t("common.expenses"))}</div><div class="v">−${esc(money(stats.total_expense))}</div></div>
            </div>
            ${spent !== null ? `
                <div class="meter ${spent > 100 ? "over" : ""}" role="img" aria-label="${esc(t("home.spent_aria", { pct: spent }))}"><span style="width:${Math.min(spent, 100)}%"></span></div>
                <div class="meter-note">${esc(t("home.spent_note", { pct: spent }))}</div>` : ""}
        </section>`;
}

const breakdownOf = (stats, type) => type === "expense" ? stats.expense_breakdown : stats.income_breakdown;
const noneThisMonth = (type) => `<div class="empty">${esc(t(type === "expense" ? "home.no_expenses" : "home.no_income"))}</div>`;
const percent = (value) => t("common.percent", { value: value.toLocaleString(LOCALE) });
const showAllLabel = (expanded, count) => expanded ? t("common.show_less") : t("common.show_all", { count });

function categoryRows(stats) {
    const breakdown = breakdownOf(stats, state.breakdownType);
    const visible = state.showAllCategories ? breakdown : breakdown.slice(0, 5);
    const rows = visible.map(item => `
        <button class="row" data-category-filter="${item.category_id ?? ""}">
            ${avatar(item.icon, item.color)}
            <span class="row-main">
                <span class="row-title">${esc(item.name)}</span>
                <span class="bar"><span style="width:${Math.max(item.percentage, 2)}%;background:${esc(item.color)}"></span></span>
            </span>
            <span class="row-end"><span class="amount">${esc(money(item.total))}</span><span class="sub-amount">${esc(percent(item.percentage))}</span></span>
        </button>`).join("");
    return (rows || noneThisMonth(state.breakdownType))
        + (breakdown.length > 5 ? `<button class="link-row" data-toggle="categories">${esc(showAllLabel(state.showAllCategories, breakdown.length))}</button>` : "");
}

function categoriesCard({ stats }) {
    return `
        <div class="sec-h"><h2>${esc(t("home.card_categories"))}</h2></div>
        <div class="card list">
            <div class="cats-head">${segmented([["expense", t("common.expenses")], ["income", t("common.income")]], state.breakdownType, "data-breakdown")}</div>
            <div class="list" id="catRows">${categoryRows(stats)}</div>
        </div>`;
}

/** Up to six slices: the biggest five and "Other" for the rest. */
function pieSlices(items) {
    if (items.length <= 6) return items;
    const rest = items.slice(5);
    const sum = (key) => rest.reduce((s, i) => s + i[key], 0);
    return [...items.slice(0, 5), { name: t("home.others"), color: "#7A8499", total: sum("total"), percentage: Math.round(sum("percentage") * 10) / 10, other: true }];
}

function pieCard({ stats }, type) {
    const slices = pieSlices(breakdownOf(stats, type));
    const total = type === "expense" ? stats.total_expense : stats.total_income;
    return `
        <div class="sec-h"><h2>${esc(t(type === "expense" ? "common.expenses" : "common.income"))}</h2><span class="note">${esc(money(total))}</span></div>
        <div class="card pie-card">${slices.length ? `
            <div class="pie-box"><canvas role="img" aria-label="${esc(t("home.pie_aria"))}"></canvas></div>
            <div class="legend">${slices.map(s => `
                <button class="legend-item" ${s.other ? "disabled" : `data-category-filter="${s.category_id ?? ""}"`}>
                    <span class="dot" style="--c:${esc(s.color)}"></span><span class="ellipsis">${esc(s.name)}</span><span class="muted">${esc(percent(s.percentage))}</span>
                </button>`).join("")}
            </div>` : noneThisMonth(type)}
        </div>`;
}

function mountPie(el, { stats }, type) {
    const canvas = $("canvas", el);
    if (!canvas) return;
    const slices = pieSlices(breakdownOf(stats, type));
    makeChart(canvas, {
        type: "doughnut",
        data: {
            labels: slices.map(s => s.name),
            datasets: [{ data: slices.map(s => s.total), backgroundColor: slices.map(s => s.color), borderColor: cssVar("--card"), borderWidth: 2 }],
        },
        options: {
            cutout: "62%",
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${money(c.raw)} · ${percent(slices[c.dataIndex].percentage)}` } } },
            onClick: (_, [hit]) => {
                const slice = hit && slices[hit.index];
                if (slice && !slice.other) showMovements({ category: String(slice.category_id ?? "") });
            },
        },
    });
}

function accountsCard({ stats }) {
    const accounts = stats.accounts;
    const visible = state.showAllAccounts ? accounts : accounts.slice(0, 5);
    return `
        <div class="sec-h"><h2>${esc(t("home.card_accounts"))}</h2><span class="note">${accounts.length || ""}</span></div>
        <div class="card list">${visible.map(acc => `
            <button class="row" data-account-filter="${acc.id}">
                ${avatar(acc.icon)}
                <span class="row-main"><span class="row-title">${esc(acc.name)}</span></span>
                <span class="row-end">
                    <span class="amount ${acc.balance < 0 ? "expense" : ""}">${esc(money(acc.balance, acc.currency))}</span>
                    ${acc.currency !== "CLP" ? `<span class="sub-amount">≈ ${esc(money(acc.balance_clp))}</span>` : ""}
                </span>
            </button>`).join("") || `<div class="empty">${esc(t("home.no_accounts"))}</div>`}
            ${accounts.length > 5 ? `<button class="link-row" data-toggle="accounts">${esc(showAllLabel(state.showAllAccounts, accounts.length))}</button>` : ""}
        </div>`;
}

function budgetsCard({ budgets }) {
    return `
        <div class="sec-h"><h2>${esc(t("home.card_budgets"))}</h2></div>
        <div class="card list plain-rows">${budgets.map(b => {
            const { pct, level } = budgetLevel(b.status);
            return `
            <button class="row" data-go="budgets">
                <span class="row-main">
                    <span class="row-title">${esc(b.name)}</span>
                    <span class="meter slim ${level}"><span style="width:${Math.min(pct, 100)}%"></span></span>
                </span>
                <span class="row-end"><span class="amount">${esc(money(b.status.spent))}</span><span class="sub-amount">${esc(t("common.of_amount", { amount: money(b.status.limit) }))}</span></span>
            </button>`;
        }).join("") || `<button class="link-row" data-go="budgets">${esc(t("home.create_budget"))}</button>`}
        </div>`;
}

async function renderHome(container) {
    const [stats, { budgets }] = await Promise.all([api.dashboard({ month: state.month }), api.budgets(), loadReferenceData()]);
    setReviewBadge(stats.pending_count);
    const data = { stats, budgets };
    const layout = homeLayout(stats.home_layout);
    const cards = layout.filter(c => c.visible);

    container.innerHTML = `
        <div class="home-grid">
            ${stats.pending_count ? `<div class="wide">${reviewBanner(stats.pending_count)}</div>` : ""}
            ${cards.map(({ id }) => `<section class="${HOME_CARDS[id].wide ? "wide" : ""}" data-card="${id}">${HOME_CARDS[id].render(data)}</section>`).join("")}
            <button class="btn btn-tinted wide" id="customizeHome">${esc(t("home.customize"))}</button>
        </div>`;
    cards.forEach(({ id }) => HOME_CARDS[id].mount?.($(`[data-card="${id}"]`, container), data));

    container.onclick = (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        if (btn.id === "customizeHome") return openHomeLayoutSheet(layout);
        if (btn.dataset.go) return go(btn.dataset.go);
        if (btn.dataset.breakdown) {
            // Update in place so the segmented thumb slides instead of the view reloading
            selectSegment(btn);
            state.breakdownType = btn.dataset.breakdown;
            state.showAllCategories = false;
            $("#catRows", container).innerHTML = categoryRows(stats);
            return;
        }
        if (btn.dataset.toggle === "categories") {
            state.showAllCategories = !state.showAllCategories;
            $("#catRows", container).innerHTML = categoryRows(stats);
            return;
        }
        if (btn.dataset.toggle === "accounts") { state.showAllAccounts = !state.showAllAccounts; return render(); }
        if ("categoryFilter" in btn.dataset) return showMovements({ category: btn.dataset.categoryFilter });
        if (btn.dataset.accountFilter) return showMovements({ account_id: btn.dataset.accountFilter });
    };
}

function openHomeLayoutSheet(layout) {
    const cards = layout.map(c => ({ ...c }));
    const sheet = openSheet(t("home.customize"), `
        <p class="section-note">${esc(t("home.customize_note"))}</p>
        <div class="card list plain-rows" id="layoutRows"></div>
        <div class="sheet-actions"><button class="btn btn-primary btn-block" id="layoutSave">${esc(t("common.save"))}</button></div>`);
    const el = sheet.el;
    const paint = () => {
        $("#layoutRows", el).innerHTML = cards.map((c, i) => `
            <div class="row layout-row">
                <label class="switch" aria-label="${esc(t("home.show_card", { name: HOME_CARDS[c.id].title }))}"><input type="checkbox" data-visible="${i}" ${c.visible ? "checked" : ""}><span></span></label>
                <span class="row-main"><span class="row-title">${esc(HOME_CARDS[c.id].title)}</span></span>
                <button class="circle-btn" data-move="${i}" data-step="-1" aria-label="${esc(t("home.move_up"))}" ${i === 0 ? "disabled" : ""}>${icon("arrow-up")}</button>
                <button class="circle-btn" data-move="${i}" data-step="1" aria-label="${esc(t("home.move_down"))}" ${i === cards.length - 1 ? "disabled" : ""}>${icon("arrow-down")}</button>
            </div>`).join("");
    };
    paint();
    $("#layoutRows", el).onchange = (e) => { cards[Number(e.target.dataset.visible)].visible = e.target.checked; };
    $("#layoutRows", el).onclick = (e) => {
        const btn = e.target.closest("[data-move]");
        if (!btn) return;
        const from = Number(btn.dataset.move);
        const to = from + Number(btn.dataset.step);
        [cards[from], cards[to]] = [cards[to], cards[from]];
        paint();
        // Keep keyboard focus on the card that moved (on the other arrow once it reaches an end)
        const arrows = $$(`[data-move="${to}"]:not(:disabled)`, el);
        (arrows.find(b => b.dataset.step === btn.dataset.step) || arrows[0])?.focus();
    };
    $("#layoutSave", el).onclick = async () => {
        if (await attempt(() => api.saveHomeLayout(cards), t("home.updated"))) {
            sheet.close();
            render();
        }
    };
}

// =============================================================================
// Movements
// =============================================================================

function movementQuery(offset) {
    const f = state.filters;
    const params = { limit: PAGE_SIZE, offset, account_id: f.account_id, search: f.search.trim() };
    // Searching looks across all months; browsing shows the selected month
    if (!params.search) params.month = state.month;
    if (f.category === "transfer") params.type = "transfer";
    else if (f.category) params.category_id = f.category;
    return params;
}

/** Appends the next page to `list`, which belongs to one render: a slower, older render never mixes into it. */
async function loadMoreMovements(list) {
    const page = await api.transactions(movementQuery(list.items.length));
    list.items.push(...page);
    list.done = page.length < PAGE_SIZE;
}

async function renderMovements(container) {
    const [pending] = await Promise.all([api.pendingCount(), loadReferenceData()]);
    setReviewBadge(pending.count);
    const f = state.filters;
    container.innerHTML = `
        <div class="mov-layout">
            <div class="mov-side">
                ${reviewBanner(pending.count)}
                <label class="search">${icon("search")}
                    <input id="searchInput" type="search" placeholder="${esc(t("movements.search_placeholder"))}" value="${esc(f.search)}" aria-label="${esc(t("common.search"))}" autocomplete="off">
                </label>
                <div class="filters">
                    <select id="accountFilter" class="chip-select ${f.account_id ? "on" : ""}" aria-label="${esc(t("field.account"))}">
                        <option value="">${esc(t("movements.all_accounts"))}</option>
                        ${state.accounts.map(a => `<option value="${a.id}" ${String(a.id) === f.account_id ? "selected" : ""}>${esc(archivedName(a))}</option>`).join("")}
                    </select>
                    <select id="categoryFilter" class="chip-select ${f.category ? "on" : ""}" aria-label="${esc(t("field.category"))}">
                        <option value="">${esc(t("movements.all_categories"))}</option>
                        <option value="transfer" ${f.category === "transfer" ? "selected" : ""}>${esc(t("movements.transfers"))}</option>
                        ${state.categories.filter(c => c.is_active || String(c.id) === f.category).map(c => `<option value="${c.id}" ${String(c.id) === f.category ? "selected" : ""}>${esc(archivedName(c))}</option>`).join("")}
                    </select>
                </div>
                ${f.search.trim() ? `<p class="section-note">${esc(t("movements.searching_all"))}</p>` : ""}
            </div>
            <div class="mov-list" id="movementList"></div>
        </div>`;

    const listEl = $("#movementList", container);
    const movements = { items: [], done: false };
    const paint = () => {
        const { items, done } = movements;
        listEl.innerHTML = items.length
            ? dayGroupsHtml(items) + (done ? "" : `<button class="btn btn-tinted btn-block" id="moreBtn">${esc(t("common.load_more"))}</button>`)
            : `<div class="card"><div class="empty">${esc(t(f.search || f.account_id || f.category ? "movements.empty_filtered" : "movements.empty_month"))}</div></div>`;
    };

    const searchInput = $("#searchInput", container);
    searchInput.addEventListener("input", debounce(() => {
        f.search = searchInput.value;
        render().then(() => {
            const input = $("#searchInput");
            if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
        });
    }, 450));
    $("[data-go]", container)?.addEventListener("click", () => go("review"));
    $("#accountFilter", container).onchange = (e) => { f.account_id = e.target.value; render(); };
    $("#categoryFilter", container).onchange = (e) => { f.category = e.target.value; render(); };
    listEl.addEventListener("click", async (e) => {
        if (e.target.id === "moreBtn") {
            e.target.disabled = true;
            await attempt(() => loadMoreMovements(movements));
            return paint();
        }
        const row = e.target.closest("[data-tx]");
        const tx = row && movements.items.find(t => t.id === Number(row.dataset.tx));
        if (tx) openTxSheet(tx, { onSaved: render });
    });

    await loadMoreMovements(movements);
    paint();
}

// =============================================================================
// Review (movements imported from email)
// =============================================================================

async function renderReview(container) {
    const [pending] = await Promise.all([api.transactions({ status: "pending_review", limit: 500 }), loadReferenceData()]);
    setReviewBadge(pending.length);
    if (!pending.length) {
        container.innerHTML = `<div class="card"><div class="empty">${icon("check")}<br>${esc(t("review.empty_title"))}<br>${esc(t("review.empty_body"))}</div></div>`;
        return;
    }
    const isReady = (tx) => tx.type === "transfer" ? tx.destination_account_id : tx.category_id;
    // "Approve all" leaves possible duplicates for the user to decide one by one
    const ready = pending.filter(tx => isReady(tx) && !tx.duplicate_of).length;

    container.innerHTML = `
        <div class="sec-h">
            <span class="note">${esc(t("review.to_review", { count: pending.length }))}</span>
            ${ready ? `<button class="btn btn-tinted" id="approveAll">${icon("check")}${esc(ready === pending.length ? t("review.approve_all") : t("review.approve_ready", { count: ready }))}</button>` : ""}
        </div>
        <div class="rev-grid">
        ${pending.map(tx => {
            const v = txVisual(tx);
            const how = sourceLabel(tx.ai_source);
            return `
            <article class="card review-card" data-id="${tx.id}">
                <div class="top">
                    ${avatar(v.icon, v.color)}
                    <div class="row-main">
                        <div class="row-title">${esc(tx.merchant || t("tx.fallback_name"))}</div>
                        <div class="row-sub">${esc(friendlyDate(tx.date))} · ${esc(txAccountsLabel(tx))}</div>
                    </div>
                    <div class="row-end">
                        <div class="rev-amt ${amountClass(tx)}">${esc(signedMoney(tx))}</div>
                        ${tx.currency !== "CLP" ? `<div class="sub-amount">≈ ${esc(money(tx.base_amount))}</div>` : ""}
                    </div>
                </div>
                ${isReady(tx)
                    ? `<div class="suggestion">${esc(typeLabel(tx.type))} <span class="chip" style="--c:${esc(v.color)}">${icon(v.icon)}${esc(v.label)}</span> ${esc(how)}</div>`
                    : `<div class="suggestion missing">${esc(t(tx.type === "transfer" ? "review.missing_destination" : "review.missing_category"))}</div>`}
                ${tx.duplicate_of ? `<div class="duplicate-note">${icon("warning")}<span>${esc(duplicateNote(tx))}</span></div>` : ""}
                ${tx.raw_text ? `<details><summary class="muted small">${esc(t("review.show_email"))}</summary><pre class="raw-email">${esc(tx.raw_text)}</pre></details>` : ""}
                <div class="actions">
                    <button class="btn btn-plain" data-action="discard">${esc(t("common.discard"))}</button>
                    <button class="btn" data-action="edit">${esc(t("common.edit"))}</button>
                    <button class="btn btn-primary" data-action="approve" ${isReady(tx) ? "" : "disabled"}>${esc(t("common.approve"))}</button>
                </div>
            </article>`;
        }).join("")}
        </div>`;

    container.onclick = async (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        if (btn.id === "approveAll") {
            btn.disabled = true;
            const res = await attempt(api.confirmAll, r => t("review.approved_count", { count: r.confirmed })
                + (r.skipped ? t("review.need_edit", { count: r.skipped }) : "")
                + (r.duplicates ? t("review.duplicates_left", { count: r.duplicates }) : ""));
            if (res) render(); else btn.disabled = false;
            return;
        }
        const card = btn.closest("[data-id]");
        const tx = card && pending.find(t => t.id === Number(card.dataset.id));
        if (!tx) return;
        if (btn.dataset.action === "approve") {
            btn.disabled = true;
            if (await attempt(() => api.confirmTransaction(tx.id), t("review.approved"))) render();
            else btn.disabled = false;
        } else if (btn.dataset.action === "discard") {
            if (await confirmDialog(t("review.discard_title"), t("review.discard_message"), t("common.discard"), true)
                && await attempt(() => api.deleteTransaction(tx.id), t("review.discarded"))) render();
        } else if (btn.dataset.action === "edit") {
            openTxSheet(tx, { review: true, onSaved: render });
        }
    };
}

// =============================================================================
// Add / edit movement sheet
// =============================================================================

function accountOptions(selectedId, excludeId) {
    const list = activeAccounts().filter(a => a.id !== excludeId);
    const selected = accountById(selectedId);
    if (selected && !selected.is_active) list.unshift(selected);  // keep an archived account visible when editing history
    return list.map(a => `<option value="${a.id}" ${a.id === selectedId ? "selected" : ""}>${esc(a.name)} (${esc(a.currency)})</option>`).join("");
}

const FREQUENCIES = ["day", "week", "month", "year"].map(unit => [unit, t(`freq.${unit}`)]);
const FREQUENCY_LABELS = Object.fromEntries(FREQUENCIES);

/**
 * Add/edit sheet for a movement. With `recurring`, `tx` is a recurring rule (null for a new one);
 * a new movement also becomes recurring when a frequency is chosen.
 */
function openTxSheet(tx, { review = false, recurring = false, onSaved } = {}) {
    if (tx && tx.type === "adjustment") return openAdjustmentSheet(tx, onSaved);

    const isNew = !tx;
    const lastAccount = Number(storage("lastAccountId"));
    const defaultAccount = activeAccounts().find(a => a.id === lastAccount) || activeAccounts()[0];
    if (!defaultAccount) {
        toast(t("tx.create_account_first"), true);
        return;
    }
    const f = {
        type: tx?.type || "expense",
        amount: tx?.amount || 0,
        currency: tx?.currency || defaultAccount.currency,
        rate: tx?.exchange_rate || null,
        rateEstimated: Boolean(tx?.rate_estimated),
        rateTyped: false,  // only a rate the user typed is sent; otherwise the server resolves (and later corrects) it
        date: tx ? (recurring ? tx.start_date : tx.date.slice(0, 10)) : todayISO(),
        account_id: tx?.account_id || defaultAccount.id,
        destination_account_id: tx?.destination_account_id || null,
        category_id: tx?.category_id || null,
        merchant: tx?.merchant || "",
        note: tx?.description || "",
        tags: (tx?.tags || []).map(t => t.name).join(", "),
        frequency: recurring ? tx?.frequency || "month" : "",
    };
    // Fields the user already chose, so suggestions never overwrite a manual choice
    const touched = { type: !isNew, category: !isNew, account: !isNew };
    // An existing movement stays single: its series (if any) is edited on its own
    const canRepeat = isNew || recurring;

    const title = recurring ? t(isNew ? "tx.title_new_recurring" : "tx.title_edit_recurring")
        : t(isNew ? "tx.title_new" : review ? "tx.title_review" : "tx.title_edit");
    const sheet = openSheet(title, `
        ${tx?.duplicate_of ? `<div class="duplicate-note">${icon("warning")}<span>${esc(duplicateNote(tx))}</span></div>` : ""}
        ${segmented(["expense", "income", "transfer"].map(type => [type, typeLabel(type)]), f.type, "data-type", "typeSeg")}
        <div class="amount-box">
            <label class="amount-line" for="fAmount">
                <span class="cur" id="curSymbol">${esc(CURRENCY_SYMBOLS[f.currency] || f.currency)}</span>
                <input id="fAmount" inputmode="decimal" placeholder="0" autocomplete="off" aria-label="${esc(t("field.amount"))}" value="${esc(formatAmountInput(f.amount, f.currency))}">
            </label>
            <span class="chip currency-chip"><span id="curLabel">${esc(f.currency)}</span>${icon("chevron-down")}
                <select id="fCurrency" aria-label="${esc(t("field.currency"))}">${CURRENCIES.map(c => `<option ${c === f.currency ? "selected" : ""}>${c}</option>`).join("")}</select>
            </span>
            <div class="rate-line" id="rateLine" hidden>
                <span>1 <span id="rateCur"></span> =</span>
                <input id="fRate" class="input" inputmode="decimal" aria-label="${esc(t("field.rate"))}">
                <span>CLP · <strong id="clpPreview"></strong></span>
            </div>
            <p class="muted small rate-note" id="rateNote" hidden>${esc(t("tx.rate_note"))}</p>
        </div>
        <div class="card form-group">
            <div class="frow"><label for="fMerchant">${esc(t("field.description"))}</label><input id="fMerchant" placeholder="${esc(t("tx.description_placeholder"))}" autocomplete="off" value="${esc(f.merchant)}"></div>
            <div class="frow"><label for="fAccount" id="accountLabel">${esc(t("field.account"))}</label><select id="fAccount"></select>${icon("chevron-down", "i chevron")}</div>
            <div class="frow" id="destField" hidden><label for="fDest">${esc(t("field.to"))}</label><select id="fDest"></select>${icon("chevron-down", "i chevron")}</div>
            <div class="frow"><label for="fDate" id="dateLabel">${esc(t("field.date"))}</label><input id="fDate" type="date" value="${esc(f.date)}"></div>
        </div>
        ${canRepeat ? `
        <div class="card form-group">
            <div class="frow"><label for="fRepeat">${esc(t("field.repeat"))}</label><select id="fRepeat">
                ${recurring ? "" : `<option value="">${esc(t("freq.never"))}</option>`}
                ${FREQUENCIES.map(([value, label]) => `<option value="${value}" ${value === f.frequency ? "selected" : ""}>${esc(label)}</option>`).join("")}
            </select>${icon("chevron-down", "i chevron")}</div>
            <div class="frow" data-repeating><label for="fUntil">${esc(t("field.until"))}</label><input id="fUntil" type="date" value="${esc(tx?.end_date || "")}"></div>
            <div class="frow" data-repeating><label for="fAuto" class="grow">${esc(t("tx.auto_confirm"))}</label>
                <span class="switch"><input type="checkbox" id="fAuto" ${tx?.auto_confirm ?? true ? "checked" : ""}><span></span></span></div>
        </div>
        <p class="section-note" data-repeating>${esc(t("tx.repeat_note"))}</p>` : ""}
        <div id="suggestHint" class="suggest-hint" hidden></div>
        <div id="catBlock">
            <div class="field-cap">${esc(t("field.category"))}</div>
            <div class="chip-wrap" id="catGrid"></div>
        </div>
        <details class="more" ${f.note || f.tags ? "open" : ""}>
            <summary>${esc(t("tx.note_and_tags"))}</summary>
            <div class="card form-group">
                <div class="frow block"><label for="fNote">${esc(t("field.note"))}</label><textarea id="fNote" rows="2">${esc(f.note)}</textarea></div>
                <div class="frow block" id="tagsField"><label for="fTags">${esc(t("field.tags"))}</label><input id="fTags" value="${esc(f.tags)}" autocomplete="off"></div>
            </div>
        </details>
        ${tx?.raw_text && !review ? `<details class="more"><summary>${esc(t("tx.original_email"))}</summary><pre class="raw-email">${esc(tx.raw_text)}</pre></details>` : ""}
        <div class="sheet-actions">
            <button class="btn btn-primary btn-big btn-block" id="saveBtn">${esc(t(review ? "tx.save_and_approve" : "common.save"))}</button>
            ${tx?.recurring_id ? `<button class="btn btn-tinted btn-block" id="seriesBtn">${icon("repeat")}${esc(t("tx.edit_series"))}</button>` : ""}
            ${isNew ? "" : `<button class="btn btn-plain btn-block" id="deleteBtn">${esc(t(review ? "common.discard" : recurring ? "tx.delete_recurring" : "tx.delete"))}</button>`}
        </div>`);
    const el = sheet.el;

    // The amount input grows with its content so the currency symbol stays next to the digits
    const fitAmount = () => {
        const input = $("#fAmount", el);
        const length = Math.max(input.value.length, 1);
        input.style.width = `${length + 0.6}ch`;
        input.style.fontSize = length > 10 ? "36px" : length > 7 ? "44px" : "";
    };
    fitAmount();

    const paintCategories = () => {
        // An archived category stays selectable for the movement that already uses it, so saving keeps it
        const cats = categoryChoices(f.type, tx?.category_id);
        if (f.category_id && !cats.some(c => c.id === f.category_id)) f.category_id = null;
        $("#catGrid", el).innerHTML = cats.map(c => `
            <button type="button" class="chip" data-cat="${c.id}" aria-pressed="${c.id === f.category_id}" style="--c:${esc(c.color)}">
                ${icon(c.icon)}${esc(c.name)}
            </button>`).join("") || `<div class="muted small">${esc(t("tx.no_categories"))}</div>`;
    };
    const paintType = () => {
        selectSegment($(`#typeSeg [data-type="${f.type}"]`, el));
        const isTransfer = f.type === "transfer";
        $("#catBlock", el).hidden = isTransfer;
        $("#destField", el).hidden = !isTransfer;
        $("#accountLabel", el).textContent = t(isTransfer ? "field.from" : "field.account");
        if (isTransfer) {
            $("#fDest", el).innerHTML = `<option value="">${esc(t("tx.choose_account"))}</option>` + accountOptions(f.destination_account_id, f.account_id);
            if (f.destination_account_id === f.account_id) f.destination_account_id = null;
        }
        paintCategories();
    };
    const paintAccounts = () => { $("#fAccount", el).innerHTML = accountOptions(f.account_id); };
    const paintClp = () => {
        $("#clpPreview", el).textContent = f.currency !== "CLP" && f.rate ? money(f.amount * f.rate) : "";
    };
    const paintRate = async (refetch) => {
        // Each repetition takes the rate of its own date, so a recurring movement has none to show
        const foreign = f.currency !== "CLP" && !f.frequency;
        $("#rateLine", el).hidden = !foreign;
        $("#rateNote", el).hidden = !foreign || f.rateTyped || !f.rateEstimated;
        if (!foreign) return;
        $("#rateCur", el).textContent = f.currency;
        if (refetch || !f.rate) {
            const res = await api.rate(f.currency, f.date).catch(() => null);
            if (res) {
                f.rate = res.rate;
                f.rateEstimated = res.estimated;
                f.rateTyped = false;
            }
        }
        $("#fRate", el).value = f.rate ? formatAmountInput(f.rate, "USD") : "";
        $("#rateNote", el).hidden = f.rateTyped || !f.rateEstimated;
        paintClp();
    };
    const paintRepeat = () => {
        $$("[data-repeating]", el).forEach(x => { x.hidden = !f.frequency; });
        $("#dateLabel", el).textContent = t(f.frequency ? "field.start_date" : "field.date");
        $("#tagsField", el).hidden = Boolean(f.frequency);
        paintRate(false);
    };

    paintAccounts();
    paintType();
    paintRepeat();

    $("#typeSeg", el).onclick = (e) => {
        const b = e.target.closest("[data-type]");
        if (!b) return;
        f.type = b.dataset.type;
        touched.type = true;
        paintType();
    };
    $("#catGrid", el).onclick = (e) => {
        const b = e.target.closest("[data-cat]");
        if (!b) return;
        f.category_id = Number(b.dataset.cat);
        touched.category = true;
        paintCategories();
    };
    const paintCurrency = () => {
        $("#curSymbol", el).textContent = CURRENCY_SYMBOLS[f.currency] || f.currency;
        $("#curLabel", el).textContent = f.currency;
    };
    $("#fAmount", el).oninput = (e) => { f.amount = parseAmount(e.target.value); paintClp(); fitAmount(); };
    $("#fAmount", el).onblur = (e) => { e.target.value = formatAmountInput(f.amount, f.currency); fitAmount(); };
    $("#fCurrency", el).onchange = (e) => { f.currency = e.target.value; f.rate = null; paintCurrency(); paintRate(true); };
    $("#fRate", el).oninput = (e) => {
        f.rate = parseAmount(e.target.value);
        f.rateTyped = true;
        $("#rateNote", el).hidden = true;
        paintClp();
    };
    $("#fDate", el).onchange = (e) => { f.date = e.target.value; if (f.currency !== "CLP") paintRate(true); };
    if (canRepeat) $("#fRepeat", el).onchange = (e) => { f.frequency = e.target.value; paintRepeat(); };
    $("#fAccount", el).onchange = (e) => {
        f.account_id = Number(e.target.value);
        touched.account = true;
        const acc = accountById(f.account_id);
        // A new movement defaults to the account's currency until an amount is typed
        if (isNew && acc && acc.currency !== f.currency && !f.amount) {
            f.currency = acc.currency;
            $("#fCurrency", el).value = f.currency;
            paintCurrency();
            f.rate = null;
            paintRate(true);
        }
        if (f.type === "transfer") paintType();
    };
    $("#fDest", el).onchange = (e) => { f.destination_account_id = Number(e.target.value) || null; };

    const applySuggestion = debounce(async (text) => {
        const hint = $("#suggestHint", el);
        if (text.trim().length < 3) { hint.hidden = true; return; }
        const s = await api.suggest(text).catch(() => null);
        if (!document.body.contains(el)) return;
        if (!s || s.source === "none") { hint.hidden = true; return; }
        if (!touched.type && s.type) f.type = s.type;
        if (!touched.category && s.category_id) f.category_id = s.category_id;
        if (!touched.account && s.account_id && accountById(s.account_id)?.is_active) f.account_id = s.account_id;
        if (f.type === "transfer" && s.destination_account_id && !f.destination_account_id) f.destination_account_id = s.destination_account_id;
        paintAccounts();
        paintType();
        const label = f.type === "transfer" ? typeLabel("transfer") : categoryById(f.category_id)?.name;
        hint.textContent = label ? t("tx.suggested", { label, source: sourceLabel(s.source) }) : "";
        hint.hidden = !label;
    }, 450);
    $("#fMerchant", el).oninput = (e) => { f.merchant = e.target.value; if (isNew) applySuggestion(f.merchant); };

    $("#saveBtn", el).onclick = async () => {
        f.merchant = $("#fMerchant", el).value.trim();
        f.note = $("#fNote", el).value.trim();
        if (!(f.amount > 0)) return toast(t("tx.amount_required"), true);
        if (f.type === "transfer" && !f.destination_account_id) return toast(t("tx.destination_required"), true);
        if (review && f.type !== "transfer" && !f.category_id) return toast(t("tx.category_to_approve"), true);

        const movement = {
            type: f.type,
            amount: f.amount,
            currency: f.currency,
            account_id: f.account_id,
            destination_account_id: f.type === "transfer" ? f.destination_account_id : null,
            category_id: f.type === "transfer" ? null : f.category_id,
            merchant: f.merchant || null,
            description: f.note || null,
        };
        let save, message;
        if (f.frequency) {
            const rule = { ...movement, frequency: f.frequency, start_date: f.date,
                end_date: $("#fUntil", el).value || null, auto_confirm: $("#fAuto", el).checked };
            save = () => isNew ? api.createRecurring(rule) : api.updateRecurring(tx.id, rule);
            message = (r) => r.created ? t("tx.saved_created", { count: r.created }) : t("common.saved");
        } else {
            const payload = {
                ...movement,
                exchange_rate: f.currency !== "CLP" && f.rateTyped ? f.rate : null,
                tags: $("#fTags", el).value.split(",").map(s => s.trim()).filter(Boolean),
            };
            // Keep the original time of day unless the user picked another date
            if (isNew || f.date !== tx.date.slice(0, 10)) payload.date = f.date;
            if (review) payload.status = "confirmed";
            save = () => isNew ? api.createTransaction(payload) : api.updateTransaction(tx.id, payload);
            message = t(review ? "review.approved" : "common.saved");
        }

        const btn = $("#saveBtn", el);
        btn.disabled = true;
        const saved = await attempt(save, message);
        btn.disabled = false;
        if (!saved) return;
        storage("lastAccountId", String(f.account_id));
        sheet.close();
        (onSaved || render)();
    };

    const seriesBtn = $("#seriesBtn", el);
    if (seriesBtn) {
        seriesBtn.onclick = async () => {
            const rule = (await attempt(api.recurring))?.find(r => r.id === tx.recurring_id);
            if (!rule) return;
            sheet.close();
            openTxSheet(rule, { recurring: true, onSaved });
        };
    }

    const deleteBtn = $("#deleteBtn", el);
    if (deleteBtn) {
        deleteBtn.onclick = async () => {
            const verb = t(review ? "common.discard" : "common.delete");
            const title = t(recurring ? "tx.delete_recurring" : review ? "review.discard_title" : "tx.delete");
            const msg = t(recurring ? "tx.delete_recurring_message"
                : tx.source === "email" ? "review.discard_message" : "common.cannot_undo");
            if (!await confirmDialog(title, msg, verb, true)) return;
            const remove = () => recurring ? api.deleteRecurring(tx.id) : api.deleteTransaction(tx.id);
            if (await attempt(remove, t(review ? "review.discarded" : "common.deleted"))) {
                sheet.close();
                (onSaved || render)();
            }
        };
    }
    if (isNew) setTimeout(() => $("#fAmount", el).focus({ preventScroll: true }), reducedMotion() ? 0 : 350);
}

function openAdjustmentSheet(tx, onSaved) {
    const sheet = openSheet(typeLabel("adjustment"), `
        <p class="muted">${tHtml("adjustment.note", { account: `<strong>${esc(accountById(tx.account_id)?.name || t("adjustment.the_account"))}</strong>` })}</p>
        <div class="card-title"><span>${esc(friendlyDate(tx.date))}</span><span class="amount">${esc(signedMoney(tx))}</span></div>
        ${tx.description ? `<p>${esc(tx.description)}</p>` : ""}
        <div class="sheet-actions"><button class="btn btn-danger btn-block" id="deleteAdj">${esc(t("adjustment.delete"))}</button></div>`);
    $("#deleteAdj", sheet.el).onclick = async () => {
        if (!await confirmDialog(t("adjustment.delete"), t("adjustment.delete_message"), t("common.delete"), true)) return;
        if (await attempt(() => api.deleteTransaction(tx.id), t("adjustment.deleted"))) {
            sheet.close();
            (onSaved || render)();
        }
    };
}

// =============================================================================
// Planning
// =============================================================================

const PLAN_METRICS = [["balance", t("plan.balance")], ["expense", t("common.expenses")], ["income", t("common.income")], ["net_worth", t("plan.net_worth")]];

/** Month totals with what recurring movements still plan to add (the net worth already includes it). */
const planTotals = (m) => {
    const income = m.income + m.planned_income;
    const expense = m.expense + m.planned_expense;
    return { income, expense, balance: income - expense, net_worth: m.net_worth };
};

/** Axis label: "mar" / "Mar", or ["ene", "2027"] (two lines) where a year starts */
function shortMonth(ym) {
    const [y, m] = ym.split("-").map(Number);
    const name = MONTHS[m - 1].slice(0, 3);
    return m === 1 ? [name, String(y)] : name;
}

async function renderPlan(container) {
    // Twelve months with the selected one in the middle; the header arrows move it
    const { months, current_month: current } = await api.timeline(shiftMonth(state.month, -6), 12);
    const selected = months.find(m => m.month === state.month);
    const totals = planTotals(selected);
    const line = (label, amount, planned, cls = "") => `
        <div class="row">
            <span class="row-main"><span class="row-title">${esc(label)}</span>${planned ? `<span class="row-sub">${esc(t("plan.includes_planned", { amount: money(planned) }))}</span>` : ""}</span>
            <span class="row-end amount ${cls}">${esc(money(amount))}</span>
        </div>`;

    container.innerHTML = `
        <div class="card plan-card">
            ${segmented(PLAN_METRICS, state.planMetric, "data-metric")}
            <div class="chart-box"><canvas role="img" aria-label="${esc(t("plan.chart_aria"))}"></canvas></div>
            <p class="section-note">${esc(t("plan.note"))}</p>
        </div>
        <section>
            <div class="sec-h"><h2>${esc(monthLabel(state.month))}</h2>${state.month > current ? `<span class="note">${esc(t("plan.planned"))}</span>` : ""}</div>
            <div class="card list plain-rows">
                ${line(t("common.income"), totals.income, selected.planned_income, "income")}
                ${line(t("common.expenses"), totals.expense, selected.planned_expense)}
                ${line(t("plan.balance"), totals.balance, 0, totals.balance < 0 ? "expense" : "income")}
                ${line(t("plan.net_worth_close"), totals.net_worth)}
            </div>
        </section>`;

    const canvas = $("canvas", container);
    const draw = () => {
        destroyCharts();
        const metric = state.planMetric;
        const color = { income: cssVar("--pos"), expense: cssVar("--neg"), net_worth: cssVar("--accent") };
        const bar = { borderRadius: 5, maxBarThickness: 34 };
        let datasets;
        if (metric === "income" || metric === "expense") {
            datasets = [
                { ...bar, label: t("plan.actual"), data: months.map(m => m[metric]), backgroundColor: color[metric] },
                { ...bar, label: t("plan.planned"), data: months.map(m => m[`planned_${metric}`]), backgroundColor: withAlpha(color[metric], .35) },
            ];
        } else {
            const values = months.map(m => planTotals(m)[metric]);
            const forecast = (m) => m.month > current || m.planned_income || m.planned_expense;
            datasets = [{
                ...bar,
                label: PLAN_METRICS.find(([key]) => key === metric)[1],
                data: values,
                backgroundColor: months.map((m, i) => withAlpha(
                    metric === "net_worth" ? color.net_worth : values[i] < 0 ? color.expense : color.income,
                    forecast(m) ? .4 : 1)),
            }];
        }
        const isSelected = (index) => months[index]?.month === state.month;
        makeChart(canvas, {
            type: "bar",
            data: { labels: months.map(m => shortMonth(m.month)), datasets },
            options: {
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },  // a tap anywhere in a month's column selects it
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false },
                        ticks: {
                            autoSkip: false,
                            maxRotation: 0,
                            color: (c) => isSelected(c.index) ? cssVar("--accent") : cssVar("--text-2"),
                            font: (c) => ({ weight: isSelected(c.index) ? "700" : "500" }),
                        },
                    },
                    y: {
                        stacked: true,
                        border: { display: false },
                        grid: { color: cssVar("--sep") },
                        ticks: { maxTicksLimit: 5, callback: (v) => compactMoney(v) },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${money(c.raw)}` } },
                },
                onClick: (_, [hit]) => {
                    if (!hit) return;
                    state.month = months[hit.index].month;
                    render();
                },
            },
        });
    };
    draw();

    container.onclick = (e) => {
        const btn = e.target.closest("[data-metric]");
        if (!btn || btn.dataset.metric === state.planMetric) return;
        selectSegment(btn);
        state.planMetric = btn.dataset.metric;
        draw();
    };
}

// =============================================================================
// Budgets
// =============================================================================

// [key, label, plural unit for "every N <unit>"]
const BUDGET_PERIODS = ["day", "week", "month", "year", "once"].map(key =>
    [key, t(`budget.period_${key}`), key === "once" ? "" : t(`budget.unit_${key}`)]);
const BUDGET_SCOPES = ["all", "include", "exclude"].map(key => [key, t(`budget.scope_${key}`)]);

function periodLabel(b) {
    const [, label, unit] = BUDGET_PERIODS.find(([key]) => key === b.period);
    return b.period_count > 1 ? t("budget.every_n", { count: b.period_count, unit }) : label;
}

function scopeLabel(b) {
    const names = b.category_ids.map(id => categoryById(id)?.name).filter(Boolean).join(", ");
    return b.scope === "all" ? t("budget.all_expenses") : b.scope === "include" ? names : t("budget.all_except", { names });
}

/** Share of the limit spent; "warn" from 80 % or when the current pace would exceed it. */
function budgetLevel(s) {
    const pct = s.limit ? s.spent / s.limit * 100 : 0;
    return { pct, level: pct > 100 ? "over" : pct >= 80 || s.forecast > s.limit ? "warn" : "" };
}

function budgetCard(b, tag = "button") {
    const s = b.status;
    const { pct, level } = budgetLevel(s);
    const left = s.limit - s.spent;
    const days = s.days_left ? t("budget.days_left", { count: s.days_left }) : "";
    return `
        <${tag} class="card budget-card" data-id="${b.id}">
            <span class="budget-head">
                <span class="row-main"><span class="row-title">${esc(b.name)}</span><span class="row-sub">${esc(scopeLabel(b))}</span></span>
                <span class="pill">${esc(periodLabel(b))}</span>
            </span>
            <span class="budget-amounts"><span class="amount">${esc(money(s.spent))}</span><span class="muted">${esc(t("common.of_amount", { amount: money(s.limit) }))}</span></span>
            <span class="meter ${level}" role="img" aria-label="${esc(t("budget.spent_aria", { pct: Math.round(pct) }))}"><span style="width:${Math.min(pct, 100)}%"></span></span>
            <span class="meter-note">${left >= 0 ? esc(t("budget.left", { amount: money(left) })) : `<span class="expense">${esc(t("budget.over", { amount: money(-left) }))}</span>`}${esc(days)} · ${esc(dayMonth(s.start))} – ${esc(dayMonth(s.end))}</span>
            ${level === "warn" && s.forecast > s.limit ? `<span class="meter-note warn">${esc(t("budget.forecast", { amount: money(s.forecast) }))}</span>` : ""}
        </${tag}>`;
}

async function renderBudgets(container) {
    const [{ budgets, expected_income: income }] = await Promise.all([api.budgets(), loadReferenceData()]);
    container.innerHTML = `
        ${budgets.length ? `<div class="budget-grid">${budgets.map(b => budgetCard(b)).join("")}</div>`
            : `<div class="card"><div class="empty">${icon("target")}<br>${esc(t("budget.empty_1"))}<br>${esc(t("budget.empty_2"))}</div></div>`}
        <button class="btn btn-primary btn-block" id="newBudget">${esc(t("budget.new_button"))}</button>`;
    container.onclick = (e) => {
        if (e.target.id === "newBudget") return openBudgetSheet(null, income);
        const card = e.target.closest("[data-id]");
        if (card) openBudgetDetail(budgets.find(b => b.id === Number(card.dataset.id)), income);
    };
}

/** A budget's periods and, for the chosen one, every movement it counts (biggest first, to spot odd ones). */
function openBudgetDetail(budget, expectedIncome) {
    const sheet = openSheet(budget.name, `
        <div class="field"><label for="bdPeriod">${esc(t("field.period"))}</label><select id="bdPeriod" class="select">
            <option value="">${esc(t("budget.current_period", { range: `${dayMonth(budget.status.start)} – ${dayMonth(budget.status.end)}` }))}</option>
        </select></div>
        <div id="bdStatus">${budgetCard(budget, "div")}</div>
        <section>
            <div class="sec-h"><h2>${esc(t("budget.transactions"))}</h2><span class="note" id="bdCount"></span></div>
            <div class="card list" id="bdList"><div class="empty">${esc(t("common.loading"))}</div></div>
        </section>
        <p class="section-note">${esc(t("budget.detail_note"))}</p>
        <div class="sheet-actions"><button class="btn btn-tinted btn-block" id="bdEdit">${esc(t("budget.edit"))}</button></div>`);
    const el = sheet.el;
    const select = $("#bdPeriod", el);
    let movements = [];

    const load = async () => {
        const period = await attempt(() => api.budgetPeriod(budget.id, select.value));
        if (!period || !document.body.contains(el)) return;
        movements = period.transactions;
        $("#bdStatus", el).innerHTML = budgetCard({ ...budget, status: period }, "div");
        $("#bdCount", el).textContent = movements.length || "";
        $("#bdList", el).innerHTML = movements.map(tx => txRow(tx, { withDate: true })).join("")
            || `<div class="empty">${esc(t("budget.no_expenses"))}</div>`;
    };
    load();
    if (budget.period !== "once") {
        api.budgetHistory(budget.id).then(periods => {
            select.insertAdjacentHTML("beforeend", periods.map(s =>
                `<option value="${s.start}">${esc(dayMonth(s.start))} – ${esc(dayMonth(s.end))} · ${esc(money(s.spent))} ${esc(t("common.of_amount", { amount: money(s.limit) }))}</option>`).join(""));
        }).catch(() => {});
    }
    select.onchange = load;
    $("#bdList", el).onclick = (e) => {
        const row = e.target.closest("[data-tx]");
        const tx = row && movements.find(t => t.id === Number(row.dataset.tx));
        // After a fix, refresh this list and the budgets underneath
        if (tx) openTxSheet(tx, { onSaved: () => { load(); render(); } });
    };
    $("#bdEdit", el).onclick = () => { sheet.close(); openBudgetSheet(budget, expectedIncome); };
}

function openBudgetSheet(budget, expectedIncome) {
    const isNew = !budget;
    const b = budget || { scope: "all", category_ids: [], amount_type: "fixed", period: "month", period_count: 1, start_date: todayISO().slice(0, 8) + "01" };
    const chosen = new Set(b.category_ids);
    const sheet = openSheet(t(isNew ? "budget.new" : "budget.edit"), `
        <div class="field"><label for="bName">${esc(t("field.name"))}</label><input id="bName" class="input" value="${esc(b.name || "")}" placeholder="${esc(t("budget.name_placeholder"))}"></div>
        <div>
            <div class="field-cap">${esc(t("budget.counts"))}</div>
            ${segmented(BUDGET_SCOPES, b.scope, "data-scope", "scopeSeg")}
        </div>
        <div class="chip-wrap" id="bCats"></div>
        <div>
            <div class="field-cap">${esc(t("field.amount"))}</div>
            ${segmented([["fixed", t("budget.fixed")], ["income_pct", t("budget.income_pct")]], b.amount_type, "data-amount-type", "amountSeg")}
        </div>
        <div class="field">
            <input id="bAmount" class="input" inputmode="decimal" aria-label="${esc(t("field.amount"))}" value="${esc(formatAmountInput(b.amount, b.amount_type === "fixed" ? "CLP" : "USD"))}">
            <p class="section-note" id="bIncomeNote" style="margin-top:6px"></p>
        </div>
        <div class="grid-2">
            <div class="field"><label for="bPeriod">${esc(t("field.period"))}</label><select id="bPeriod" class="select">
                ${BUDGET_PERIODS.map(([key, label]) => `<option value="${key}" ${key === b.period ? "selected" : ""}>${esc(label)}</option>`).join("")}
            </select></div>
            <div class="field" id="bCountField"><label for="bCount" id="bCountLabel"></label><input id="bCount" class="input" type="number" min="1" max="99" value="${b.period_count}"></div>
            <div class="field" id="bEndField"><label for="bEnd">${esc(t("field.until"))}</label><input id="bEnd" class="input" type="date" value="${esc(b.end_date || "")}"></div>
        </div>
        <div class="field"><label for="bStart">${esc(t("field.start_date"))}</label><input id="bStart" class="input" type="date" value="${esc(b.start_date)}"></div>
        <div class="sheet-actions">
            <button class="btn btn-primary btn-block" id="bSave">${esc(t("common.save"))}</button>
            ${isNew ? "" : `<button class="btn btn-plain btn-block" id="bDelete">${esc(t("budget.delete"))}</button>`}
        </div>`);
    const el = sheet.el;
    let scope = b.scope;
    let amountType = b.amount_type;

    const paint = () => {
        $("#bCats", el).hidden = scope === "all";
        $("#bCats", el).innerHTML = categoryChoices("expense", null).map(c => `
            <button type="button" class="chip" data-cat="${c.id}" aria-pressed="${chosen.has(c.id)}" style="--c:${esc(c.color)}">${icon(c.icon)}${esc(c.name)}</button>`).join("");
        const pct = amountType === "income_pct";
        $("#bAmount", el).placeholder = t(pct ? "budget.pct_placeholder" : "budget.amount_placeholder");
        $("#bIncomeNote", el).textContent = pct ? t("budget.income_note", { amount: money(expectedIncome) }) : "";
        $("#bIncomeNote", el).hidden = !pct;
        const period = BUDGET_PERIODS.find(([key]) => key === $("#bPeriod", el).value);
        const once = period[0] === "once";
        $("#bCountLabel", el).textContent = t("budget.repeat_every", { unit: period[2] });
        $("#bCountField", el).hidden = once;
        $("#bEndField", el).hidden = !once;
    };
    paint();
    $("#bPeriod", el).onchange = paint;
    el.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-scope], [data-amount-type], [data-cat]");
        if (!btn) return;
        if (btn.dataset.scope) { scope = btn.dataset.scope; selectSegment(btn); }
        if (btn.dataset.amountType) { amountType = btn.dataset.amountType; selectSegment(btn); }
        if (btn.dataset.cat) {
            const id = Number(btn.dataset.cat);
            if (!chosen.delete(id)) chosen.add(id);
        }
        paint();
    });

    const done = () => { sheet.close(); render(); };
    $("#bSave", el).onclick = async () => {
        const period = $("#bPeriod", el).value;
        const data = {
            name: $("#bName", el).value.trim(),
            scope,
            category_ids: [...chosen],
            amount_type: amountType,
            amount: parseAmount($("#bAmount", el).value),
            period,
            period_count: Number($("#bCount", el).value) || 1,
            start_date: $("#bStart", el).value,
            end_date: period === "once" ? $("#bEnd", el).value || null : null,
        };
        if (!data.name) return toast(t("common.name_required"), true);
        if (!(data.amount > 0)) return toast(t("tx.amount_required"), true);
        if (await attempt(() => isNew ? api.createBudget(data) : api.updateBudget(b.id, data), t("budget.saved"))) done();
    };
    const del = $("#bDelete", el);
    if (del) del.onclick = async () => {
        if (await confirmDialog(t("budget.delete"), t("budget.delete_message"), t("common.delete"), true)
            && await attempt(() => api.deleteBudget(b.id), t("budget.deleted"))) done();
    };
}

// =============================================================================
// Settings
// =============================================================================

// Titles and notes come from the catalogs: settings.<key> and settings.<key>_note
const SETTINGS_PAGES = {
    accounts: { icon: "wallet", group: "data", render: renderAccountsPage },
    categories: { icon: "tag", group: "data", render: renderCategoriesPage },
    recurring: { icon: "repeat", group: "data", render: renderRecurringPage },
    rules: { icon: "bolt", group: "data", render: renderRulesPage },
    rates: { icon: "dollar-sign", group: "data", render: renderRatesPage },
    mail: { icon: "mail", group: "import", render: renderMailPage },
    banks: { icon: "building-columns", group: "import", render: renderBanksPage },
    data: { icon: "backup", group: "security", render: renderDataPage },
    access: { icon: "lock", group: "security", render: renderAccessPage },
    users: { icon: "users", group: "security", render: renderUsersPage, admin: true },
};
Object.entries(SETTINGS_PAGES).forEach(([key, page]) => Object.assign(page, { title: t(`settings.${key}`), note: t(`settings.${key}_note`) }));

const settingsPages = () => Object.entries(SETTINGS_PAGES).filter(([, p]) => !p.admin || state.user?.is_admin);

// ---- Theme (System / Light / Dark) and language ---------------------------------

const THEME_COLORS = { light: "#EEF1F6", dark: "#0B0F19" };

function currentTheme() {
    const saved = storage("theme");
    return saved === "light" || saved === "dark" ? saved : "system";
}

function applyTheme(theme) {
    storage("theme", theme);
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    // Browser chrome color: forced theme wins over each meta's media query
    $$('meta[name="theme-color"]').forEach(m => {
        const metaTheme = (m.getAttribute("media") || "").includes("dark") ? "dark" : "light";
        m.content = THEME_COLORS[theme === "system" ? metaTheme : theme];
    });
}

/**
 * Background jobs (mail sync, exchange rates) save their results in the user's language: keep the server's copy
 * in step with the one this device shows. Remembered per device and user, so it is only sent when it changes.
 */
function syncServerLanguage() {
    const synced = `${state.user?.id}:${LANG}`;
    if (!state.user || storage("languageSynced") === synced) return;
    api.setLanguage(LANG).then(() => storage("languageSynced", synced)).catch(() => {});
}

/** Every string is rendered in the page's language, so a new one applies by reloading (which also syncs the server). */
function applyLanguage(choice) {
    setLanguageChoice(choice);
    window.location.reload();
}

async function renderSettings(container, sub) {
    const pages = settingsPages();
    const page = pages.find(([key]) => key === sub)?.[1];
    if (page) {
        await loadReferenceData();
        return page.render(container);
    }
    const info = await api.info().catch(() => ({}));
    const groups = [...new Set(pages.map(([, p]) => p.group))];
    const user = state.user;
    container.innerHTML = `
        <div class="settings">
            ${user ? `
            <div class="card list">
                <button class="row" data-page="access">
                    ${avatar("user")}
                    <span class="row-main"><span class="row-title">${esc(user.display_name)}</span><span class="row-sub">@${esc(user.username)}${user.is_admin ? ` · ${esc(t("users.admin"))}` : ""}</span></span>
                    ${chevron()}
                </button>
            </div>` : ""}
            <div class="sec-cap">${esc(t("settings.appearance"))}</div>
            <div class="card theme-box">
                <span class="row-title">${esc(t("settings.theme"))}</span>
                ${segmented([["system", t("settings.system")], ["light", t("settings.light")], ["dark", t("settings.dark")]], currentTheme(), "data-theme-choice")}
                <span class="row-title">${esc(t("settings.language"))}</span>
                ${segmented([["system", t("settings.system")], ...Object.entries(LANGUAGE_NAMES)], languageChoice(), "data-language-choice")}
            </div>
            <p class="section-note">${esc(t("settings.motion_note"))}</p>
            ${groups.map(group => `
                <div class="sec-cap">${esc(t(`settings.group_${group}`))}</div>
                <div class="card list">
                    ${pages.filter(([, p]) => p.group === group).map(([key, p]) => `
                        <button class="row" data-page="${key}">
                            <span class="tile">${icon(p.icon)}</span>
                            <span class="row-main"><span class="row-title">${esc(p.title)}</span><span class="row-sub">${esc(p.note)}</span></span>
                            ${chevron()}
                        </button>`).join("")}
                </div>`).join("")}
            <div class="footer-note">Expense Tracker ${esc(info.version || "")}</div>
        </div>`;
    container.onclick = (e) => {
        const themeBtn = e.target.closest("[data-theme-choice]");
        if (themeBtn) {
            selectSegment(themeBtn);
            return applyTheme(themeBtn.dataset.themeChoice);
        }
        const languageBtn = e.target.closest("[data-language-choice]");
        if (languageBtn) {
            if (languageBtn.dataset.languageChoice === languageChoice()) return;
            selectSegment(languageBtn);
            return applyLanguage(languageBtn.dataset.languageChoice);
        }
        const row = e.target.closest("[data-page]");
        if (row) go("settings", row.dataset.page);
    };
}

// ---- Accounts ----------------------------------------------------------------

async function renderAccountsPage(container) {
    const accounts = await api.accounts(true);
    const rows = (list) => list.map(a => `
        <button class="row" data-id="${a.id}">
            ${avatar(a.icon)}
            <span class="row-main"><span class="row-title">${esc(a.name)}</span><span class="row-sub">${esc(accountTypeLabel(a.type))} · ${esc(a.currency)}</span></span>
            <span class="row-end amount ${a.balance < 0 ? "expense" : ""}">${esc(money(a.balance, a.currency))}</span>
        </button>`).join("");
    const active = accounts.filter(a => a.is_active);
    const archived = accounts.filter(a => !a.is_active);
    container.innerHTML = `
        <div class="card list">${rows(active) || `<div class="empty">${esc(t("accounts.empty"))}</div>`}</div>
        <button class="btn btn-primary btn-block" id="newAccount">${esc(t("accounts.new_button"))}</button>
        ${archived.length ? `<div class="sec-cap">${esc(t("accounts.archived"))}</div><div class="card list">${rows(archived)}</div>` : ""}`;
    container.onclick = (e) => {
        if (e.target.id === "newAccount") return openAccountSheet(null);
        const row = e.target.closest("[data-id]");
        if (row) openAccountSheet(accounts.find(a => a.id === Number(row.dataset.id)));
    };
}

function openAccountSheet(acc) {
    const isNew = !acc;
    const typeCode = acc ? (ACCOUNT_TYPE_ALIASES[acc.type] || acc.type) : "corriente";
    const sheet = openSheet(t(isNew ? "accounts.new" : "accounts.edit"), `
        <div class="field"><label for="aName">${esc(t("field.name"))}</label><input id="aName" class="input" value="${esc(acc?.name || "")}" placeholder="${esc(t("accounts.name_placeholder"))}"></div>
        <div class="grid-2">
            <div class="field"><label for="aType">${esc(t("field.type"))}</label><select id="aType" class="select">
                ${ACCOUNT_TYPES.map(([code]) => `<option value="${code}" ${code === typeCode ? "selected" : ""}>${esc(accountTypeLabel(code))}</option>`).join("")}
                ${accountType(typeCode) ? "" : `<option value="${esc(acc.type)}" selected>${esc(acc.type)}</option>`}
            </select></div>
            <div class="field"><label for="aCurrency">${esc(t("field.currency"))}</label><select id="aCurrency" class="select" ${isNew ? "" : "disabled"}>
                ${CURRENCIES.map(c => `<option ${c === (acc?.currency || "CLP") ? "selected" : ""}>${c}</option>`).join("")}
            </select></div>
        </div>
        <div class="field">
            <label for="aBalance">${esc(t(isNew ? "accounts.opening_balance" : "accounts.current_balance"))}</label>
            <input id="aBalance" class="input" inputmode="decimal" value="${esc(acc ? formatAmountInput(acc.balance, acc.currency) || "0" : "")}" placeholder="0">
            <p class="section-note" style="margin-top:6px">${esc(t(isNew ? "accounts.debt_note" : "accounts.adjust_note"))}</p>
        </div>
        <div class="field" id="aNoteField" hidden><label for="aNote">${esc(t("accounts.adjust_reason"))}</label><input id="aNote" class="input"></div>
        <div class="sheet-actions">
            ${isNew ? "" : acc.is_active
                ? `<button class="btn btn-danger" id="aDelete">${esc(t("common.delete"))}</button>`
                : `<button class="btn" id="aRestore">${esc(t("common.reactivate"))}</button>`}
            <button class="btn btn-primary" id="aSave">${esc(t("common.save"))}</button>
        </div>`);
    const el = sheet.el;
    const done = () => { sheet.close(); render(); };
    const readBalance = () => {
        const text = $("#aBalance", el).value.trim();
        return /^[-−]/.test(text) ? -parseAmount(text) : parseAmount(text);
    };
    if (!isNew) {
        $("#aBalance", el).oninput = () => { $("#aNoteField", el).hidden = Math.abs(readBalance() - acc.balance) < 0.01; };
    }

    $("#aSave", el).onclick = async () => {
        const name = $("#aName", el).value.trim();
        if (!name) return toast(t("common.name_required"), true);
        const type = $("#aType", el).value;
        const data = { name, type, icon: (accountType(type) || [])[1] || "wallet" };
        if (isNew) {
            Object.assign(data, { currency: $("#aCurrency", el).value, balance: readBalance() });
            if (await attempt(() => api.createAccount(data), t("accounts.created"))) done();
        } else {
            if (Math.abs(readBalance() - acc.balance) >= 0.01) {
                data.balance = readBalance();
                data.adjustment_note = $("#aNote", el).value.trim() || null;
            }
            if (await attempt(() => api.updateAccount(acc.id, data), t("accounts.updated"))) done();
        }
    };
    const del = $("#aDelete", el);
    if (del) del.onclick = async () => {
        if (!await confirmDialog(t("accounts.delete_title"), t("accounts.delete_message"), t("common.delete"), true)) return;
        if (await attempt(() => api.deleteAccount(acc.id), r => r.message)) done();
    };
    const restore = $("#aRestore", el);
    if (restore) restore.onclick = async () => {
        if (await attempt(() => api.updateAccount(acc.id, { is_active: true }), t("accounts.reactivated"))) done();
    };
}

// ---- Categories --------------------------------------------------------------

let categoriesTab = "expense";

function renderCategoriesPage(container) {
    const list = categoryChoices(categoriesTab);
    container.innerHTML = `
        ${segmented([["expense", t("common.expenses")], ["income", t("common.income")]], categoriesTab, "data-cat-tab")}
        <div class="card list" id="catList">
            ${list.map(c => `
                <button class="row" data-id="${c.id}">
                    ${avatar(c.icon, c.color)}
                    <span class="row-main"><span class="row-title">${esc(c.name)}</span></span>
                    ${chevron()}
                </button>`).join("") || `<div class="empty">${esc(t("categories.empty"))}</div>`}
        </div>
        <button class="btn btn-primary btn-block" id="newCategory">${esc(t("categories.new_button"))}</button>`;
    container.onclick = (e) => {
        const tab = e.target.closest("[data-cat-tab]");
        if (tab) {
            if (tab.dataset.catTab === categoriesTab) return;
            categoriesTab = tab.dataset.catTab;
            selectSegment(tab);
            // Let the thumb slide before the list is replaced
            return setTimeout(() => renderCategoriesPage(container), reducedMotion() ? 0 : 180);
        }
        if (e.target.id === "newCategory") return openCategorySheet(null);
        const row = e.target.closest("[data-id]");
        if (row) openCategorySheet(categoryById(Number(row.dataset.id)));
    };
}

function openCategorySheet(cat) {
    const isNew = !cat;
    let chosenIcon = cat?.icon || "tag";
    const type = cat?.type || categoriesTab;
    const sheet = openSheet(t(isNew ? "categories.new" : "categories.edit"), `
        <div class="field"><label for="cName">${esc(t("field.name"))}</label><input id="cName" class="input" value="${esc(cat?.name || "")}"></div>
        <div class="grid-2">
            <div class="field"><label for="cType">${esc(t("field.type"))}</label><select id="cType" class="select">
                <option value="expense" ${type === "expense" ? "selected" : ""}>${esc(typeLabel("expense"))}</option>
                <option value="income" ${type === "income" ? "selected" : ""}>${esc(typeLabel("income"))}</option>
            </select></div>
            <div class="field"><label for="cColor">${esc(t("field.color"))}</label><input id="cColor" type="color" class="input" value="${esc(cat?.color || "#78909c")}"></div>
        </div>
        <div class="label">${esc(t("field.icon"))}</div>
        <div class="cat-grid" id="iconGrid">
            ${CATEGORY_ICON_CHOICES.map(name => `<button type="button" class="cat-chip ${name === chosenIcon ? "selected" : ""}" data-icon="${name}" aria-label="${name}">${icon(name)}</button>`).join("")}
        </div>
        <div class="sheet-actions">
            ${isNew ? "" : `<button class="btn btn-danger" id="cDelete">${esc(t("common.delete"))}</button>`}
            <button class="btn btn-primary" id="cSave">${esc(t("common.save"))}</button>
        </div>`);
    const el = sheet.el;
    const done = () => { sheet.close(); render(); };
    $("#iconGrid", el).onclick = (e) => {
        const b = e.target.closest("[data-icon]");
        if (!b) return;
        chosenIcon = b.dataset.icon;
        $$("[data-icon]", el).forEach(x => x.classList.toggle("selected", x === b));
    };
    $("#cSave", el).onclick = async () => {
        const data = { name: $("#cName", el).value.trim(), type: $("#cType", el).value, color: $("#cColor", el).value, icon: chosenIcon };
        if (!data.name) return toast(t("common.name_required"), true);
        if (await attempt(() => isNew ? api.createCategory(data) : api.updateCategory(cat.id, data), t("categories.saved"))) done();
    };
    const del = $("#cDelete", el);
    if (del) del.onclick = async () => {
        if (!await confirmDialog(t("categories.delete_title"), t("categories.delete_message"), t("common.delete"), true)) return;
        if (await attempt(() => api.deleteCategory(cat.id), r => r.message)) done();
    };
}

// ---- Recurring movements -------------------------------------------------------

async function renderRecurringPage(container) {
    const rules = await api.recurring();
    container.innerHTML = `
        <p class="section-note">${esc(t("recurring.note"))}</p>
        <div class="card list">${rules.map(r => {
            const v = txVisual(r);
            const next = r.next_date ? t("recurring.next", { date: dayMonth(r.next_date) }) : t("recurring.ended");
            return `
            <button class="row" data-id="${r.id}">
                ${avatar(v.icon, v.color)}
                <span class="row-main"><span class="row-title">${esc(r.merchant || v.label)}</span><span class="row-sub">${esc(FREQUENCY_LABELS[r.frequency])} · ${esc(next)}</span></span>
                <span class="row-end amount ${amountClass(r)}">${esc(signedMoney(r))}</span>
            </button>`;
        }).join("") || `<div class="empty">${esc(t("recurring.empty"))}</div>`}
        </div>
        <button class="btn btn-primary btn-block" id="newRecurring">${esc(t("recurring.new_button"))}</button>`;
    container.onclick = (e) => {
        if (e.target.id === "newRecurring") return openTxSheet(null, { recurring: true });
        const row = e.target.closest("[data-id]");
        if (row) openTxSheet(rules.find(r => r.id === Number(row.dataset.id)), { recurring: true });
    };
}

// ---- Rules -------------------------------------------------------------------

async function renderRulesPage(container) {
    const rules = await api.rules();
    const target = (r) => {
        if (r.tx_type === "transfer") return t("rules.transfer_to", { account: accountById(r.destination_account_id)?.name || "?" });
        const cat = categoryById(r.category_id);
        return cat ? archivedName(cat) : t("common.uncategorized");
    };
    container.innerHTML = `
        <p class="section-note">${esc(t("rules.note"))}</p>
        <div class="card list plain-rows">
            ${rules.map(r => `
                <button class="row" data-id="${r.id}">
                    <span class="row-main">
                        <span class="row-title ellipsis">${esc(r.name || r.pattern)}</span>
                        <span class="row-sub ellipsis">${r.is_active ? "" : esc(t("rules.paused"))}${esc(target(r))}</span>
                    </span>
                    ${chevron()}
                </button>`).join("") || `<div class="empty">${esc(t("rules.empty"))}</div>`}
        </div>
        <button class="btn btn-primary btn-block" id="newRule">${esc(t("rules.new_button"))}</button>`;
    container.onclick = (e) => {
        if (e.target.id === "newRule") return openRuleSheet(null);
        const row = e.target.closest("[data-id]");
        if (row) openRuleSheet(rules.find(r => r.id === Number(row.dataset.id)));
    };
}

function openRuleSheet(rule) {
    const isNew = !rule;
    const r = rule || { tx_type: "expense", match_field: "any", is_active: true };
    // Old rules may be typed "expense" while pointing at an income category
    const ruleType = r.tx_type === "transfer" ? "transfer" : categoryById(r.category_id)?.type || r.tx_type || "expense";
    const categoryOptions = (type) => categoryChoices(type)
        .map(c => `<option value="${c.id}" ${c.id === r.category_id ? "selected" : ""}>${esc(c.name)}</option>`).join("");
    const sheet = openSheet(t(isNew ? "rules.new" : "rules.edit"), `
        <div class="field"><label for="rName">${esc(t("rules.name_optional"))}</label><input id="rName" class="input" value="${esc(r.name || "")}"></div>
        <div class="field">
            <label for="rPattern">${esc(t("rules.if_contains"))}</label>
            <input id="rPattern" class="input" value="${esc(r.pattern || "")}" placeholder="jumbo OR lider OR unimarc">
            <p class="section-note" style="margin-top:6px">${esc(t("rules.pattern_note"))}</p>
        </div>
        <div class="grid-2">
            <div class="field"><label for="rType">${esc(t("rules.is_a"))}</label><select id="rType" class="select">
                ${["expense", "income", "transfer"].map(type => `<option value="${type}" ${type === ruleType ? "selected" : ""}>${esc(typeLabel(type))}</option>`).join("")}
            </select></div>
            <div class="field"><label for="rField">${esc(t("rules.search_in"))}</label><select id="rField" class="select">
                ${["any", "merchant", "description", "sender"]
                    .map(v => `<option value="${v}" ${v === r.match_field ? "selected" : ""}>${esc(t(`rules.field_${v}`))}</option>`).join("")}
            </select></div>
        </div>
        <div class="field" id="rCatField"><label for="rCategory">${esc(t("field.category"))}</label><select id="rCategory" class="select"></select></div>
        <div class="field" id="rDestField"><label for="rDest">${esc(t("rules.to_account"))}</label><select id="rDest" class="select">
            <option value="">${esc(t("tx.choose_account"))}</option>${accountOptions(r.destination_account_id)}
        </select></div>
        <div class="field"><label for="rAccount">${esc(t("rules.account_optional"))}</label><select id="rAccount" class="select">
            <option value="">${esc(t("rules.any_account"))}</option>${accountOptions(r.account_id)}
        </select></div>
        <label class="switch-row"><span>${esc(t("rules.active"))}</span><span class="switch"><input type="checkbox" id="rActive" ${r.is_active ? "checked" : ""}><span></span></span></label>
        <div class="sheet-actions">
            ${isNew ? "" : `<button class="btn btn-danger" id="rDelete">${esc(t("common.delete"))}</button>`}
            <button class="btn btn-primary" id="rSave">${esc(t("common.save"))}</button>
        </div>`);
    const el = sheet.el;
    if (!r.account_id) $("#rAccount", el).value = "";
    if (!r.destination_account_id) $("#rDest", el).value = "";
    const paint = () => {
        const type = $("#rType", el).value;
        $("#rCatField", el).hidden = type === "transfer";
        $("#rDestField", el).hidden = type !== "transfer";
        $("#rCategory", el).innerHTML = `<option value="">${esc(t("rules.choose_category"))}</option>` + categoryOptions(type);
    };
    paint();
    $("#rType", el).onchange = paint;
    const done = () => { sheet.close(); render(); };
    $("#rSave", el).onclick = async () => {
        const type = $("#rType", el).value;
        const data = {
            name: $("#rName", el).value.trim() || null,
            pattern: $("#rPattern", el).value.trim(),
            tx_type: type,
            match_field: $("#rField", el).value,
            category_id: type === "transfer" ? null : Number($("#rCategory", el).value) || null,
            destination_account_id: type === "transfer" ? Number($("#rDest", el).value) || null : null,
            account_id: Number($("#rAccount", el).value) || null,
            is_active: $("#rActive", el).checked,
        };
        if (await attempt(() => isNew ? api.createRule(data) : api.updateRule(r.id, data), t("rules.saved"))) done();
    };
    const del = $("#rDelete", el);
    if (del) del.onclick = async () => {
        if (await confirmDialog(t("rules.delete_title"), t("rules.delete_message"), t("common.delete"), true)
            && await attempt(() => api.deleteRule(r.id), t("rules.deleted"))) done();
    };
}

// ---- Exchange rates ------------------------------------------------------------

const clpRate = (value) => `$${Number(value).toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

async function renderRatesPage(container) {
    const paint = (s) => {
        const failed = s.last_attempt && s.last_attempt !== s.last_sync;
        const lines = [
            esc(s.last_sync ? t("rates.last_sync", { date: s.last_sync }) : t("rates.never")),
            failed ? `<span class="expense">${esc(t("rates.failed", { date: s.last_attempt, result: s.last_result || "" }))}</span>` : "",
            s.next_run ? `<span class="muted">${esc(t("rates.next", { date: s.next_run }))}</span>` : "",
            s.estimated_count ? `<span class="muted">${esc(t("rates.estimated", { count: s.estimated_count }))}</span>` : "",
        ].filter(Boolean);
        container.innerHTML = `
            <p class="section-note">${esc(t("rates.note"))}</p>
            <div class="card list">${s.currencies.map(c => `
                <div class="row">
                    <span class="row-main"><span class="row-title">${esc(c.code)}</span><span class="row-sub">${esc(c.name)}</span></span>
                    <span class="row-end">
                        <span class="amount">${esc(c.rate ? clpRate(c.rate) : t("rates.no_data"))}</span>
                        ${c.date ? `<span class="sub-amount">${esc(friendlyDate(c.date))}</span>` : ""}
                    </span>
                </div>`).join("")}
            </div>
            <div class="card">
                <div class="card-title">${esc(t("common.status"))}</div>
                <p class="small">${lines.join("<br>")}</p>
                <button class="btn btn-block" id="ratesSync">${esc(t("rates.update_now"))}</button>
            </div>`;
        $("#ratesSync", container).onclick = async (e) => {
            e.target.disabled = true;
            e.target.textContent = t("rates.downloading");
            const res = await attempt(api.syncRates);
            if (res) {
                toast(res.success ? t("rates.updated") : res.message, !res.success);
                paint(res);
            } else {
                e.target.disabled = false;
                e.target.textContent = t("rates.update_now");
            }
        };
    };
    paint(await api.ratesStatus());
}

// ---- Mail --------------------------------------------------------------------

const minutesLabel = (mins) => mins % 1440 === 0 ? t("time.days", { count: mins / 1440 })
    : mins % 60 === 0 ? t("time.hours", { count: mins / 60 }) : t("time.minutes", { count: mins });
const INTERVALS = [15, 30, 60, 180, 360, 720, 1440].map(mins => [mins, minutesLabel(mins)]);
const LOOKBACKS = [1, 3, 7, 14, 30].map(days => [days, t("time.days", { count: days })]);
const MAIL_SECURITY = [["ssl", "SSL/TLS"], ["starttls", "STARTTLS"]];

async function renderMailPage(container) {
    const [s, mailboxes, { providers, default_ports }] = await Promise.all([api.mailSettings(), api.mailAccounts(), api.mailProviders()]);
    const options = (list, value) => {
        const known = list.some(([v]) => v === value) ? list : [...list, [value, `${value}`]];
        return known.map(([v, l]) => `<option value="${v}" ${v === value ? "selected" : ""}>${esc(l)}</option>`).join("");
    };
    const status = (m) => m.has_secret ? ""
        : `<span class="pill pill-warn">${esc(t(m.provider === "outlook" ? "mail.not_connected" : "mail.no_password"))}</span>`;
    container.innerHTML = `
        <p class="section-note">${esc(t("mail.note"))}</p>
        <div class="card list plain-rows">
            ${mailboxes.map(m => `
                <div class="row">
                    <button class="row-main plain" data-edit="${m.id}">
                        <span class="row-title">${esc(m.name)} ${status(m)}</span>
                        <span class="row-sub">${esc(m.provider_label)} · ${esc(m.email)}</span>
                        ${m.last_result ? `<span class="row-sub">${esc(m.last_result)}</span>` : ""}
                    </button>
                    <label class="switch" aria-label="${esc(t("mail.read_aria", { name: m.name }))}"><input type="checkbox" data-toggle="${m.id}" ${m.is_enabled ? "checked" : ""}><span></span></label>
                </div>`).join("") || `<div class="empty">${esc(t("mail.empty"))}</div>`}
        </div>
        <button class="btn btn-primary btn-block" id="mNew">${esc(t("mail.add_button"))}</button>
        <div class="card">
            <div class="card-title">${esc(t("mail.sync_title"))}</div>
            <label class="switch-row"><span>${esc(t("mail.auto_sync"))}</span><span class="switch"><input type="checkbox" id="gEnabled" ${s.sync_enabled ? "checked" : ""}><span></span></span></label>
            <div class="grid-2">
                <div class="field"><label for="gInterval">${esc(t("mail.every"))}</label><select id="gInterval" class="select">${options(INTERVALS, s.interval_mins)}</select></div>
                <div class="field"><label for="gLookback">${esc(t("mail.lookback"))}</label><select id="gLookback" class="select">${options(LOOKBACKS, s.lookback_days)}</select></div>
            </div>
            <button class="btn btn-primary btn-block" id="gSave">${esc(t("common.save"))}</button>
        </div>
        <div class="card">
            <div class="card-title">${esc(t("common.status"))}</div>
            <p class="small">${esc(s.last_sync ? t("mail.last_sync", { date: s.last_sync }) : t("mail.never_synced"))}
            ${s.last_result ? `<br><span class="muted">${esc(s.last_result)}</span>` : ""}
            ${s.sync_enabled && s.next_run ? `<br><span class="muted">${esc(t("mail.next", { date: s.next_run }))}</span>` : ""}</p>
            <button class="btn btn-block" id="gSync" ${mailboxes.some(m => m.is_enabled) ? "" : "disabled"}>${esc(t("mail.sync_now"))}</button>
        </div>`;
    container.onchange = async (e) => {
        const id = Number(e.target.dataset.toggle);
        if (id && await attempt(() => api.updateMailAccount(id, { is_enabled: e.target.checked }), t(e.target.checked ? "mail.enabled" : "mail.disabled"))) render();
    };
    container.onclick = (e) => {
        if (e.target.id === "mNew") return openMailSheet(null, providers, default_ports);
        const btn = e.target.closest("[data-edit]");
        if (btn) openMailSheet(mailboxes.find(m => m.id === Number(btn.dataset.edit)), providers, default_ports);
    };
    $("#gSave", container).onclick = async () => {
        const data = {
            sync_enabled: $("#gEnabled", container).checked,
            interval_mins: Number($("#gInterval", container).value),
            lookback_days: Number($("#gLookback", container).value),
        };
        if (await attempt(() => api.saveMailSettings(data), t("mail.settings_saved"))) render();
    };
    $("#gSync", container).onclick = async (e) => {
        e.target.disabled = true;
        e.target.textContent = t("mail.syncing");
        const res = await attempt(() => api.syncMail());
        if (res) {
            toast(res.message, !res.success);
            await refreshBadge();
        }
        render();
    };
}

function openMailSheet(box, providers, defaultPorts) {
    const isNew = !box;
    const provider = (code) => providers.find(p => p.code === code);
    const sheet = openSheet(isNew ? t("mail.new") : box.name, `
        <div class="field"><label for="mProvider">${esc(t("field.type"))}</label><select id="mProvider" class="select">
            ${providers.map(p => `<option value="${p.code}" ${p.code === (box?.provider || "gmail") ? "selected" : ""}>${esc(p.label)}</option>`).join("")}
        </select></div>
        <div class="field"><label for="mName">${esc(t("field.name"))}</label><input id="mName" class="input" value="${esc(box?.name || "")}" placeholder="${esc(t("mail.name_placeholder"))}"></div>
        <div class="field"><label for="mEmail" id="mEmailLabel">${esc(t("mail.email"))}</label><input id="mEmail" class="input" value="${esc(box?.email || "")}" autocomplete="off" autocapitalize="off"></div>
        <div data-for="password">
            <p class="section-note" data-for="gmail" style="margin-bottom:12px">${tHtml("mail.gmail_note", { link: `<a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener">${esc(t("mail.app_password_link"))}</a>` })}</p>
            <div class="field"><label for="mPassword" id="mPasswordLabel">${esc(t("field.password"))}</label>
                <input id="mPassword" type="password" class="input" autocomplete="new-password" placeholder="${box?.has_secret ? esc(t("mail.password_saved")) : ""}"></div>
        </div>
        <div data-for="server">
            <div class="field"><label for="mHost">${esc(t("mail.server"))}</label><input id="mHost" class="input" value="${esc(box?.host || "")}" placeholder="${esc(t("mail.server_placeholder"))}" autocomplete="off" autocapitalize="off"></div>
            <div class="grid-2">
                <div class="field"><label for="mSecurity">${esc(t("mail.security"))}</label><select id="mSecurity" class="select">
                    ${MAIL_SECURITY.map(([v, l]) => `<option value="${v}" ${v === (box?.security || "ssl") ? "selected" : ""}>${l}</option>`).join("")}
                </select></div>
                <div class="field"><label for="mPort">${esc(t("mail.port"))}</label><input id="mPort" class="input" inputmode="numeric" value="${esc(box?.port || "")}"></div>
            </div>
            <p class="section-note" style="margin-bottom:12px">${esc(t("mail.server_note"))}</p>
        </div>
        <div class="field" data-for="imap"><label for="mFolders">${esc(t("mail.folders"))}</label>
            <textarea id="mFolders" class="input" rows="2" placeholder="${esc(t("mail.folders_placeholder"))}">${esc((box?.folders || []).join("\n"))}</textarea></div>
        <p class="section-note" data-for="pop3" style="margin-bottom:12px">${esc(t("mail.pop3_note"))}</p>
        <div data-for="oauth">
            <p class="section-note" style="margin-bottom:12px">${tHtml("mail.oauth_note", {
                link: `<a href="https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade" target="_blank" rel="noopener">${esc(t("mail.entra_link"))}</a>`,
                permission: "<em>IMAP.AccessAsUser.All</em>",
            })}</p>
            <div class="field"><label for="mClientId">${esc(t("mail.client_id"))}</label><input id="mClientId" class="input" value="${esc(box?.oauth_client_id || "")}" autocomplete="off" placeholder="00000000-0000-0000-0000-000000000000"></div>
            <div class="field"><label for="mTenant">${esc(t("mail.tenant"))}</label><input id="mTenant" class="input" value="${esc(box?.oauth_tenant || "")}" autocomplete="off" placeholder="common"></div>
            ${isNew ? `<p class="section-note" style="margin-bottom:12px">${esc(t("mail.save_then_connect"))}</p>` : `
            <div class="card">
                <p class="small" id="mOauthStatus">${esc(t(box.has_secret ? "mail.connected" : "mail.not_connected_yet"))}</p>
                <button class="btn btn-block" id="mOauth">${esc(t(box.has_secret ? "mail.reconnect" : "mail.connect"))}</button>
            </div>`}
        </div>
        <div class="sheet-actions">
            ${isNew ? "" : `<button class="btn btn-danger" id="mDelete">${esc(t("common.delete"))}</button>`}
            <button class="btn" id="mTest">${esc(t("mail.test"))}</button>
            <button class="btn btn-primary" id="mSave">${esc(t("common.save"))}</button>
        </div>`);
    const el = sheet.el;
    const done = () => { sheet.close(); render(); };
    const field = (id) => $(`#${id}`, el);
    const defaultPort = (proto, security) => defaultPorts.find(d => d.protocol === proto && d.security === security)?.port;

    const layout = () => {
        const p = provider(field("mProvider").value);
        const oauth = p.auth === "oauth";
        const fixed = p.code === "gmail" || p.code === "outlook";
        const shown = { password: !oauth, server: !fixed, imap: p.protocol === "imap", pop3: p.code === "pop3", gmail: p.code === "gmail", oauth };
        $$("[data-for]", el).forEach(n => { n.hidden = !shown[n.dataset.for]; });
        field("mEmailLabel").textContent = t(fixed ? "mail.email" : "mail.username");
        field("mPasswordLabel").textContent = t(p.code === "gmail" ? "mail.app_password" : "field.password");
    };
    field("mProvider").onchange = () => {
        const p = provider(field("mProvider").value);
        field("mPort").value = defaultPort(p.protocol, field("mSecurity").value) || p.port;
        layout();
    };
    field("mSecurity").onchange = () => {
        const port = defaultPort(provider(field("mProvider").value).protocol, field("mSecurity").value);
        if (port) field("mPort").value = port;
    };
    if (isNew) field("mPort").value = provider(field("mProvider").value).port;
    layout();

    const formData = () => {
        const p = provider(field("mProvider").value);
        const data = {
            provider: p.code,
            name: field("mName").value.trim() || p.label,
            email: field("mEmail").value.trim(),
            password: field("mPassword").value || null,
        };
        if (p.code === "imap" || p.code === "pop3") {
            Object.assign(data, { host: field("mHost").value.trim(), port: Number(field("mPort").value) || null, security: field("mSecurity").value });
        }
        if (p.protocol === "imap") data.folders = field("mFolders").value.split("\n").map(f => f.trim()).filter(Boolean);
        if (p.auth === "oauth") Object.assign(data, { oauth_client_id: field("mClientId").value.trim(), oauth_tenant: field("mTenant").value.trim() });
        return data;
    };

    field("mSave").onclick = async () => {
        const data = formData();
        const saved = await attempt(() => isNew ? api.createMailAccount(data) : api.updateMailAccount(box.id, data), t("mail.saved"));
        if (!saved) return;
        done();
        // A new Outlook mailbox goes straight on to the Microsoft login
        if (isNew && saved.provider === "outlook") openMailSheet(saved, providers, defaultPorts);
    };
    field("mTest").onclick = async (e) => {
        e.target.disabled = true;
        const res = await attempt(() => api.testMail({ ...formData(), account_id: box?.id || null }));
        e.target.disabled = false;
        if (res) toast(res.message, !res.success);
    };
    const del = field("mDelete");
    if (del) del.onclick = async () => {
        if (await confirmDialog(t("mail.delete_title"), t("mail.delete_message"), t("common.delete"), true)
            && await attempt(() => api.deleteMailAccount(box.id), t("mail.deleted"))) done();
    };
    const connect = field("mOauth");
    if (connect) connect.onclick = async () => {
        // Unsaved changes (client id, tenant, address) are stored before asking Microsoft
        if (!await attempt(() => api.updateMailAccount(box.id, formData()))) return;
        const flow = await attempt(() => api.mailOauthStart(box.id));
        if (!flow) return;
        connect.hidden = true;
        field("mOauthStatus").innerHTML = tHtml("mail.device_code", {
            link: `<a href="${esc(flow.verification_uri)}" target="_blank" rel="noopener">${esc(flow.verification_uri.replace(/^https?:\/\//, ""))}</a>`,
            code: `<strong style="font-size:18px;letter-spacing:1px">${esc(flow.user_code)}</strong>`,
        }) + `<br><span class="muted">${esc(t("mail.waiting"))}</span>`;
        let wait = flow.interval * 1000;
        const poll = async () => {
            if (!document.body.contains(el)) return;  // sheet closed: stop asking
            const res = await api.mailOauthPoll(box.id).catch(err => ({ status: "error", message: err.message }));
            if (res.status === "slow_down") wait += 5000;
            if (res.status === "pending" || res.status === "slow_down") return setTimeout(poll, wait);
            toast(res.message, res.status !== "ok");
            if (res.status === "ok") return done();
            field("mOauthStatus").textContent = res.message;
            connect.hidden = false;
        };
        setTimeout(poll, wait);
    };
}

// ---- Banks -------------------------------------------------------------------

async function renderBanksPage(container) {
    const banks = await api.banks();
    container.innerHTML = `
        <p class="section-note">${esc(t("banks.note"))}</p>
        <div class="card list plain-rows">
            ${banks.map(b => `
                <div class="row">
                    <button class="row-main plain" data-edit="${b.id}">
                        <span class="row-title">${esc(b.bank_name)}</span>
                        <span class="row-sub">${esc(accountById(b.default_account_id)?.name || t("banks.no_default"))}</span>
                    </button>
                    <label class="switch" aria-label="${esc(t("banks.enable_aria", { name: b.bank_name }))}"><input type="checkbox" data-toggle="${b.id}" ${b.is_enabled ? "checked" : ""}><span></span></label>
                </div>`).join("")}
        </div>`;
    container.onchange = async (e) => {
        const id = Number(e.target.dataset.toggle);
        if (id) await attempt(() => api.updateBank(id, { is_enabled: e.target.checked }), t(e.target.checked ? "banks.enabled" : "banks.disabled"));
    };
    container.onclick = (e) => {
        const btn = e.target.closest("[data-edit]");
        if (btn) openBankSheet(banks.find(b => b.id === Number(btn.dataset.edit)));
    };
}

function openBankSheet(bank) {
    const sheet = openSheet(bank.bank_name, `
        <div class="field"><label for="bSenders">${esc(t("banks.senders"))}</label>
            <textarea id="bSenders" class="input" rows="4">${esc(bank.sender_emails.join("\n"))}</textarea></div>
        <div class="field"><label for="bAccount">${esc(t("banks.default_account"))}</label><select id="bAccount" class="select">
            <option value="">${esc(t("banks.none"))}</option>${accountOptions(bank.default_account_id)}
        </select></div>
        <p class="section-note">${esc(t("banks.match_note"))}</p>
        <div class="sheet-actions"><button class="btn btn-primary" id="bSave">${esc(t("common.save"))}</button></div>`);
    if (!bank.default_account_id) $("#bAccount", sheet.el).value = "";
    $("#bSave", sheet.el).onclick = async () => {
        const data = {
            sender_emails: $("#bSenders", sheet.el).value.split(/[\n,;]+/).map(s => s.trim()).filter(Boolean),
            default_account_id: Number($("#bAccount", sheet.el).value) || null,
        };
        if (await attempt(() => api.updateBank(bank.id, data), t("banks.updated"))) { sheet.close(); render(); }
    };
}

// ---- Data --------------------------------------------------------------------

function renderDataPage(container) {
    container.innerHTML = `
        <div class="card">
            <div class="card-title">${esc(t("data.backup"))}</div>
            <p class="section-note">${esc(t("data.backup_note"))}</p>
            <a class="btn btn-block" href="/api/system/backup" download>${esc(t("data.download_backup"))}</a>
            ${state.user?.is_admin ? `
            <p class="section-note" style="margin-top:12px">${esc(t("data.full_backup_note"))}</p>
            <a class="btn btn-block" href="/api/system/backup-all" download>${esc(t("data.download_full_backup"))}</a>` : ""}
        </div>
        <div class="card">
            <div class="card-title">${esc(t("data.import_csv"))}</div>
            <p class="section-note">${esc(t("data.csv_note"))}</p>
            <input id="csvFile" type="file" accept=".csv,text/csv" class="input">
            <button class="btn btn-primary btn-block" id="csvImport" style="margin-top:10px" disabled>${esc(t("data.import"))}</button>
        </div>
        <div class="card danger-zone">
            <div class="card-title expense">${esc(t("data.reset_title"))}</div>
            <p class="section-note">${esc(t("data.reset_note"))}</p>
            <button class="btn btn-danger btn-block" id="resetBtn">${esc(t("data.reset_button"))}</button>
        </div>`;
    const fileInput = $("#csvFile", container);
    const importBtn = $("#csvImport", container);
    fileInput.onchange = () => { importBtn.disabled = !fileInput.files.length; };
    importBtn.onclick = async () => {
        const file = fileInput.files[0];
        if (!file) return;
        importBtn.disabled = true;
        importBtn.textContent = t("data.importing");
        const text = await file.text();
        await attempt(() => api.importCsv(text), r => r.message);
        importBtn.textContent = t("data.import");
        importBtn.disabled = false;
    };
    $("#resetBtn", container).onclick = () => {
        const sheet = openSheet(t("data.reset_sheet"), `
            <p>${tHtml("data.reset_prompt", { word: `<strong>${esc(t("data.reset_word"))}</strong>` })}</p>
            <div class="field"><input id="resetConfirm" class="input" autocomplete="off" aria-label="${esc(t("common.confirmation"))}"></div>
            <div class="sheet-actions"><button class="btn btn-danger btn-block" id="resetGo">${esc(t("data.reset_go"))}</button></div>`);
        $("#resetGo", sheet.el).onclick = async () => {
            const res = await attempt(() => api.resetData($("#resetConfirm", sheet.el).value), r => t("data.reset_done", { count: r.deleted }));
            if (res) { sheet.close(); refreshBadge(); }
        };
    };
}

// ---- Access ------------------------------------------------------------------

function renderAccessPage(container) {
    const user = state.user;
    container.innerHTML = `
        ${user ? `<p class="section-note">${tHtml("access.signed_in_as", { name: `<strong>${esc(user.display_name)}</strong>`, username: esc(user.username) })}</p>` : ""}
        <div class="card">
            <div class="card-title">${esc(t("access.change_password"))}</div>
            <div class="field"><label for="pCurrent">${esc(t("access.current_password"))}</label><input id="pCurrent" type="password" class="input" autocomplete="current-password"></div>
            <div class="field"><label for="pNew">${esc(t("access.new_password"))}</label><input id="pNew" type="password" class="input" autocomplete="new-password" placeholder="${esc(t("common.min_chars", { count: 6 }))}"></div>
            <button class="btn btn-primary btn-block" id="pSave">${esc(t("access.change_password"))}</button>
            <p class="section-note" style="margin-top:10px">${esc(t("access.change_note"))}</p>
        </div>
        <button class="btn btn-block" id="logoutBtn">${esc(t("access.logout"))}</button>`;
    $("#pSave", container).onclick = async () => {
        const current = $("#pCurrent", container).value;
        const next = $("#pNew", container).value;
        if (!current || next.length < 6) return toast(t("access.password_incomplete"), true);
        if (await attempt(() => api.changePassword(current, next), t("access.password_updated"))) {
            $("#pCurrent", container).value = "";
            $("#pNew", container).value = "";
        }
    };
    $("#logoutBtn", container).onclick = async () => {
        await api.logout().catch(() => {});
        window.location.replace("/");
    };
}

// ---- Users (administrators) ----------------------------------------------------

async function renderUsersPage(container) {
    const users = await api.users();
    container.innerHTML = `
        <p class="section-note">${esc(t("users.note"))}</p>
        <div class="card list">
            ${users.map(u => `
                <button class="row" data-id="${u.id}">
                    ${avatar("user")}
                    <span class="row-main">
                        <span class="row-title">${esc(u.display_name)}${u.id === state.user?.id ? esc(t("users.you")) : ""}</span>
                        <span class="row-sub">@${esc(u.username)}${u.is_admin ? ` · ${esc(t("users.admin"))}` : ""}${u.is_active ? "" : ` · ${esc(t("users.deactivated"))}`}</span>
                    </span>
                    ${chevron()}
                </button>`).join("")}
        </div>
        <button class="btn btn-primary btn-block" id="newUser">${esc(t("users.new_button"))}</button>`;
    container.onclick = (e) => {
        if (e.target.id === "newUser") return openUserSheet(null);
        const row = e.target.closest("[data-id]");
        if (row) openUserSheet(users.find(u => u.id === Number(row.dataset.id)));
    };
}

function openUserSheet(user) {
    const isNew = !user;
    const isSelf = user && user.id === state.user?.id;
    const sheet = openSheet(isNew ? t("users.new") : user.display_name, `
        ${isNew ? `<div class="field"><label for="uUsername">${esc(t("users.username"))}</label>
            <input id="uUsername" class="input" autocomplete="off" autocapitalize="none" spellcheck="false" placeholder="${esc(t("users.username_placeholder"))}">
            <p class="section-note" style="margin-top:6px">${esc(t("users.username_note"))}</p></div>` : ""}
        <div class="field"><label for="uName">${esc(t("field.name"))}</label><input id="uName" class="input" value="${esc(user?.display_name || "")}" placeholder="${esc(t("users.name_placeholder"))}"></div>
        <div class="field"><label for="uPassword">${esc(t(isNew ? "field.password" : "users.new_password_optional"))}</label>
            <input id="uPassword" type="password" class="input" autocomplete="new-password" placeholder="${esc(t("common.min_chars", { count: 6 }))}">
            ${isNew ? "" : `<p class="section-note" style="margin-top:6px">${esc(t("users.password_note"))}</p>`}</div>
        <label class="switch-row"><span>${esc(t("users.admin"))}</span><span class="switch"><input type="checkbox" id="uAdmin" ${user?.is_admin ? "checked" : ""} ${isSelf ? "disabled" : ""}><span></span></span></label>
        <div class="sheet-actions">
            ${isNew || isSelf ? "" : `<button class="btn btn-danger" id="uDelete">${esc(t("common.delete"))}</button>
                <button class="btn" id="uToggle">${esc(t(user.is_active ? "users.deactivate" : "common.reactivate"))}</button>`}
            <button class="btn btn-primary" id="uSave">${esc(t(isNew ? "users.create" : "common.save"))}</button>
        </div>`);
    const el = sheet.el;
    const done = () => { sheet.close(); render(); };

    $("#uSave", el).onclick = async () => {
        const password = $("#uPassword", el).value;
        const data = { display_name: $("#uName", el).value.trim(), is_admin: $("#uAdmin", el).checked };
        if (password && password.length < 6) return toast(t("users.password_short"), true);
        if (isNew) {
            data.username = $("#uUsername", el).value.trim().toLowerCase();
            if (!data.username || !password) return toast(t("users.username_password_required"), true);
            data.password = password;
            if (await attempt(() => api.createUser(data), t("users.created", { username: data.username }))) done();
        } else {
            if (!data.display_name) return toast(t("common.name_required"), true);
            if (isSelf) delete data.is_admin;
            if (password) data.password = password;
            if (await attempt(() => api.updateUser(user.id, data), t("users.updated"))) done();
        }
    };
    const toggle = $("#uToggle", el);
    if (toggle) toggle.onclick = async () => {
        if (user.is_active && !await confirmDialog(t("users.deactivate_title"), t("users.deactivate_message", { name: user.display_name }), t("users.deactivate"), true)) return;
        if (await attempt(() => api.updateUser(user.id, { is_active: !user.is_active }), t(user.is_active ? "users.deactivated_toast" : "users.reactivated"))) done();
    };
    const del = $("#uDelete", el);
    if (del) del.onclick = () => {
        const confirmSheet = openSheet(t("users.delete_title"), `
            <p>${tHtml("users.delete_message", { name: `<strong>${esc(user.display_name)}</strong>`, folder: "<code>data/users/deleted</code>" })}</p>
            <p>${tHtml("users.type_to_confirm", { username: `<strong>${esc(user.username)}</strong>` })}</p>
            <div class="field"><input id="delConfirm" class="input" autocomplete="off" autocapitalize="none" aria-label="${esc(t("common.confirmation"))}"></div>
            <div class="sheet-actions"><button class="btn btn-danger btn-block" id="delGo">${esc(t("users.delete_title"))}</button></div>`);
        $("#delGo", confirmSheet.el).onclick = async () => {
            if (await attempt(() => api.deleteUser(user.id, $("#delConfirm", confirmSheet.el).value), t("users.deleted"))) {
                confirmSheet.close();
                done();
            }
        };
    };
}

// =============================================================================
// Boot
// =============================================================================

function init() {
    applyI18n();
    $$(".tab").forEach(btn => {
        btn.onclick = () => {
            const { view, sub } = currentRoute();
            // Tapping the current tab scrolls back to the top, like iOS
            if (view === btn.dataset.nav && !sub && window.scrollY > 0) {
                window.scrollTo({ top: 0, behavior: reducedMotion() ? "auto" : "smooth" });
            } else {
                go(btn.dataset.nav);
            }
        };
    });
    $$("[data-month-step]").forEach(btn => {
        btn.onclick = () => {
            state.month = shiftMonth(state.month, Number(btn.dataset.monthStep));
            render();
        };
    });
    $("#backBtn").onclick = (e) => go(e.currentTarget.dataset.back);
    $("#addBtn").onclick = async () => {
        if (!state.accounts.length) await attempt(loadReferenceData);
        openTxSheet(null, { onSaved: render });
    };
    window.addEventListener("hashchange", () => {
        window.scrollTo(0, 0);
        render();
    });
    let scrollFrame = 0;
    window.addEventListener("scroll", () => {
        if (!scrollFrame) scrollFrame = requestAnimationFrame(() => { scrollFrame = 0; updateNavbar(); });
    }, { passive: true });
    window.addEventListener("resize", () => { updateNavbar(); fitHeroValue(); });
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        const top = $$(".sheet-backdrop.open").pop();
        top?.querySelector("[data-close], [data-answer='no']")?.click();
    });
    // Who is logged in decides what Settings shows (e.g. user administration for admins)
    api.authStatus()
        .then(s => {
            if (!s.authenticated) return window.location.replace("/");
            state.user = s.user;
            syncServerLanguage();
        })
        .catch(() => {})
        .finally(render);
}

init();
