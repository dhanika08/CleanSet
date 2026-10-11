"""
fieldmap.py - the list of facts CleanSet reads from the documents.

Every fact has an ID like "invoice.total_amount". The same IDs are used:
  * to tell Gemini what to look for in each document,
  * by the rule checks (rules.py),
  * by the verifier (verify.py) to make sure a finding only mentions facts that really were read,
  * to turn our test data (truth.json) into the same shape, so we can score the reading.

Each entry: (field_id, document_type, kind, description, path_in_truth_json)
"""
import re
from datetime import datetime

DOC_TYPES = {
    "lc": "Letter of credit (SWIFT MT700 text issued by the buyer's bank)",
    "invoice": "Commercial invoice",
    "packing_list": "Packing list",
    "bill_of_lading": "Bill of lading (the shipping line's receipt)",
    "insurance": "Marine insurance certificate",
    "certificate_of_origin": "Certificate of origin",
    "presentation": "Covering schedule / letter that lists the documents presented and the date of presentation",
}

FIELDS = [
    # ---- letter of credit ----
    ("lc.number", "lc", "str", "Documentary credit number (tag 20)", ("lc", "20_documentary_credit_number")),
    ("lc.expiry_date", "lc", "date", "Expiry date (tag 31D)", ("lc", "31D_expiry", "date")),
    ("lc.latest_shipment_date", "lc", "date", "Latest date of shipment (tag 44C)", ("lc", "44C_latest_shipment_date")),
    ("lc.amount", "lc", "num", "Credit amount, number only (tag 32B)", ("lc", "32B_currency_amount", "amount")),
    ("lc.currency", "lc", "str", "Credit currency code (tag 32B)", ("lc", "32B_currency_amount", "currency")),
    ("lc.tolerance_plus_pct", "lc", "num", "Plus tolerance percentage (tag 39A, the first number). Use 0 if none is stated", ("lc", "39A_tolerance", "plus_percent")),
    ("lc.port_of_loading", "lc", "str", "Port of loading (tag 44E)", ("lc", "44E_port_of_loading")),
    ("lc.port_of_discharge", "lc", "str", "Port of discharge (tag 44F)", ("lc", "44F_port_of_discharge")),
    ("lc.goods_description", "lc", "str", "Full description of goods (tag 45A), copied exactly", ("lc", "45A_goods_description")),
    ("lc.applicant_name", "lc", "str", "Applicant (the buyer) company name (tag 50)", ("lc", "50_applicant", "name")),
    ("lc.applicant_address", "lc", "str", "Applicant address (tag 50)", ("lc", "50_applicant", "address")),
    ("lc.beneficiary_name", "lc", "str", "Beneficiary (the exporter) company name (tag 59)", ("lc", "59_beneficiary", "name")),
    ("lc.presentation_days", "lc", "num", "Number of days after shipment allowed for presenting documents (tag 48)", ("lc", "48_presentation_period_days")),
    # ---- commercial invoice ----
    ("invoice.lc_number", "invoice", "str", "Documentary credit number quoted on the invoice", ("invoice", "lc_number")),
    ("invoice.date", "invoice", "date", "Invoice date", ("invoice", "invoice_date")),
    ("invoice.issued_by_name", "invoice", "str", "Name of the company that issued the invoice (the seller)", ("invoice", "issued_by", "name")),
    ("invoice.made_out_to_name", "invoice", "str", "Name of the company the invoice is made out to (the buyer)", ("invoice", "made_out_to", "name")),
    ("invoice.goods_description", "invoice", "str", "Description of goods, copied exactly", ("invoice", "goods_description")),
    ("invoice.quantity", "invoice", "num", "Quantity of pieces, number only", ("invoice", "quantity")),
    ("invoice.unit_price", "invoice", "num", "Unit price, number only", ("invoice", "unit_price")),
    ("invoice.total_amount", "invoice", "num", "Total invoice amount, number only", ("invoice", "total_amount")),
    ("invoice.currency", "invoice", "str", "Invoice currency code", ("invoice", "currency")),
    # ---- packing list ----
    ("packing_list.lc_number", "packing_list", "str", "Documentary credit number quoted on the packing list", ("packing_list", "lc_number")),
    ("packing_list.total_cartons", "packing_list", "num", "Total number of cartons", ("packing_list", "total_cartons")),
    ("packing_list.total_pieces", "packing_list", "num", "Total number of pieces", ("packing_list", "total_pieces")),
    ("packing_list.gross_weight_kg", "packing_list", "num", "Gross weight in kg, number only", ("packing_list", "gross_weight_kg")),
    ("packing_list.volume_cbm", "packing_list", "num", "Volume in cubic metres, number only", ("packing_list", "volume_cbm")),
    ("packing_list.consignee_address", "packing_list", "str", "Consignee address", ("packing_list", "consignee", "address")),
    # ---- bill of lading ----
    ("bill_of_lading.lc_number", "bill_of_lading", "str", "Documentary credit number quoted on the bill of lading", ("bill_of_lading", "lc_number")),
    ("bill_of_lading.port_of_loading", "bill_of_lading", "str", "Port of loading", ("bill_of_lading", "port_of_loading")),
    ("bill_of_lading.port_of_discharge", "bill_of_lading", "str", "Port of discharge", ("bill_of_lading", "port_of_discharge")),
    ("bill_of_lading.shipped_on_board_date", "bill_of_lading", "date", "Shipped on board date", ("bill_of_lading", "shipped_on_board_date")),
    ("bill_of_lading.gross_weight_kg", "bill_of_lading", "num", "Gross weight in kg, number only", ("bill_of_lading", "gross_weight_kg")),
    ("bill_of_lading.measurement_cbm", "bill_of_lading", "num", "Measurement in cubic metres, number only", ("bill_of_lading", "measurement_cbm")),
    ("bill_of_lading.number_of_packages", "bill_of_lading", "num", "Number of packages", ("bill_of_lading", "number_of_packages")),
    ("bill_of_lading.goods_description", "bill_of_lading", "str", "Description of goods, copied exactly", ("bill_of_lading", "goods_description")),
    ("bill_of_lading.clean_on_board", "bill_of_lading", "bool", "true if the bill of lading is clean, meaning it has NO clause saying the goods or packaging are damaged or defective; false if it has such a clause", ("bill_of_lading", "clean_on_board")),
    # ---- insurance ----
    ("insurance.lc_number", "insurance", "str", "Documentary credit number quoted on the insurance certificate", ("insurance", "lc_number")),
    ("insurance.insured_amount", "insurance", "num", "Sum insured, number only", ("insurance", "insured_amount")),
    ("insurance.cif_invoice_value", "insurance", "num", "CIF invoice value, number only", ("insurance", "cif_invoice_value")),
    ("insurance.currency", "insurance", "str", "Currency code of the insurance amount", ("insurance", "currency")),
    ("insurance.effective_from", "insurance", "date", "Date the insurance cover starts", ("insurance", "effective_from")),
    # ---- certificate of origin ----
    ("certificate_of_origin.lc_number", "certificate_of_origin", "str", "Documentary credit number quoted on the certificate", ("certificate_of_origin", "lc_number")),
    ("certificate_of_origin.country_of_origin", "certificate_of_origin", "str", "Country of origin", ("certificate_of_origin", "country_of_origin")),
    # ---- presentation ----
    ("presentation.date", "presentation", "date", "Date of presentation to the bank", ("presentation", "presentation_date")),
]

