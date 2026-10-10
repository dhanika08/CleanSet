"""
make_gold.py - builds the DEMO set and the 30-case GOLD set, with answer keys.

Why this design: we never write errors by hand. Each error is a small function
(a "mutation") that changes ONE thing in the truth data and, in the same breath,
records what a bank checker should find. So the answer key can never disagree
with the documents.

Run:   python3 make_gold.py            (makes everything, with PDFs if Chrome is found)
       python3 make_gold.py --no-pdf   (HTML only, faster)

Output:
    data/truth/demo.json                     the demo deal (4 errors + 2 harmless variations)
    data/demo/demo_answer_key.json
    data/demo/planted/                       the demo documents
    data/gold/<CASE_ID>/truth.json
    data/gold/<CASE_ID>/answer_key.json
    data/gold/<CASE_ID>/docs/                the case documents
    data/gold/index.json                     list of all 30 cases

Rule IDs (CHK-xx) are the ones in rules.md (rulebook v1).
"""
import argparse
import copy
import json
import os
from datetime import date, timedelta

from render import render_case

BASE_PATH = "data/truth/base.json"


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def d(s):
    return date.fromisoformat(s)


def shift(iso, days):
    """Return an ISO date string moved by +/- days."""
    return (d(iso) + timedelta(days=days)).isoformat()


def split_sizes(cartons):
    """Split cartons into S/M/L/XL at roughly 15/30/35/20 percent. Always adds up exactly."""
    s = round(cartons * 0.15)
    m = round(cartons * 0.30)
    xl = round(cartons * 0.20)
    l = cartons - s - m - xl
    return [("S", s), ("M", m), ("L", l), ("XL", xl)]


def desc(qty, item, style, pi, price, city, about=False):
    return "%s%s PCS %s, STYLE NO. %s, AS PER PROFORMA INVOICE NO. %s, USD %.2f PER PIECE CIF %s INCOTERMS 2020" % (
        "ABOUT " if about else "", "{:,}".format(qty), item, style, pi, price, city)


# ----------------------------------------------------------------------------
# Build a fully COMPLIANT deal from the base file, with chosen variations
# ----------------------------------------------------------------------------
BUYER_NORDIC = dict(name="Nordic Textiles GmbH", address="Speicherstrasse 14, 20457 Hamburg, Germany",
                    bank="Hanseatic Commerzbank AG", bank_address="Ballindamm 22, 20095 Hamburg, Germany")
BUYER_BALTIC = dict(name="Baltic Apparel Oy", address="Satamakatu 9, 00160 Helsinki, Finland",
                    bank="Nordlund Pankki Oyj", bank_address="Aleksanterinkatu 30, 00100 Helsinki, Finland")


