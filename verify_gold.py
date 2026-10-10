"""
verify_gold.py - an INDEPENDENT check of the answer keys.

It reads each case's truth.json, works out the discrepancies with plain Python
rules, and compares the result with answer_key.json. If they disagree, either
the answer key or the generator has a bug, and you should fix it before using
the gold set to measure anything.

This is also a preview of the "Rule checks (plain code)" step on Day 4.

Run:  python3 verify_gold.py
"""
import json
import os
import sys
from datetime import date


def d(s):
    return date.fromisoformat(s)


def cents(x):
    """Money is compared in whole cents so 1.10 x 50,000 does not become 55000.00000000001."""
    return round(x * 100)


def run_rules(t):
    """Return the set of rule IDs that fail for this deal."""
    lc, inv, pl, bl, ins = t["lc"], t["invoice"], t["packing_list"], t["bill_of_lading"], t["insurance"]
    pres = t["presentation"]["presentation_date"]
    ship = bl["shipped_on_board_date"]
    fails = set()

    # CHK-01 presented after the credit expired
    if d(pres) > d(lc["31D_expiry"]["date"]):
        fails.add("CHK-01")
    # CHK-02 shipped after the latest shipment date
    if d(ship) > d(lc["44C_latest_shipment_date"]):
        fails.add("CHK-02")
    # CHK-03 presented more than N days after shipment
    if (d(pres) - d(ship)).days > lc["48_presentation_period_days"]:
        fails.add("CHK-03")
    # CHK-04 invoice total above the credit amount (plus tolerance)
    tol = lc["39A_tolerance"]["plus_percent"]
    cap = lc["32B_currency_amount"]["amount"] * (1 + tol / 100.0)
    if cents(inv["total_amount"]) > cents(cap):
        fails.add("CHK-04")
    # CHK-05 invoice description differs from the credit
    lc_desc = lc["45A_goods_description"]
    if inv["goods_description"] != lc_desc:
        about = lc_desc.startswith("ABOUT ")
        # 'about' allows +/-10% on the quantity (UCP 600 Art. 30(a)). Compare the text after the quantity.
        if about:
            same_rest_lc = lc_desc.split(" PCS ", 1)[1].replace("USD 10.00", "")
            same_rest_inv = inv["goods_description"].split(" PCS ", 1)[1].replace("USD 10.00", "")
            lc_qty = int(lc_desc[len("ABOUT "):].split(" PCS")[0].replace(",", ""))
            within = abs(inv["quantity"] - lc_qty) <= 0.10 * lc_qty
            if not (within and same_rest_lc == same_rest_inv):
                fails.add("CHK-05")
        else:
            fails.add("CHK-05")
    # CHK-06 invoice made out to someone other than the applicant
    if inv["made_out_to"]["name"] != lc["50_applicant"]["name"]:
        fails.add("CHK-06")
    # CHK-07 invoice issued by someone other than the beneficiary
    if inv["issued_by"]["name"] != lc["59_beneficiary"]["name"]:
        fails.add("CHK-07")
    # CHK-08 / CHK-09 ports on the bill of lading
    if bl["port_of_loading"] != lc["44E_port_of_loading"]:
        fails.add("CHK-08")
    if bl["port_of_discharge"] != lc["44F_port_of_discharge"]:
        fails.add("CHK-09")
    # CHK-10 clean on board
    if not bl["clean_on_board"]:
        fails.add("CHK-10")
    # CHK-11 insurance at least 110% of the CIF value
    if cents(ins["insured_amount"]) < cents(ins["cif_invoice_value"] * 1.10):
        fails.add("CHK-11")
    # CHK-12 insurance must start on or before shipment
    if d(ins["effective_from"]) > d(ship):
        fails.add("CHK-12")
    # CHK-13 insurance currency
    if ins["currency"] != lc["32B_currency_amount"]["currency"]:
        fails.add("CHK-13")
    # CHK-14 weight / volume conflict between packing list and bill of lading
    if pl["gross_weight_kg"] != bl["gross_weight_kg"] or pl["volume_cbm"] != bl["measurement_cbm"]:
        fails.add("CHK-14")
    # CHK-15 package count
    if pl["total_cartons"] != bl["number_of_packages"] or sum(s["pieces"] for s in pl["size_breakdown"]) != inv["quantity"]:
        fails.add("CHK-15")
    # CHK-16 country of origin
    if t["certificate_of_origin"]["country_of_origin"] != "INDIA":
        fails.add("CHK-16")
    # CHK-19 LC number on every document
    n = lc["20_documentary_credit_number"]
    if any(x["lc_number"] != n for x in (inv, pl, bl, ins, t["certificate_of_origin"])):
        fails.add("CHK-19")
    return fails


def main():
    with open("data/gold/index.json", encoding="utf-8") as f:
        index = json.load(f)
    problems = 0
    for item in index:
        cid = item["case_id"]
        folder = os.path.join("data", "gold", cid)
        t = json.load(open(os.path.join(folder, "truth.json"), encoding="utf-8"))
        key = json.load(open(os.path.join(folder, "answer_key.json"), encoding="utf-8"))
        expected = {f["rule_id"] for f in key["expected_findings"]}
        actual = run_rules(t)
        ok = expected == actual
        print("%s  %-4s expected=%-28s actual=%s" % ("OK  " if ok else "FAIL", cid, sorted(expected), sorted(actual)))
        if not ok:
            problems += 1

    # the demo set too
    t = json.load(open("data/truth/demo.json", encoding="utf-8"))
    key = json.load(open("data/demo/demo_answer_key.json", encoding="utf-8"))
    expected = {f["rule_id"] for f in key["expected_findings"]}
    actual = run_rules(t)
    ok = expected == actual
    print("%s  DEMO expected=%-28s actual=%s" % ("OK  " if ok else "FAIL", sorted(expected), sorted(actual)))
    if not ok:
        problems += 1

    print("\n%s" % ("All answer keys agree with the independent checker." if problems == 0
                    else "%d case(s) disagree. Fix make_gold.py and re-run it." % problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
