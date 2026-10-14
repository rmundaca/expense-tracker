"""Movements, balances, transfers, adjustments and the dashboard through the HTTP API."""


def balances(client):
    return {a["id"]: a["balance"] for a in client.get("/api/accounts", params={"include_archived": True}).json()}


def create(client, **fields):
    payload = {"type": "expense", "amount": 1000, "currency": "CLP", "date": "2026-09-10", "merchant": "Test"}
    payload.update(fields)
    res = client.post("/api/transactions", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def test_balances_follow_movements(client, ids):
    start = balances(client)
    create(client, account_id=ids["checking"], amount=5000, category_id=ids["groceries"])
    create(client, account_id=ids["checking"], type="income", amount=20000, category_id=ids["salary"])
    after = balances(client)
    assert after[ids["checking"]] == start[ids["checking"]] + 15000


def test_transfer_can_be_edited_and_deleted(client, ids):
    tx = create(client, type="transfer", account_id=ids["checking"], destination_account_id=ids["cash"], amount=30000)
    assert tx["category_id"] is None
    b = balances(client)
    assert b[ids["checking"]] == -30000 and b[ids["cash"]] == 30000

    res = client.put(f"/api/transactions/{tx['id']}", json={"amount": 10000, "destination_account_id": ids["card"]})
    assert res.status_code == 200, res.text
    b = balances(client)
    assert b[ids["checking"]] == -10000 and b[ids["cash"]] == 0 and b[ids["card"]] == 10000

    assert client.delete(f"/api/transactions/{tx['id']}").status_code == 200
    assert all(v == 0 for v in balances(client).values())


def test_transfer_validation(client, ids):
    base = {"type": "transfer", "amount": 100, "date": "2026-09-10", "account_id": ids["checking"]}
    assert client.post("/api/transactions", json=base).status_code == 400
    assert client.post("/api/transactions", json={**base, "destination_account_id": ids["checking"]}).status_code == 400


def test_foreign_expense_converts_into_account_currency(client, ids, usd_rate):
    # US$ 10 charged to a CLP account reduces it by the CLP equivalent, not by 10
    tx = create(client, account_id=ids["card"], amount=10, currency="USD", date="2026-09-10", category_id=ids["groceries"])
    assert tx["exchange_rate"] == 950 and tx["base_amount"] == 9500
    assert balances(client)[ids["card"]] == -9500


def test_cross_currency_transfer_uses_the_rate_of_its_date(client, ids, usd_rate):
    create(client, type="transfer", account_id=ids["checking"], destination_account_id=ids["usd_card"],
           amount=95000, date="2026-09-10")
    assert balances(client)[ids["usd_card"]] == 100.0  # 95.000 CLP / 950


def test_changing_date_or_currency_recomputes_rate(client, ids, usd_rate):
    tx = create(client, account_id=ids["card"], amount=10, currency="USD", date="2026-09-10", category_id=ids["groceries"])
    moved = client.put(f"/api/transactions/{tx['id']}", json={"date": "2026-03-01"}).json()
    assert moved["exchange_rate"] == 900 and moved["base_amount"] == 9000
    clp = client.put(f"/api/transactions/{tx['id']}", json={"currency": "CLP", "amount": 5000}).json()
    assert clp["exchange_rate"] == 1 and clp["base_amount"] == 5000


def test_category_must_match_type(client, ids):
    res = client.post("/api/transactions", json={"type": "expense", "amount": 10, "date": "2026-09-10",
                                                 "account_id": ids["checking"], "category_id": ids["salary"]})
    assert res.status_code == 400


def test_balance_adjustment_is_not_income_or_expense(client, ids):
    res = client.put(f"/api/accounts/{ids['checking']}", json={"balance": 250000, "adjustment_note": "cuadratura"})
    assert res.status_code == 200 and res.json()["balance"] == 250000
    stats = client.get("/api/stats/dashboard").json()
    assert stats["total_income"] == 0 and stats["total_expense"] == 0
    adjustments = client.get("/api/transactions", params={"type": "adjustment"}).json()
    assert len(adjustments) == 1 and adjustments[0]["amount"] == 250000
    # Adjustments cannot be edited, only deleted
    assert client.put(f"/api/transactions/{adjustments[0]['id']}", json={"amount": 1}).status_code == 400


def test_new_account_opening_balance(client):
    acc = client.post("/api/accounts", json={"name": "Ahorro", "type": "ahorro", "currency": "CLP", "balance": 1000000}).json()
    assert acc["balance"] == 1000000
    assert client.get("/api/stats/dashboard").json()["total_income"] == 0


def test_account_type_validation(client):
    base = {"name": "Visa", "currency": "CLP"}
    assert client.post("/api/accounts", json={**base, "type": "credit_card"}).status_code == 400
    acc = client.post("/api/accounts", json={**base, "type": "credit"}).json()
    assert acc["type"] == "credito"  # English alias normalized
    assert client.put(f"/api/accounts/{acc['id']}", json={"type": "tarjeta"}).status_code == 400
    assert client.put(f"/api/accounts/{acc['id']}", json={"type": "ahorro"}).json()["type"] == "ahorro"


def test_account_delete_rules(client, ids):
    assert client.delete(f"/api/accounts/{ids['cash']}").json()["archived"] is False
    create(client, account_id=ids["checking"], amount=100)
    assert client.delete(f"/api/accounts/{ids['checking']}").status_code == 400  # has balance
    client.put(f"/api/accounts/{ids['checking']}", json={"balance": 0})
    assert client.delete(f"/api/accounts/{ids['checking']}").json()["archived"] is True


def test_dashboard_counts_only_confirmed_income_and_expense(client, ids, db):
    from app.models.schemas import Transaction
    create(client, account_id=ids["checking"], amount=7000, category_id=ids["groceries"], date="2026-09-05")
    create(client, account_id=ids["checking"], type="income", amount=50000, category_id=ids["salary"], date="2026-09-06")
    create(client, type="transfer", account_id=ids["checking"], destination_account_id=ids["cash"], amount=9999, date="2026-09-07")
    db.add(Transaction(account_id=ids["checking"], type="expense", amount=1234, currency="CLP", exchange_rate=1,
                       base_amount=1234, date="2026-09-08", status="pending_review", source="email"))
    db.commit()
    stats = client.get("/api/stats/dashboard", params={"month": "2026-09"}).json()
    assert stats["total_expense"] == 7000 and stats["total_income"] == 50000
    assert stats["pending_count"] == 1
    assert stats["expense_breakdown"][0]["name"] == "Groceries & Food"


def test_review_flow_and_ignored_email(client, ids, db):
    from app.models.schemas import IgnoredEmail, Transaction
    for i, cat in enumerate([ids["groceries"], None]):
        db.add(Transaction(account_id=ids["card"], type="expense", amount=100 + i, currency="CLP", exchange_rate=1,
                           base_amount=100 + i, date="2026-09-08", status="pending_review", source="email",
                           merchant=f"Comercio {i}", category_id=cat, email_message_id=f"<m{i}@bank>"))
    db.commit()
    listed = client.get("/api/transactions", params={"status": "pending_review"}).json()
    assert {t["ai_source"] for t in listed} == {None}  # manual inserts: no classifier involved
    res = client.post("/api/transactions/confirm-all").json()
    assert res == {"confirmed": 1, "skipped": 1, "duplicates": 0}  # the one without category needs editing

    pending = client.get("/api/transactions", params={"status": "pending_review"}).json()
    assert len(pending) == 1
    assert client.delete(f"/api/transactions/{pending[0]['id']}").status_code == 200
    assert db.query(IgnoredEmail).filter(IgnoredEmail.email_message_id == "<m1@bank>").first()


def test_approving_teaches_the_classifier(client, ids, db):
    from app.models.schemas import Transaction
    tx = Transaction(account_id=ids["card"], type="expense", amount=4500, currency="CLP", exchange_rate=1,
                     base_amount=4500, date="2026-09-08", status="pending_review", source="email", merchant="LA PICADA DEL BARRIO")
    db.add(tx)
    db.commit()
    res = client.put(f"/api/transactions/{tx.id}", json={"status": "confirmed", "category_id": ids["restaurants"]})
    assert res.status_code == 200
    suggestion = client.get("/api/transactions/suggest", params={"merchant": "La Picada del Barrio"}).json()
    assert suggestion["category_id"] == ids["restaurants"] and suggestion["source"] == "memory"


def test_search_and_pagination(client, ids):
    for i in range(7):
        create(client, account_id=ids["checking"], amount=100 + i, merchant=f"Farmacia {i}", date=f"2025-0{i + 1}-15")
    create(client, account_id=ids["checking"], amount=5, merchant="Kiosko")
    found = client.get("/api/transactions", params={"search": "farmacia", "limit": 5}).json()
    assert len(found) == 5 and all("Farmacia" in t["merchant"] for t in found)
    rest = client.get("/api/transactions", params={"search": "farmacia", "limit": 5, "offset": 5}).json()
    assert len(rest) == 2


def test_merchant_is_returned_verbatim_for_the_client_to_escape(client, ids):
    evil = '<img src=x onerror="alert(1)">'
    tx = create(client, account_id=ids["checking"], merchant=evil)
    assert tx["merchant"] == evil


def test_backup_is_a_valid_sqlite_file(client):
    res = client.get("/api/system/backup")
    assert res.status_code == 200 and res.content.startswith(b"SQLite format 3")


def test_reset_data(client, ids):
    create(client, account_id=ids["checking"], amount=100)
    assert client.post("/api/system/reset-data", json={"confirm": "no"}).status_code == 400
    assert client.post("/api/system/reset-data", json={"confirm": "BORRAR"}).json()["deleted"] == 1
    assert all(v == 0 for v in balances(client).values())


def test_archived_category_still_labels_and_keeps_its_movements(client, ids):
    tx = create(client, account_id=ids["checking"], category_id=ids["groceries"])
    assert client.delete(f"/api/categories/{ids['groceries']}").json()["archived"] is True

    assert ids["groceries"] not in {c["id"] for c in client.get("/api/categories").json()}
    listed = {c["id"]: c for c in client.get("/api/categories", params={"include_archived": True}).json()}
    assert listed[ids["groceries"]]["is_active"] is False

    # Editing the note of an old movement keeps its (archived) category
    res = client.put(f"/api/transactions/{tx['id']}", json={"description": "nota", "category_id": ids["groceries"]})
    assert res.status_code == 200 and res.json()["category_id"] == ids["groceries"]


def test_category_with_movements_cannot_switch_type(client, ids):
    create(client, account_id=ids["checking"], category_id=ids["groceries"])
    assert client.put(f"/api/categories/{ids['groceries']}", json={"type": "income"}).status_code == 400
    assert client.put(f"/api/categories/{ids['restaurants']}", json={"type": "income"}).status_code == 200


def test_unsupported_currency_is_rejected(client, ids):
    assert client.post("/api/accounts", json={"name": "Libras", "type": "ahorro", "currency": "GBP"}).status_code == 400
    res = client.post("/api/transactions", json={"type": "expense", "amount": 10, "currency": "GBP", "date": "2026-09-10",
                                                 "account_id": ids["checking"], "category_id": ids["groceries"]})
    assert res.status_code == 400


def test_reference_accounts_skip_balances_and_pending_count(client, ids, db):
    from app.models.schemas import Transaction
    light = client.get("/api/accounts", params={"include_archived": True, "with_balances": False}).json()
    assert light and all(a["balance"] is None and a["balance_clp"] is None for a in light)

    db.add(Transaction(account_id=ids["card"], type="expense", amount=100, currency="CLP", exchange_rate=1,
                       base_amount=100, date="2026-09-08", status="pending_review", source="email"))
    db.commit()
    assert client.get("/api/transactions/pending-count").json() == {"count": 1}


def test_static_assets_are_revalidated(client):
    res = client.get("/static/js/app.js")
    assert res.status_code == 200 and res.headers["cache-control"] == "no-cache"


def test_movement_typed_by_hand_and_imported_from_email_is_flagged(client, ids, db):
    from app.models.schemas import Transaction
    manual = create(client, type="transfer", account_id=ids["checking"], destination_account_id=ids["card"],
                    amount=66476, date="2026-10-05", merchant="Pago TC")
    # The bank's email for the same payment, a day later; plus two identical real purchases, both from email
    email = Transaction(account_id=ids["checking"], destination_account_id=ids["card"], type="transfer", amount=66476,
                        currency="CLP", exchange_rate=1, base_amount=66476, date="2026-10-06", status="pending_review",
                        source="email", merchant="Comprobante Pago Tarjeta", email_message_id="<pago@bank>")
    db.add(email)
    for i in range(2):
        db.add(Transaction(account_id=ids["card"], type="expense", amount=815, currency="CLP", exchange_rate=1,
                           base_amount=815, date="2026-10-05", status="pending_review", source="email",
                           merchant="Metro", category_id=ids["groceries"], email_message_id=f"<metro{i}@bank>"))
    db.commit()

    listed = {t["id"]: t for t in client.get("/api/transactions", params={"month": "2026-10"}).json()}
    assert listed[email.id]["duplicate_of"]["id"] == manual["id"]
    assert listed[manual["id"]]["duplicate_of"]["id"] == email.id
    assert [t["duplicate_of"] for t in listed.values() if t["merchant"] == "Metro"] == [None, None]

    # "Approve all" leaves the possible duplicate for the user to decide
    assert client.post("/api/transactions/confirm-all").json() == {"confirmed": 2, "skipped": 0, "duplicates": 1}
    db.refresh(email)
    assert email.status == "pending_review"


def test_second_notice_of_one_bank_operation_is_recognized(db, ids):
    from app.models.schemas import Transaction
    from app.services.mail.sync import _same_operation

    tx = Transaction(account_id=ids["checking"], type="expense", amount=70000, currency="CLP", exchange_rate=1,
                     base_amount=70000, date="2026-09-29", status="confirmed", source="email",
                     bank_reference="TEF_IPE2609290000000000000001")
    legacy = Transaction(account_id=ids["checking"], type="expense", amount=5000, currency="CLP", exchange_rate=1,
                         base_amount=5000, date="2026-09-28", status="confirmed", source="email",
                         raw_text="Monto: $5.000 Transacción TEFMBCO2609280000000000000002")
    db.add_all([tx, legacy])
    db.commit()
    assert _same_operation(db, "TEF_IPE2609290000000000000001") == tx.id
    assert _same_operation(db, "TEFMBCO2609280000000000000002") == legacy.id  # imported before references were stored
    assert _same_operation(db, "TEF_IPE0000000000000000000000") is None
    assert _same_operation(db, None) is None
