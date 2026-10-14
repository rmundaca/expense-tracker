#!/bin/sh
export PATH="/opt/bin:/opt/sbin:$PATH"

HAS_MODERN_PY=0
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c 'import sys; print(sys.version_info.major * 10 + sys.version_info.minor)' 2>/dev/null)
    if [ -n "$PY_VER" ] && [ "$PY_VER" -ge 310 ]; then
        HAS_MODERN_PY=1
    fi
fi

if [ "$HAS_MODERN_PY" -eq 0 ] && [ ! -x "/opt/bin/opkg" ] && [ ! -x "/opt/bin/python3" ]; then
    echo "=================================================================="
    echo "ERROR: This application requires Python >= 3.10."
    echo "On this NAS, install 'Entware' from App Central"
    echo "before installing this package."
    echo "=================================================================="
    exit 1
fi

# Backup existing database and settings if upgrading
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
