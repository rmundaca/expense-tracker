#!/bin/sh
APKG_PATH="/usr/local/AppCentral/expense-tracker"
cd "$APKG_PATH" || exit 1

mkdir -p data
LOG_FILE="$APKG_PATH/data/install.log"
echo "=== Expense Tracker upgrade (post-upgrade): $(date) ===" >> "$LOG_FILE"

# Restore the data and databases if a previous backup exists
PERSISTENT_BACKUP="/volume1/.@plugins/config/expense-tracker"
TMP_BACKUP="/tmp/expense_tracker_data_backup"

# Databases always come from the backup: app.db (users), users/ (one database per user)
# and expense_tracker.db (single-user installs before 2.1, moved to users/ on first start)
restore_data() {
    SRC="$1"
    echo "Restoring databases and settings from $SRC..." >> "$LOG_FILE"
    cp -an "$SRC/." "$APKG_PATH/data/" 2>/dev/null || true
    for DB in app.db expense_tracker.db; do
        for F in "$DB" "$DB-wal" "$DB-shm"; do
            [ -f "$SRC/$F" ] && cp -af "$SRC/$F" "$APKG_PATH/data/" 2>/dev/null || true
        done
    done
    [ -d "$SRC/users" ] && cp -af "$SRC/users" "$APKG_PATH/data/" 2>/dev/null || true
}

if [ -d "$PERSISTENT_BACKUP" ] && [ "$(ls -A "$PERSISTENT_BACKUP" 2>/dev/null)" ]; then
    restore_data "$PERSISTENT_BACKUP"
elif [ -d "$TMP_BACKUP" ] && [ "$(ls -A "$TMP_BACKUP" 2>/dev/null)" ]; then
    restore_data "$TMP_BACKUP"
fi

# 1. Make sure Entware is on the PATH
export PATH="/opt/bin:/opt/sbin:$PATH"

# 2. Install the dependencies if requirements.txt exists
if [ -f "requirements.txt" ] && [ -x "venv/bin/pip" ]; then
    ./venv/bin/pip install --no-cache-dir -r requirements.txt >> "$LOG_FILE" 2>&1 || true
fi

chmod -R 755 data
# Key that encrypts the stored mail credentials: readable by the app only
[ -f data/secret.key ] && chmod 600 data/secret.key
echo "=== Upgrade completed successfully: $(date) ===" >> "$LOG_FILE"
exit 0