def build_truth(base, case_id, qty=5000, price=10.0, item="MEN'S 100% COTTON POLO SHIRTS",
                style="NTX-P210", pi="PI-2026-118", buyer=None,
                load_port="TUTICORIN, INDIA", load_city="TUTICORIN",
                dest_port="HAMBURG, GERMANY", dest_city="HAMBURG",
                ship="2026-11-10", latest="2026-11-15", present_after=8, expiry="2026-12-15",
                ins_pct=110, lc_about=False, ship_qty=None, lc_no="LC-NTX-2026-0457"):
    """Return a truth dict for a deal that obeys every rule."""
    buyer = buyer or BUYER_NORDIC
    text = json.dumps(base)
    # 1. swap names, places and the LC number everywhere they appear (longest strings first)
    swaps = [
        ("Speicherstrasse 14, 20457 Hamburg, Germany", buyer["address"]),
        ("Ballindamm 22, 20095 Hamburg, Germany", buyer["bank_address"]),
        ("Nordic Textiles GmbH", buyer["name"]),
        ("HANSEATIC COMMERZBANK AG", buyer["bank"].upper()),
        ("Hanseatic Commerzbank AG", buyer["bank"]),
        ("TUTICORIN, INDIA", load_port),
        ("HAMBURG, GERMANY", dest_port),
        ("TUTICORIN", load_city),
        ("HAMBURG", dest_city),
        ("LC-NTX-2026-0457", lc_no),
    ]
    for old, new in swaps:
        text = text.replace(old, new)
    t = json.loads(text)
    t["_meta"]["deal_id"] = case_id

    sq = ship_qty or qty                       # quantity actually shipped
    total = round(sq * price, 2)
    lc = t["lc"]

    # 2. the letter of credit
    lc["31C_date_of_issue"] = "2026-09-15"
    lc["31D_expiry"]["date"] = expiry
    lc["44C_latest_shipment_date"] = latest
    lc["32B_currency_amount"]["amount"] = round(qty * price, 2)
    lc["45A_goods_description"] = desc(qty, item, style, pi, price, dest_city, about=lc_about)

    # 3. invoice
    inv = t["invoice"]
    inv["invoice_date"] = shift(ship, -2)
    inv["quantity"] = sq
    inv["unit_price"] = price
    inv["total_amount"] = total
    inv["goods_description"] = desc(sq, item, style, pi, price, dest_city)
    inv["incoterm"] = "CIF " + dest_city
    inv["shipment_from"] = lc["44E_port_of_loading"]
    inv["shipment_to"] = lc["44F_port_of_discharge"]

    # 4. packing list (cartons of 50 pieces)
    pl = t["packing_list"]
    cartons = sq // 50
    sizes = split_sizes(cartons)
    pl["packing_list_date"] = shift(ship, -2)
    pl["goods_description"] = "%s PCS %s, STYLE NO. %s" % ("{:,}".format(sq), item, style)
    pl["size_breakdown"] = [{"size": s, "pieces": c * 50, "cartons": c} for s, c in sizes]
    pl["total_pieces"] = sq
    pl["total_cartons"] = cartons
    pl["shipping_marks"] = "NTX / %s / CTN 1-%d / %s" % (dest_city, cartons, lc_no)
    pl["net_weight_kg"] = round(sq * 0.22, 1)
    pl["gross_weight_kg"] = round(sq * 0.236, 1)
    pl["volume_cbm"] = round(cartons * 0.072, 2)

    # 5. bill of lading
    bl = t["bill_of_lading"]
    bl["number_of_packages"] = cartons
    bl["marks_and_numbers"] = pl["shipping_marks"]
    bl["goods_description"] = pl["goods_description"]
    bl["gross_weight_kg"] = pl["gross_weight_kg"]
    bl["measurement_cbm"] = pl["volume_cbm"]
    bl["shipped_on_board_date"] = ship
    bl["date_of_issue"] = ship

    # 6. insurance (effective the day before shipment)
    ins = t["insurance"]
    ins["cif_invoice_value"] = total
    ins["insured_amount"] = round(total * ins_pct / 100, 2)
    ins["insured_percentage"] = ins_pct
    ins["date_of_issue"] = shift(ship, -1)
    ins["effective_from"] = shift(ship, -1)
    ins["goods_description"] = "%s PCS %s" % ("{:,}".format(sq), item)

    # 7. certificate of origin
    co = t["certificate_of_origin"]
    co["date_of_issue"] = shift(ship, -3)
    co["goods_description"] = ins["goods_description"]

    # 8. presentation
    t["presentation"]["presentation_date"] = shift(ship, present_after)
    return t


# ----------------------------------------------------------------------------
# Mutations: each one plants ONE problem and returns what a checker should report.
# A finding is {"rule_id", "field", "related_fields", "description"}.
# ----------------------------------------------------------------------------
def finding(rule, field, related, text):
    return {"rule_id": rule, "field": field, "related_fields": related, "description": text}


def m_late_shipment(t):                                   # CHK-02
    ship = "2026-11-18"                                   # LC latest date is 15 Nov
    t["bill_of_lading"]["shipped_on_board_date"] = ship
    t["bill_of_lading"]["date_of_issue"] = ship
    t["presentation"]["presentation_date"] = shift(ship, 7)
    t["insurance"]["effective_from"] = shift(ship, -1)
    t["insurance"]["date_of_issue"] = shift(ship, -1)
    return [finding("CHK-02", "bill_of_lading.shipped_on_board_date", ["lc.44C_latest_shipment_date"],
                    "Goods were shipped on 18 Nov 2026, after the latest shipment date of 15 Nov 2026.")]


def m_invoice_over_amount(t):                             # CHK-04 (+ CHK-05, see note)
    price = 10.60
    q = t["invoice"]["quantity"]
    t["invoice"]["unit_price"] = price
    t["invoice"]["total_amount"] = round(q * price, 2)
    t["invoice"]["goods_description"] = t["invoice"]["goods_description"].replace("USD 10.00", "USD 10.60")
    t["insurance"]["cif_invoice_value"] = t["invoice"]["total_amount"]
    t["insurance"]["insured_amount"] = round(t["invoice"]["total_amount"] * 1.10, 2)
    return [
        finding("CHK-04", "invoice.total_amount", ["lc.32B_currency_amount"],
                "Invoice total USD 53,000.00 exceeds the credit amount of USD 50,000.00 (unit price 10.60 instead of 10.00)."),
        finding("CHK-05", "invoice.goods_description", ["lc.45A_goods_description"],
                "Invoice states USD 10.60 per piece, but the credit describes the goods at USD 10.00 per piece."),
    ]


