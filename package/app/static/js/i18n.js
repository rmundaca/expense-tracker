"use strict";

// Translations. Each catalog in js/locales/<code>.js registers itself in window.LOCALES and must be loaded
// before this file. The language is fixed for the page's lifetime: changing it in Settings reloads the page.

const LANGUAGE_NAMES = { en: "English", es: "Español" };  // each in its own language, never translated
const DEFAULT_LANGUAGE = "en";
const LANGUAGE_KEY = "lang";  // localStorage: "en", "es"... or absent to follow the device

const LANG = (() => {
    const available = Object.keys(window.LOCALES || {});
    let saved = null;
    try { saved = localStorage.getItem(LANGUAGE_KEY); } catch (e) { /* storage unavailable */ }
    if (available.includes(saved)) return saved;
    const device = (navigator.languages || [navigator.language || ""]).map(l => String(l).toLowerCase().split("-")[0]);
    return device.find(code => available.includes(code)) || DEFAULT_LANGUAGE;
})();
const MESSAGES = window.LOCALES[LANG];
const FALLBACK = window.LOCALES[DEFAULT_LANGUAGE];
// Number and date formatting follow the language (e.g. es-CL writes 12.500,5 and en-US 12,500.5)
const LOCALE = MESSAGES["locale"];
const PLURALS = new Intl.PluralRules(LANG);

document.documentElement.lang = LANG;
// The server answers in the same language (error messages, sync results): see app/i18n on the backend
document.cookie = `lang=${LANG}; path=/; max-age=31536000; samesite=lax`;

/** "system" (follow the device) or a language code the user picked in Settings. */
function languageChoice() {
    try {
        const saved = localStorage.getItem(LANGUAGE_KEY);
        return LANGUAGE_NAMES[saved] ? saved : "system";
    } catch (e) {
        return "system";
    }
}

function setLanguageChoice(choice) {
    try {
        if (choice === "system") localStorage.removeItem(LANGUAGE_KEY);
        else localStorage.setItem(LANGUAGE_KEY, choice);
    } catch (e) { /* storage unavailable: the device language stays */ }
}

function i18nMessage(key, params) {
    let msg = MESSAGES[key] ?? FALLBACK[key] ?? key;
    // Plural forms: { "one": "...", "other": "..." }, chosen by params.count
    if (msg && typeof msg === "object" && !Array.isArray(msg)) {
        msg = msg[PLURALS.select(Number(params?.count) || 0)] ?? msg.other;
    }
    return msg;
}

/** The text of `key` in the current language, with {placeholders} replaced by `params`. */
function t(key, params) {
    const msg = i18nMessage(key, params);
    if (typeof msg !== "string" || !params) return msg;
    return msg.replace(/\{(\w+)\}/g, (match, name) => name in params ? String(params[name]) : match);
}

const I18N_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Like t(), but returns HTML: the text is escaped and `html` params are inserted as given (markup the caller built). */
function tHtml(key, html) {
    const escape = (s) => String(s).replace(/[&<>"']/g, c => I18N_ESCAPES[c]);
    return i18nMessage(key, html).split(/(\{\w+\})/).map(part => {
        const name = /^\{(\w+)\}$/.exec(part)?.[1];
        return name && html && name in html ? String(html[name]) : escape(part);
    }).join("");
}

/** Translates the static markup of a page: data-i18n (text), data-i18n-aria-label and data-i18n-placeholder. */
function applyI18n(root = document) {
    root.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-aria-label]").forEach(el => el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel)));
    root.querySelectorAll("[data-i18n-placeholder]").forEach(el => el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder)));
}
