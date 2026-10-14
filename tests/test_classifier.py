"""Rules (whole-word matching) and the classifier's memory / Naive Bayes fallback."""
from app.models.schemas import RuleMapping, Transaction
from app.services.classifier import classifier_service, tokenize
from app.services.rules_engine import evaluate_boolean_pattern


def test_rules_match_whole_words_only():
    assert evaluate_boolean_pattern("sueldo OR bono", "Pago bono anual")
    assert not evaluate_boolean_pattern("sueldo OR bono", "Abono en cuenta corriente")
    assert not evaluate_boolean_pattern("curso", "Pago recursos humanos")
    assert evaluate_boolean_pattern("c. verde", "Farmacia C. Verde Providencia")
    assert evaluate_boolean_pattern("apple.com", "APPLE.COM/BILL")


def test_boolean_operators_and_groups():
    assert evaluate_boolean_pattern("uber AND eats", "UBER EATS SANTIAGO")
    assert not evaluate_boolean_pattern("uber AND eats", "UBER TRIP")
    assert evaluate_boolean_pattern("(jumbo OR lider) AND express", "Lider Express Ñuñoa")
    assert evaluate_boolean_pattern('"santa isabel"', "SANTA ISABEL MACUL")


def test_rule_with_income_category_suggests_income(db, ids):
    # Older rules were stored as "expense" even when pointing to an income category
    db.add(RuleMapping(name="Sueldo", pattern="remuneracion", match_field="any",
                       category_id=ids["salary"], tx_type="expense", priority=50))
    db.commit()
    res = classifier_service.classify(db, merchant="REMUNERACION SEPTIEMBRE")
    assert res.source == "rule" and res.category_id == ids["salary"] and res.tx_type == "income"


def test_memory_recalls_last_choice_for_a_merchant(db, ids):
    classifier_service.learn(db, "CAFE ALTO", None, category_id=ids["groceries"], account_id=ids["card"], tx_type="expense")
    classifier_service.learn(db, "Café Alto", None, category_id=ids["restaurants"], account_id=ids["cash"], tx_type="expense")
    db.commit()
    res = classifier_service.classify(db, merchant="cafe alto")
    assert (res.source, res.category_id, res.account_id) == ("memory", ids["restaurants"], ids["cash"])


def test_transfer_memory_keeps_destination(db, ids):
    classifier_service.learn(db, "Traspaso a ahorro", None, category_id=None, account_id=ids["checking"],
                             tx_type="transfer", destination_account_id=ids["cash"])
    db.commit()
    res = classifier_service.classify(db, merchant="Traspaso a ahorro")
    assert res.tx_type == "transfer" and res.destination_account_id == ids["cash"]


def test_naive_bayes_generalizes_by_words(db, ids):
    for name in ("Pizzeria Napoli Centro", "Pizzeria Roma", "Pizzeria Il Forno"):
        classifier_service.learn(db, name, None, category_id=ids["restaurants"], account_id=None, tx_type="expense")
    for name in ("Ferreteria Central", "Ferreteria Sur"):
        classifier_service.learn(db, name, None, category_id=ids["groceries"], account_id=None, tx_type="expense")
    db.commit()
    res = classifier_service.classify(db, merchant="Pizzeria Nueva")
    assert res.source == "ml" and res.category_id == ids["restaurants"]


def test_nothing_learned_returns_none(db):
    assert classifier_service.classify(db, merchant="zzzz qqqq").source == "none"


def test_tokenize_drops_stop_words():
    assert tokenize("Pago con tarjeta en JUMBO") == ["jumbo"]


def test_rule_never_suggests_an_archived_category(client, db, ids):
    db.add(RuleMapping(name="Jumbo", pattern="jumbo", match_field="any",
                       category_id=ids["groceries"], tx_type="expense", priority=50))
    db.add(Transaction(account_id=ids["checking"], type="expense", amount=100, currency="CLP", exchange_rate=1,
                       base_amount=100, date="2026-09-08", category_id=ids["groceries"], merchant="Jumbo"))
    db.commit()
    assert client.delete(f"/api/categories/{ids['groceries']}").json()["archived"] is True
    res = classifier_service.classify(db, merchant="JUMBO BILBAO")
    assert res.source == "rule" and res.category_id is None and res.tx_type == "expense"