def m_wrong_loading_port(t):                              # CHK-08
    t["bill_of_lading"]["port_of_loading"] = "CHENNAI, INDIA"
    return [finding("CHK-08", "bill_of_lading.port_of_loading", ["lc.44E_port_of_loading"],
                    "Bill of lading shows port of loading Chennai, but the credit requires Tuticorin.")]


def m_wrong_discharge_port(t):                            # CHK-09
    t["bill_of_lading"]["port_of_discharge"] = "ROTTERDAM, NETHERLANDS"
    return [finding("CHK-09", "bill_of_lading.port_of_discharge", ["lc.44F_port_of_discharge"],
                    "Bill of lading shows port of discharge Rotterdam, but the credit requires Hamburg.")]


def m_late_presentation(t):                               # CHK-03
    ship = t["bill_of_lading"]["shipped_on_board_date"]
    t["presentation"]["presentation_date"] = shift(ship, 22)     # limit is 21 days
    return [finding("CHK-03", "presentation.presentation_date", ["bill_of_lading.shipped_on_board_date", "lc.48_presentation_period_days"],
                    "Documents were presented 22 days after shipment; the credit allows 21 days.")]


def m_insurance_100(t):                                   # CHK-11
    t["insurance"]["insured_amount"] = t["insurance"]["cif_invoice_value"]
    t["insurance"]["insured_percentage"] = 100
    return [finding("CHK-11", "insurance.insured_amount", ["insurance.cif_invoice_value", "lc.46A_documents_required"],
                    "Insurance covers 100% of the CIF value; the credit requires at least 110%.")]


def m_insurance_after_shipment(t):                        # CHK-12
    ship = t["bill_of_lading"]["shipped_on_board_date"]
    t["insurance"]["effective_from"] = shift(ship, 2)
    t["insurance"]["date_of_issue"] = shift(ship, 2)
    return [finding("CHK-12", "insurance.effective_from", ["bill_of_lading.shipped_on_board_date"],
                    "Insurance cover starts after the goods were shipped.")]


def m_weight_conflict(t):                                 # CHK-14
    t["bill_of_lading"]["gross_weight_kg"] = 1108.0       # packing list says 1,180.0 (digits swapped)
    return [finding("CHK-14", "bill_of_lading.gross_weight_kg", ["packing_list.gross_weight_kg"],
                    "Gross weight conflicts: packing list 1,180.0 kg, bill of lading 1,108.0 kg.")]


def m_wrong_buyer(t):                                     # CHK-06
    t["invoice"]["made_out_to"] = {"name": "Nordic Trading GmbH", "address": t["invoice"]["made_out_to"]["address"]}
    return [finding("CHK-06", "invoice.made_out_to", ["lc.50_applicant"],
                    "Invoice is made out to Nordic Trading GmbH, but the applicant in the credit is Nordic Textiles GmbH.")]


def m_lc_expired(t):                                      # CHK-01
    t["lc"]["31D_expiry"]["date"] = "2026-11-16"          # presentation is 18 Nov
    return [finding("CHK-01", "presentation.presentation_date", ["lc.31D_expiry"],
                    "Documents were presented on 18 Nov 2026, after the credit expired on 16 Nov 2026.")]


# ---- harmless variations: look odd, are acceptable. Each returns "accepted" notes. ----
def a_cotton_garments(t):                                 # CHK-18
    t["bill_of_lading"]["goods_description"] = "COTTON GARMENTS"
    return [{"rule_id": "CHK-18", "note": "Bill of lading describes the goods generally as 'cotton garments'. This does not conflict with the invoice or credit (UCP 600 Art. 14(e))."}]


def a_address_abbreviation(t):                            # CHK-20
    addr = t["packing_list"]["consignee"]["address"]
    t["packing_list"]["consignee"]["address"] = addr.replace("strasse", "str.")
    return [{"rule_id": "CHK-20", "note": "Packing list abbreviates 'Speicherstrasse' to 'Speicherstr.'. Address detail need not be identical (UCP 600 Art. 14(j))."}]


def a_insurance_112(t):                                   # CHK-11
    t["insurance"]["insured_amount"] = round(t["insurance"]["cif_invoice_value"] * 1.12, 2)
    t["insurance"]["insured_percentage"] = 112
    return [{"rule_id": "CHK-11", "note": "Insurance covers 112% of CIF value. More than the 110% minimum is acceptable."}]


