"""Toshl CSV import: transfers are paired, duplicates skipped, categories mapped."""
from app.models.schemas import Account, Transaction
from app.services.balances import compute_balances
from app.services.csv_import import import_csv, parse_amount, parse_date

CSV = """Date,Account,Category,Tags,Expense amount,Income amount,Currency,In main currency,Main currency,Description
14-08-22,Cuenta Corriente,Food & Drinks,restaurants,6.990,0,CLP,6.990,CLP,Sushi
01-08-23,Cuenta Corriente,Transfer,,100.000,0,CLP,100.000,CLP,
01-08-23,Efectivo,Transfer,,0,100.000,CLP,100.000,CLP,
02-08-23,Cuenta Corriente,Salary,,0,1.500.000,CLP,1.500.000,CLP,Sueldo agosto
03-08-23,Cuenta Corriente,Mascotas,perro,25.000,0,CLP,25.000,CLP,Veterinario
"""


def test_import_pairs_transfer_legs_and_skips_duplicates(db):
    res = import_csv(db, CSV)
    assert res["imported"] == 4 and res["duplicates"] == 0 and res["categories_created"] == 1

    transfer = db.query(Transaction).filter(Transaction.type == "transfer").one()
    accounts = {a.name: a.id for a in db.query(Account).all()}
    assert (transfer.account_id, transfer.destination_account_id) == (accounts["Cuenta Corriente"], accounts["Efectivo"])

    balances = compute_balances(db)
    assert balances[accounts["Cuenta Corriente"]] == 1500000 - 6990 - 100000 - 25000
    assert balances[accounts["Efectivo"]] == 100000

    sushi = db.query(Transaction).filter(Transaction.merchant == "Sushi").one()
    assert sushi.category.name == "Restaurants & Coffee"  # Toshl "Food & Drinks" + tag "restaurants"

    again = import_csv(db, CSV)
    assert again["imported"] == 0 and again["duplicates"] == 4


def test_parsers():
    assert parse_amount("14.000.000") == 14000000
    assert parse_amount("591,11") == 591.11
    assert parse_amount("1.250,50") == 1250.5
    assert parse_date("05-09-26") == "2026-09-05"
    assert parse_date("2026/1/2") == "2026-01-02"
    assert parse_date("31-02-2026") is None


def test_unsupported_currency_is_rejected_before_importing(db):
    import pytest
    csv_gbp = CSV.replace("25.000,0,CLP", "25.000,0,GBP")
    with pytest.raises(ValueError, match="GBP"):
        import_csv(db, csv_gbp)
    assert db.query(Transaction).count() == 0
