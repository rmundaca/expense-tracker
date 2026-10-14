"""Bank email parsing (synthetic emails modeled on real Chilean bank notifications)."""
from app.services.bank_parsers.base import detect_account_hint, parse_chilean_amount, parse_chilean_date
from app.services.bank_parsers.registry import parser_registry
from app.services.mail.sync import email_local_datetime, resolve_account

BCHILE_CARD = """Estimado cliente:
Te informamos que se ha realizado una compra por $22.347 con Tarjeta de Crédito ****1234 en UNIMARC CENTRO el 16/09/2026 19:46.
Revisa tus movimientos en la App Mi Banco."""

GENERIC_TABLE = """Comprobante de pago
Monto: $ 45.990
Comercio: FARMACIA CRUZ VERDE
Fecha: 03/09/2026 10:15
Cuenta corriente N° 12.345.678"""


def test_bchile_card_purchase():
    p = parser_registry.parse_email("Banco de Chile <enviodigital@bancochile.cl>", "Compra con Tarjeta de Crédito", BCHILE_CARD, "")
    assert (p.amount, p.currency, p.merchant) == (22347, "CLP", "UNIMARC CENTRO")
    assert p.date == "2026-09-16 19:46:00" and p.account_hint == "credito"


def test_generic_parser_reads_labelled_tables():
    p = parser_registry.parse_email("notificaciones@santander.cl", "Comprobante de pago", GENERIC_TABLE, "")
    assert p.amount == 45990 and p.merchant == "FARMACIA CRUZ VERDE"
    assert p.date == "2026-09-03 10:15:00" and p.account_hint == "corriente"


def test_generic_parser_without_merchant_label_uses_subject():
    # Used to crash with NameError('sender') or pick garbage after any word containing "en"
    p = parser_registry.parse_email("x@itau.cl", "Aviso de cargo", "Estimado cliente, se registró un cargo por $ 5.000", "")
    assert p.amount == 5000 and p.merchant == "Aviso de cargo"


def test_missing_date_falls_back_to_email_header():
    p = parser_registry.parse_email("x@bci.cl", "Compra", "Compra por $ 1.500 en KIOSKO", "", fallback_date="2026-08-30 08:00:00")
    assert p.date == "2026-08-30 08:00:00"


def test_security_emails_are_ignored():
    assert parser_registry.parse_email("x@bancochile.cl", "Aviso de seguridad", "Se inició sesión desde un dispositivo nuevo", "") is None


def test_amounts_and_dates():
    assert parse_chilean_amount("Total: US$ 4,57") == 4.57
    assert parse_chilean_amount("Cuenta N° 123.456.789 monto $ 12.000") == 12000
    assert parse_chilean_date("31/02/2026") is None  # invalid date is not invented
    assert parse_chilean_date("5 de septiembre de 2026") == "2026-09-05"


def test_account_hint_is_not_fooled_by_substrings():
    assert detect_account_hint("Gastos comunes, luz, etc.") is None  # "tc" inside "etc" used to mean credit card
    assert detect_account_hint("Compra con TC Visa") == "credito"
    assert detect_account_hint("abono en Cuenta RUT") == "vista"


def test_email_date_header():
    assert email_local_datetime("not a date") is None
    assert email_local_datetime("Tue, 16 Sep 2026 19:46:00 -0300")[:10] in ("2026-09-16", "2026-09-17")


class Acc:
    def __init__(self, id, currency, type):
        self.id, self.currency, self.type = id, currency, type


class Bank:
    def __init__(self, default):
        self.default_account_id = default


def test_resolve_account_prefers_currency_then_type_then_bank_default():
    accounts = [Acc(1, "CLP", "corriente"), Acc(2, "CLP", "credito"), Acc(3, "USD", "credit")]
    assert resolve_account(accounts, "USD", "credito", Bank(1)) == 3
    assert resolve_account(accounts, "CLP", "credito", Bank(1)) == 2
    assert resolve_account(accounts, "CLP", None, Bank(2)) == 2
    assert resolve_account(accounts, "EUR", None, Bank(1)) == 1  # no EUR account: bank default


