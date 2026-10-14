#!/bin/sh
APKG_PATH="/usr/local/AppCentral/expense-tracker"
cd "$APKG_PATH" || exit 1

mkdir -p data
LOG_FILE="$APKG_PATH/data/install.log"
echo "=== Expense Tracker installation: $(date) ===" > "$LOG_FILE"

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

# 2. Check for (and install) Python 3.11 from Entware; opkg needs --force-space on ADM
if [ -x "/opt/bin/opkg" ]; then
    echo "[1/4] Checking Entware packages..." >> "$LOG_FILE"
    if [ ! -x "/opt/bin/python3" ] || [ ! -x "/opt/bin/pip3" ]; then
        echo "Installing python3, pip, openssl and sqlite3 with opkg..." >> "$LOG_FILE"
        /opt/bin/opkg install --force-space python3 python3-pip python3-openssl python3-sqlite3 >> "$LOG_FILE" 2>&1
    fi

    if [ ! -x "/opt/bin/virtualenv" ] && [ -x "/opt/bin/pip3" ]; then
        echo "Installing virtualenv..." >> "$LOG_FILE"
        /opt/bin/pip3 install --no-cache-dir virtualenv >> "$LOG_FILE" 2>&1
    fi
fi

# 3. Find the Python binary
PYTHON_EXE=""
if [ -x "/opt/bin/python3" ]; then
    PYTHON_EXE="/opt/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="python3"
fi

if [ -z "$PYTHON_EXE" ]; then
    echo "ERROR: no Python 3 found." >> "$LOG_FILE"
    exit 1
fi

echo "[2/4] Python found: $PYTHON_EXE ($($PYTHON_EXE --version 2>&1))" >> "$LOG_FILE"

# 4. Create the virtual environment
if [ ! -x "venv/bin/python" ]; then
    echo "[3/4] Creating the venv..." >> "$LOG_FILE"
    rm -rf venv
    if [ -x "/opt/bin/virtualenv" ]; then
        /opt/bin/virtualenv -p "$PYTHON_EXE" venv >> "$LOG_FILE" 2>&1
    else
        "$PYTHON_EXE" -m venv venv >> "$LOG_FILE" 2>&1
    fi
fi

# 5. Install the dependencies (versions pinned for 32-bit)
if [ -f "requirements.txt" ] && [ -x "venv/bin/pip" ]; then
    echo "[4/4] Installing dependencies into the venv..." >> "$LOG_FILE"
    ./venv/bin/pip install --upgrade pip >> "$LOG_FILE" 2>&1
    # Remove packages that are incompatible with Pydantic v1
    ./venv/bin/pip uninstall -y pydantic-settings pydantic-core >> "$LOG_FILE" 2>&1 || true
    ./venv/bin/pip install --no-cache-dir -r requirements.txt >> "$LOG_FILE" 2>&1
    # Optional: a prebuilt scikit-learn wheel, if one exists for i686
    ./venv/bin/pip install --no-cache-dir --only-binary :all: scikit-learn >> "$LOG_FILE" 2>&1 || true
fi

chmod -R 755 data
# Key that encrypts the stored mail credentials: readable by the app only
[ -f data/secret.key ] && chmod 600 data/secret.key
echo "=== Installation completed successfully: $(date) ===" >> "$LOG_FILE"
exit 0
