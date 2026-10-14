// Thin client for the backend API. Every call returns parsed JSON or throws an Error with the server message.

async function request(method, path, body) {
    const options = { method, headers: {} };
    if (body !== undefined) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }
    const res = await fetch(path, options);
    if (res.status === 401) {
        // Session expired: the root route serves the login page
        window.location.replace("/");
        throw new Error(t("error.session_expired"));
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(", ") : data.detail;
        throw new Error(detail || t("error.status", { status: res.status }));
    }
    return data;
}

function query(params) {
    const q = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") q.set(k, v);
    });
    const s = q.toString();
    return s ? `?${s}` : "";
}

const api = {
    dashboard: (params) => request("GET", `/api/stats/dashboard${query(params)}`),
    saveHomeLayout: (cards) => request("PUT", "/api/stats/home-layout", cards),
    timeline: (start, months) => request("GET", `/api/stats/timeline${query({ start, months })}`),

    transactions: (params) => request("GET", `/api/transactions${query(params)}`),
    pendingCount: () => request("GET", "/api/transactions/pending-count"),
    createTransaction: (data) => request("POST", "/api/transactions", data),
    updateTransaction: (id, data) => request("PUT", `/api/transactions/${id}`, data),
    deleteTransaction: (id) => request("DELETE", `/api/transactions/${id}`),
    confirmTransaction: (id) => request("POST", `/api/transactions/${id}/confirm`),
    confirmAll: () => request("POST", "/api/transactions/confirm-all"),
    suggest: (merchant) => request("GET", `/api/transactions/suggest${query({ merchant })}`),

    recurring: () => request("GET", "/api/recurring"),
    createRecurring: (data) => request("POST", "/api/recurring", data),
    updateRecurring: (id, data) => request("PUT", `/api/recurring/${id}`, data),
    deleteRecurring: (id) => request("DELETE", `/api/recurring/${id}`),

    budgets: () => request("GET", "/api/budgets"),
    budgetHistory: (id) => request("GET", `/api/budgets/${id}/history`),
    budgetPeriod: (id, day) => request("GET", `/api/budgets/${id}/period${query({ day })}`),
    createBudget: (data) => request("POST", "/api/budgets", data),
    updateBudget: (id, data) => request("PUT", `/api/budgets/${id}`, data),
    deleteBudget: (id) => request("DELETE", `/api/budgets/${id}`),

    // withBalances=false skips the (costly) balance computation when only names/currencies are needed
    accounts: (includeArchived, withBalances = true) => request("GET", `/api/accounts${query({
        include_archived: includeArchived ? "true" : "", with_balances: withBalances ? "" : "false" })}`),
    createAccount: (data) => request("POST", "/api/accounts", data),
    updateAccount: (id, data) => request("PUT", `/api/accounts/${id}`, data),
    deleteAccount: (id) => request("DELETE", `/api/accounts/${id}`),

    categories: (includeArchived) => request("GET", `/api/categories${query({ include_archived: includeArchived ? "true" : "" })}`),
    createCategory: (data) => request("POST", "/api/categories", data),
    updateCategory: (id, data) => request("PUT", `/api/categories/${id}`, data),
    deleteCategory: (id) => request("DELETE", `/api/categories/${id}`),

    rules: () => request("GET", "/api/rules"),
    createRule: (data) => request("POST", "/api/rules", data),
    updateRule: (id, data) => request("PUT", `/api/rules/${id}`, data),
    deleteRule: (id) => request("DELETE", `/api/rules/${id}`),

    banks: () => request("GET", "/api/banks"),
    updateBank: (id, data) => request("PUT", `/api/banks/${id}`, data),

    mailProviders: () => request("GET", "/api/mail/providers"),
    mailSettings: () => request("GET", "/api/mail/settings"),
    saveMailSettings: (data) => request("PUT", "/api/mail/settings", data),
    mailAccounts: () => request("GET", "/api/mail/accounts"),
    createMailAccount: (data) => request("POST", "/api/mail/accounts", data),
    updateMailAccount: (id, data) => request("PUT", `/api/mail/accounts/${id}`, data),
    deleteMailAccount: (id) => request("DELETE", `/api/mail/accounts/${id}`),
    testMail: (data) => request("POST", "/api/mail/test", data),
    mailOauthStart: (id) => request("POST", `/api/mail/accounts/${id}/oauth/start`),
    mailOauthPoll: (id) => request("POST", `/api/mail/accounts/${id}/oauth/poll`),
    syncMail: (accountId) => request("POST", `/api/mail/sync${query({ account_id: accountId })}`),

    rate: (currency, date) => request("GET", `/api/exchange-rates/rate${query({ currency, date })}`),
    ratesStatus: () => request("GET", "/api/exchange-rates/status"),
    syncRates: () => request("POST", "/api/exchange-rates/sync"),

    info: () => request("GET", "/api/system/info"),
    setLanguage: (language) => request("PUT", "/api/system/language", { language }),
    importCsv: (content) => request("POST", "/api/system/import-csv", { csv_content: content }),
    resetData: (confirm) => request("POST", "/api/system/reset-data", { confirm }),

    authStatus: () => request("GET", "/api/auth/status"),
    changePassword: (current, next) => request("POST", "/api/auth/change-password", { current_password: current, new_password: next }),
    logout: () => request("POST", "/api/auth/logout"),

    users: () => request("GET", "/api/users"),
    createUser: (data) => request("POST", "/api/users", data),
    updateUser: (id, data) => request("PATCH", `/api/users/${id}`, data),
    deleteUser: (id, confirm) => request("DELETE", `/api/users/${id}${query({ confirm })}`),
};
