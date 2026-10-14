# Expense Tracker for Asustor AS-202TE

A personal expense and income web app, designed to be used from your phone. It automatically imports the
transactions your Chilean banks email you (from Gmail, Outlook or any IMAP/POP3 mailbox), leaves them
"to review" with a suggested category, and learns from what you confirm.

It runs on the **Asustor AS-202TE** NAS (32-bit Intel Atom, 1 GB RAM, ADM 3.5.x, Python 3.11 via Entware),
and anywhere Python 3.10+ runs. It is built for Chile: amounts are in Chilean pesos (CLP) with USD, EUR and UF
converted at official rates, and the email parsers understand Chilean banks' notifications.

## What it does

- **Home**: net worth, the month's income and expenses, categories (list and pie charts), accounts and
  budgets. Each user chooses which cards to show and in what order (*Customize Home*).
- **Transactions**: history by day, with search and filters by account or category. From here you open
  **Review**: transactions imported from email (or recurring ones that ask for review); approve them with one tap or edit them.
- **Plan**: month-by-month bar chart of balance, expenses, income or net worth; future months include
  what recurring transactions plan.
- **Budgets**: limits for all expenses, only some categories, or everything except some; daily, weekly,
  monthly, yearly (every N periods) or one-off; with a fixed amount or a % of the expected monthly income.
  Tapping one shows the transactions it counts in each period, largest first, to spot expenses that don't belong.
- **Settings**: appearance and language, accounts, categories, recurring transactions, rules, mailboxes,
  banks, backup/CSV import, password and users.

How it works:

- **Computed balances**: each account's balance is its opening balance plus its confirmed transactions,
  converted to the account's currency at each transaction's exchange rate.
  Correcting a balance records an *adjustment*, which counts as neither income nor expense.
- **Recurring transactions** (daily, weekly, monthly or yearly): each repetition is recorded on its date,
  including those that fall while the NAS is off. One on the 31st falls on the last day of shorter months.
- **Multi-currency** (CLP, USD, EUR, UF) with official values from [mindicador.cl](https://mindicador.cl)
  (no credentials needed), updated daily.
- **Categorization** in three levels: rules (`jumbo OR lider`, whole words), memory of what you chose
  for each merchant, and a lightweight Naive Bayes as a last resort.
- **Several fully independent users**: each one has their own accounts, transactions, categories, rules,
  learning and mailboxes. Nothing is shared between users.
- **Username and password sign-in**. The first user (an administrator) is created on first access;
  after that, only an administrator creates users in **Settings > Users** (there is no public sign-up).

## Languages

The app is available in **English** and **Spanish**. Each user picks the language in
**Settings > Appearance > Language**; *System* follows the device's language (English when it is neither).
The choice is stored on the device and also on the server, so background jobs (mail sync, exchange rates)
write their status messages in it. A new user's default accounts, categories and rules are named in the
language of whoever creates them: the administrator's for users added in Settings > Users, the setup
screen's for the first user. They are ordinary data afterwards and can be renamed.

Translations live in two places, each with one file per language:

- Web app: `package/app/static/js/locales/<code>.js` (loaded by `index.html` and `login.html`).
- Server messages and default data: `package/app/i18n/<code>.py` (registered in `package/app/i18n/__init__.py`).

To add a language, copy the English files, translate the values (keep the keys and `{placeholders}`),
register it in both places and add its name to `LANGUAGE_NAMES` in `static/js/i18n.js`.
`tests/test_i18n.py` checks that every catalog has the same keys and placeholders.

## Local development

```bash
run_local.bat                       # http://localhost:8010
```

Tests (with the same versions the NAS uses):

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests
```

Tests use a temporary database; they never touch `package/data/`.

## Building and installing on the NAS

```bash
python build_package.py            # builds dist/expense-tracker.apk (bumps the version)
```

1. In ADM, install **Entware** from App Central.
2. **App Central > Management > Manual Install**, upload `dist/expense-tracker.apk`.
3. Open the app (port **8010**) and **create the administrator right away**: while no user exists,
   whoever opens the app first defines it.

Upgrades keep the data (`data/app.db` and `data/users/`). The package never includes data: the
databases, logs and backups stay on the NAS only.

**Security**: the app serves plain HTTP. Use it on your home network or through a VPN, not exposed
to the internet.

## Users

- **Create**: Settings > Users > New user (username, name, password and whether they are an administrator).
  Each new user starts with the default accounts, categories, rules and banks.
- **Reset a password or deactivate**: immediately closes that user's open sessions.
  A deactivated user keeps their data and can be reactivated.
- **Delete**: asks you to type the username. Their database is not erased: it is archived in
  `data/users/deleted/` on the NAS.
- At least one active administrator must always remain.
- **Backup**: in Settings > Data and backup, each user downloads only their own data; an administrator
  can also download the full backup (a `.zip` with `app.db` and every database in `users/`).
  Mail passwords and tokens are stored encrypted with `data/secret.key`, which is not part of the
  backups: when restoring on another device they must be entered again.

## Setting up email

In **Settings > Email** each user adds one or more mailboxes, turns on automatic sync and uses **Test**.
In **Settings > Banks** you review each bank's senders and its default account.

- **Gmail**: with 2-Step Verification on, create a Google
  [app password](https://myaccount.google.com/apppasswords) and use it as the password.
- **Outlook / Hotmail / Microsoft 365**: Microsoft does not accept passwords over IMAP, so OAuth2 is used.
  Each user registers their own application in [Microsoft Entra](https://entra.microsoft.com) > App
  registrations: account type "Accounts in any organizational directory and personal Microsoft accounts",
  **Allow public client flows** = Yes, and the delegated permission `IMAP.AccessAsUser.All` (Office 365
  Exchange Online). Its "Application (client) ID" goes in the mailbox; then **Connect to Microsoft** shows a
  code to enter at microsoft.com/devicelogin. On work accounts the administrator may have to approve the
  application or enable IMAP.
- **Other IMAP** (Yahoo, iCloud, Zoho, corporate mail): server, port and security (SSL/TLS or
  STARTTLS). Optionally, the folders to check; otherwise the inbox and, if it is empty, the
  "All Mail" folder.
- **POP3**: last resort. It only sees the inbox and reads headers from the newest email backwards.
  It never deletes emails. Gmail over POP delivers each email only once.

## Architecture

- **Backend**: FastAPI `<0.100` + Pydantic v1 + SQLAlchemy 1.4 (32-bit compatible), SQLite in WAL mode.
- **Frontend**: HTML/CSS/JS with no dependencies and no build step (`package/app/static`).
- **Jobs**: APScheduler (mail every N minutes, exchange rates daily).
- **Data**: `data/app.db` holds the users (`models/app_schemas.py`); each user has their own database
  `data/users/<id>.db` with the full schema (`models/schemas.py`). `get_db` opens the database of the
  session's user, so no query needs to filter by user.
- **Migrations**: `run_migrations()` in `package/app/models/schemas.py`, versioned with `schema_version`;
  they are applied to each user's database the first time it is opened. The move from a single user is in
  `core/app_setup.py`.
- **Translations**: `package/app/i18n` (server) and `package/app/static/js/i18n.js` + `js/locales/` (web app);
  see [Languages](#languages).

## License

[MIT](LICENSE). Chart.js (bundled in `package/app/static/js/vendor/`) is also MIT licensed.