FIELD_INDEX = {f[0]: f for f in FIELDS}


def fields_for(doc_type):
    return [f for f in FIELDS if f[1] == doc_type]


# ---------------------------------------------------------------------------
# Cleaning values that come back from Gemini
# ---------------------------------------------------------------------------
_DATE_FORMATS = ["%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%d-%b-%Y", "%d.%m.%Y"]


def coerce(kind, value):
    """Turn a raw value into a clean str / float / ISO date / bool. Returns None if it cannot."""
    if value is None:
        return None
    if kind == "str":
        s = " ".join(str(value).split())
        return s or None
    if kind == "num":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        m = re.search(r"-?\d[\d,]*\.?\d*", str(value))
        return float(m.group(0).replace(",", "")) if m else None
    if kind == "date":
        s = str(value).strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                pass
        return None
    if kind == "bool":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("true", "yes", "clean", "1"):
            return True
        if s in ("false", "no", "unclean", "0"):
            return False
        return None
    return value


def truth_to_fields(truth):
    """Turn a truth.json dict into the same {field_id: {"value", "source"}} shape the reader produces."""
    out = {}
    for fid, doc, kind, desc, path in FIELDS:
        node = truth
        try:
            for key in path:
                node = node[key]
        except (KeyError, TypeError):
            continue
        out[fid] = {"value": coerce(kind, node), "source": "(from truth data)"}
    return out