def test_amount_is_not_taken_from_cards_ruts_or_words_containing_keywords():
    # The number after "por ... Tarjeta", a RUT, or "transPORte" is not the amount
    assert parse_chilean_amount("Gracias por usar su Tarjeta ****1234. Monto $45.990") == 45990
    assert parse_chilean_amount("Gracias por preferirnos, cliente 12.345.678-9. Total $5.000") == 5000
    assert parse_chilean_amount("Transporte 2 personas $12.000") == 12000
    assert parse_chilean_amount("Abono en cuenta N° 123 por $10.000") == 10000
    assert parse_chilean_amount("Su compra en JUMBO por $ 23.450 fue aprobada") == 23450


def test_imap_search_bounds_unread_emails():
    from app.services.mail import sources

    class FakeMail:
        def __init__(self):
            self.criteria = []

        def search(self, _charset, criteria):
            self.criteria.append(criteria)
            return "OK", [b""]

    mail = FakeMail()
    sources._search_message_numbers(mail, ["a@banco.cl"], 7)
    assert mail.criteria[0] == f'(SINCE "{sources._imap_since(7)}" FROM "a@banco.cl")'
    assert mail.criteria[1] == f'(UNSEEN SINCE "{sources._imap_since(sources.UNSEEN_MAX_DAYS)}" FROM "a@banco.cl")'


BCHILE_RECEIVED = """Estimado(a) María González
Le informamos que Pedro Pablo Rojas Vera le ha transferido $70.000 , el día 29 de septiembre de 2026.
Datos de la Transferencia
Rut: 11.111.111-1
Cuenta: 001234567
Fecha: 29/09/2026
Monto: $70.000
ID: TEF_IPE2609290000000000000001"""

BCHILE_USD_CARD_PAYMENT = """Te informamos que se ha efectuado el pago de la tarjeta de crédito internacional en forma exitosa
Tipo de tarjeta: Tarjeta de Crédito
N° de tarjeta: ************4321
Utilizado: USD$243,00
Detalle
Monto pagado: USD$136,10
Tipo de cambio: $985
Monto: $134.106
Fecha y Hora: lunes 28 de septiembre de 2026 21:38
Transacción: INTERNET_P2026092800000000003"""

BCHILE_BILLS = """Comprobante de pago de cuentas
Detalle cuenta(s) pagada(s)
Empresa: Gas Sur
ID: 0900000005
Monto: $67.987
Empresa: CGE
ID: 8000006
Monto: $21.000
Detalle del pago
Medio de pago: Cuenta Corriente ****9876
Total: $88.987
Código de autorización EXP0099020260920000004
Fecha y Hora miércoles 30 de septiembre de 2026 19:06"""


def test_bchile_incoming_transfer_is_income_from_its_sender():
    p = parser_registry.parse_email("serviciodetransferencias@bancochile.cl", "Transferencias de Fondos de Pedro Pablo Rojas Vera",
                                    BCHILE_RECEIVED, "")
    assert (p.tx_type, p.amount, p.merchant) == ("income", 70000, "Pedro Pablo Rojas Vera")
    assert p.reference == "TEF_IPE2609290000000000000001"


def test_bchile_dollar_card_payment_keeps_the_pesos_charged():
    p = parser_registry.parse_email("serviciodetransferencias@bancochile.cl", "Pago de Tarjeta de Crédito Internacional",
                                    BCHILE_USD_CARD_PAYMENT, "")
    assert (p.amount, p.currency, p.clp_amount) == (136.10, "USD", 134106)  # not the 243 "utilizado"
    assert p.reference == "INTERNET_P2026092800000000003"
    assert p.merchant == "Pago de Tarjeta de Crédito Internacional"  # not a generic "Banco de Chile"


def test_bchile_payment_of_several_bills_takes_the_total():
    p = parser_registry.parse_email("serviciodetransferencias@bancochile.cl", "Comprobante de Pago Cuentas", BCHILE_BILLS, "")
    assert p.amount == 88987
    # The bill's customer number repeats every month: it is not the operation id
    assert p.reference == "EXP0099020260920000004"


def test_bank_reference_needs_a_real_id():
    from app.services.bank_parsers.base import extract_bank_reference
    assert extract_bank_reference("Monto Pagado: $88.403 ID: 00") is None
    assert extract_bank_reference("Empresa: Gas Sur ID: 0900000005") is None
    assert extract_bank_reference("Transacción exitosa") is None
    assert extract_bank_reference("ID de transacción 8200000007") == "8200000007"