def a_date_formats(t):                                    # formatting only
    t["_render"] = {"date_formats": {"invoice": "%B %d, %Y", "packing_list": "%d/%m/%Y",
                                     "bill_of_lading": "%d-%b-%Y", "insurance": "%Y-%m-%d"}}
    return [{"rule_id": "CHK-20", "note": "Documents use different date formats (for example 'November 08, 2026' and '08/11/2026'). The dates are the same; formatting is not a discrepancy."}]


# ----------------------------------------------------------------------------
# Case definitions
# ----------------------------------------------------------------------------
def make_cases(base):
    cases = []

    def add(case_id, group, truth, findings=None, accepted=None, note=""):
        cases.append({"case_id": case_id, "group": group, "truth": truth,
                      "findings": findings or [], "accepted": accepted or [], "note": note})

    # ---- C: six compliant sets ----
    add("C01", "clean", build_truth(base, "C01"), note="The base deal, fully compliant.")
    add("C02", "clean", build_truth(base, "C02", qty=8000, price=9.50, dest_port="ROTTERDAM, NETHERLANDS",
                                    dest_city="ROTTERDAM", lc_no="LC-NTX-2026-0462", ship="2026-11-05", present_after=9),
        note="Larger order, different price and destination.")
    add("C03", "clean", build_truth(base, "C03", qty=3000, price=7.80, item="WOMEN'S 100% COTTON T-SHIRTS",
                                    style="NTX-T118", pi="PI-2026-131", lc_no="LC-NTX-2026-0470", ship="2026-11-05", present_after=7),
        note="Different goods.")
    add("C04", "clean", build_truth(base, "C04", qty=6000, price=11.25, buyer=BUYER_BALTIC, load_port="CHENNAI, INDIA",
                                    load_city="CHENNAI", dest_port="HELSINKI, FINLAND", dest_city="HELSINKI",
                                    lc_no="LC-BAO-2026-0211", ship="2026-11-12", latest="2026-11-20", present_after=10, expiry="2026-12-20"),
        note="Different buyer, bank and ports.")
    add("C05", "clean", build_truth(base, "C05", lc_no="LC-NTX-2026-0480", ship="2026-11-15", present_after=21, expiry="2026-12-15"),
        note="Boundary: shipped on the latest allowed day and presented on day 21. Still compliant.")
    add("C06", "clean", build_truth(base, "C06", lc_no="LC-NTX-2026-0485", ins_pct=120),
        note="Insurance at 120%, above the 110% minimum.")

    # ---- E: ten single-root-cause errors ----
    singles = [
        ("E01", m_late_shipment, "Shipped after the latest shipment date."),
        ("E02", m_invoice_over_amount, "Invoice price too high, so the total exceeds the credit."),
        ("E03", m_wrong_loading_port, "Wrong port of loading on the bill of lading."),
        ("E04", m_wrong_discharge_port, "Wrong port of discharge on the bill of lading."),
        ("E05", m_late_presentation, "Presented 22 days after shipment."),
        ("E06", m_insurance_100, "Insurance at 100% instead of 110%."),
        ("E07", m_insurance_after_shipment, "Insurance starts after shipment."),
        ("E08", m_weight_conflict, "Gross weight differs between packing list and bill of lading."),
        ("E09", m_wrong_buyer, "Invoice made out to the wrong company."),
        ("E10", m_lc_expired, "Credit had expired at presentation."),
    ]
    for i, (cid, fn, note) in enumerate(singles):
        t = build_truth(base, cid, lc_no="LC-NTX-2026-%04d" % (500 + i))
        add(cid, "single_error", t, findings=fn(t), note=note)

    # ---- M: eight multi-error cases ----
    multis = [
        ("M01", [m_wrong_loading_port, m_insurance_100]),
        ("M02", [m_late_shipment, m_late_presentation]),
        ("M03", [m_weight_conflict, m_wrong_buyer]),
        ("M04", [m_wrong_discharge_port, m_insurance_after_shipment, m_weight_conflict]),
        ("M05", [m_invoice_over_amount, m_wrong_loading_port]),
        ("M06", [m_insurance_100, m_insurance_after_shipment]),
        ("M07", [m_late_shipment, m_insurance_100, m_wrong_buyer]),
        ("M08", [m_wrong_loading_port, m_wrong_discharge_port, m_late_presentation]),
    ]
    for i, (cid, fns) in enumerate(multis):
        t = build_truth(base, cid, lc_no="LC-NTX-2026-%04d" % (600 + i))
        found = []
        for fn in fns:
            found += fn(t)
        add(cid, "multi_error", t, findings=found, note="Combination of %d problems." % len(fns))

    # ---- N: six near-misses (look wrong, are fine) ----
    t = build_truth(base, "N01", lc_no="LC-NTX-2026-0700")
    add("N01", "near_miss", t, accepted=a_cotton_garments(t), note="'Cotton garments' on the bill of lading.")

    t = build_truth(base, "N02", lc_no="LC-NTX-2026-0701", lc_about=True, ship_qty=4800)
    add("N02", "near_miss", t, accepted=[
        {"rule_id": "CHK-04", "note": "Invoice total USD 48,000 is below the credit amount. Under the amount is acceptable."},
        {"rule_id": "CHK-05", "note": "Credit says 'ABOUT 5,000 PCS'. Shipping 4,800 (4% under) is within the 10% allowed for 'about' (UCP 600 Art. 30(a))."}],
        note="'About' quantity, shipped 4% under.")

    t = build_truth(base, "N03", lc_no="LC-NTX-2026-0702")
    add("N03", "near_miss", t, accepted=a_insurance_112(t), note="Insurance at 112%.")

    t = build_truth(base, "N04", lc_no="LC-NTX-2026-0703")
    add("N04", "near_miss", t, accepted=a_address_abbreviation(t), note="Abbreviated street name.")

    t = build_truth(base, "N05", lc_no="LC-NTX-2026-0704", ship="2026-11-02", present_after=8)
    add("N05", "near_miss", t, accepted=[
        {"rule_id": "CHK-02", "note": "Goods shipped on 2 Nov 2026, well before the latest shipment date of 15 Nov. Early shipment is not a discrepancy."}],
        note="Shipped early.")

    t = build_truth(base, "N06", lc_no="LC-NTX-2026-0705")
    add("N06", "near_miss", t, accepted=a_date_formats(t), note="Different date formats on different documents.")
    return cases


