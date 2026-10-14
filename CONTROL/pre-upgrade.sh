#!/bin/sh
export PATH="/opt/bin:/opt/sbin:$PATH"

APKG_PATH="/usr/local/AppCentral/expense-tracker"
PERSISTENT_BACKUP="/volume1/.@plugins/config/expense-tracker"
TMP_BACKUP="/tmp/expense_tracker_data_backup"

# data/ holds app.db (users), users/<id>.db (one database per user) and, before 2.1, expense_tracker.db.
# The persistent copy is replaced as a whole (not merged): a stale expense_tracker.db left there after
# the move to users/ must not come back on the next upgrade.
if [ -d "$APKG_PATH/data" ] && [ "$(ls -A "$APKG_PATH/data" 2>/dev/null)" ]; then
    mkdir -p "$TMP_BACKUP"
    cp -af "$APKG_PATH/data/." "$TMP_BACKUP/" 2>/dev/null || true

    if [ -d "/volume1" ]; then
        rm -rf "$PERSISTENT_BACKUP.new"
        mkdir -p "$PERSISTENT_BACKUP.new"
        if cp -af "$APKG_PATH/data/." "$PERSISTENT_BACKUP.new/"; then
            rm -rf "$PERSISTENT_BACKUP"
            mv "$PERSISTENT_BACKUP.new" "$PERSISTENT_BACKUP"
        fi
    fi
fi

exit 0