def make_demo(base):
    """The demo deal: 4 planted errors + 2 harmless variations."""
    t = build_truth(base, "DEMO")
    findings = []
    findings += m_wrong_loading_port(t)                                       # CHK-08
    findings += m_late_presentation(t)                                        # CHK-03
    t["presentation"]["presentation_date"] = shift(t["bill_of_lading"]["shipped_on_board_date"], 24)
    findings[-1]["description"] = "Documents were presented 24 days after shipment; the credit allows 21 days."
    findings += m_insurance_100(t)                                            # CHK-11
    findings += m_weight_conflict(t)                                          # CHK-14
    accepted = a_cotton_garments(t) + a_address_abbreviation(t)               # CHK-18, CHK-20
    return t, findings, accepted


# ----------------------------------------------------------------------------
# Writing files
# ----------------------------------------------------------------------------
def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def answer_key(case_id, group, findings, accepted, note):
    return {
        "case_id": case_id,
        "group": group,
        "expected_verdict": "discrepant" if findings else "compliant",
        "expected_findings": findings,
        "expected_accepted": accepted,
        "note": note,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    make_pdf = not args.no_pdf

    with open(BASE_PATH, encoding="utf-8") as f:
        base = json.load(f)

    # demo
    demo_t, demo_f, demo_a = make_demo(copy.deepcopy(base))
    save_json("data/truth/demo.json", demo_t)
    save_json("data/demo/demo_answer_key.json", answer_key("DEMO", "demo", demo_f, demo_a, "The deal shown to judges."))
    render_case(demo_t, "data/demo/planted", make_pdf=make_pdf)
    render_case(base, "data/demo/clean", make_pdf=make_pdf)
    print("Demo: %d errors planted, %d harmless variations" % (len(demo_f), len(demo_a)))

    # gold
    cases = make_cases(copy.deepcopy(base))
    index = []
    for c in cases:
        folder = os.path.join("data", "gold", c["case_id"])
        save_json(os.path.join(folder, "truth.json"), c["truth"])
        key = answer_key(c["case_id"], c["group"], c["findings"], c["accepted"], c["note"])
        save_json(os.path.join(folder, "answer_key.json"), key)
        render_case(c["truth"], os.path.join(folder, "docs"), make_pdf=make_pdf)
        index.append({"case_id": c["case_id"], "group": c["group"], "expected_verdict": key["expected_verdict"],
                      "expected_rule_ids": sorted({f["rule_id"] for f in c["findings"]}), "note": c["note"]})
    save_json("data/gold/index.json", index)
    print("Gold set: %d cases written to data/gold" % len(cases))
    for g in ["clean", "single_error", "multi_error", "near_miss"]:
        print("   %-13s %d" % (g, sum(1 for c in cases if c["group"] == g)))


if __name__ == "__main__":
    main()
