"""
check_base.py - verifies that data/truth/base.json is internally consistent
and COMPLIANT with its own letter of credit. Run it after any edit to base.json.
Usage:  python3 check_base.py data/truth/base.json
"""
import json, sys
from datetime import date

def d(s): return date.fromisoformat(s)
path = sys.argv[1] if len(sys.argv) > 1 else "data/truth/base.json"
j = json.load(open(path))
lc, inv, pl, bl, ins, co, pres = (j[k] for k in
    ["lc", "invoice", "packing_list", "bill_of_lading", "insurance",
     "certificate_of_origin", "presentation"])

checks = []
def check(name, ok): checks.append((name, bool(ok)))

lc_no = lc["20_documentary_credit_number"]
# --- arithmetic
check("invoice: qty x price = total", abs(inv["quantity"] * inv["unit_price"] - inv["total_amount"]) < 0.001)
check("invoice total <= LC amount (no tolerance)", inv["total_amount"] <= lc["32B_currency_amount"]["amount"])
check("invoice currency = LC currency", inv["currency"] == lc["32B_currency_amount"]["currency"])
check("size breakdown pieces add up to 5,000", sum(s["pieces"] for s in pl["size_breakdown"]) == pl["total_pieces"] == inv["quantity"])
check("size breakdown cartons add up to 100", sum(s["cartons"] for s in pl["size_breakdown"]) == pl["total_cartons"])
check("pieces = cartons x pieces per carton", pl["total_cartons"] * pl["pieces_per_carton"] == pl["total_pieces"])
check("size cartons x 50 = size pieces", all(s["cartons"] * pl["pieces_per_carton"] == s["pieces"] for s in pl["size_breakdown"]))
check("packages on B/L = cartons on packing list", bl["number_of_packages"] == pl["total_cartons"])
check("gross weight: packing list = B/L", pl["gross_weight_kg"] == bl["gross_weight_kg"])
check("volume: packing list = B/L", pl["volume_cbm"] == bl["measurement_cbm"])
check("volume = cartons x carton size", abs(100 * 0.6 * 0.4 * 0.3 - pl["volume_cbm"]) < 0.001)
check("net weight < gross weight", pl["net_weight_kg"] < pl["gross_weight_kg"])
# --- insurance
# Money is compared in whole cents (rounded) because Python floats give 55000.00000000001 for 1.10 x 50000
check("insurance >= 110% of CIF value", round(ins["insured_amount"] * 100) >= round(ins["cif_invoice_value"] * 110))
check("insurance CIF value = invoice total", ins["cif_invoice_value"] == inv["total_amount"])
check("insurance currency = LC currency", ins["currency"] == lc["32B_currency_amount"]["currency"])
check("insurance effective on/before shipment", d(ins["effective_from"]) <= d(bl["shipped_on_board_date"]))
# --- dates
ship = d(bl["shipped_on_board_date"])
check("shipment <= latest shipment date (44C)", ship <= d(lc["44C_latest_shipment_date"]))
check("presentation within 21 days of shipment", 0 <= (d(pres["presentation_date"]) - ship).days <= lc["48_presentation_period_days"])
check("presentation <= LC expiry", d(pres["presentation_date"]) <= d(lc["31D_expiry"]["date"]))
check("invoice dated on/before shipment", d(inv["invoice_date"]) <= ship)
check("LC issued before shipment", d(lc["31C_date_of_issue"]) < ship)
# --- ports & parties
check("B/L loading port = LC 44E", bl["port_of_loading"] == lc["44E_port_of_loading"])
check("B/L discharge port = LC 44F", bl["port_of_discharge"] == lc["44F_port_of_discharge"])
check("invoice ports = LC ports", inv["shipment_from"] == lc["44E_port_of_loading"] and inv["shipment_to"] == lc["44F_port_of_discharge"])
check("invoice made out to applicant", inv["made_out_to"]["name"] == lc["50_applicant"]["name"])
check("invoice issued by beneficiary", inv["issued_by"]["name"] == lc["59_beneficiary"]["name"])
check("certificate of origin = INDIA", co["country_of_origin"] == "INDIA")
check("B/L is clean on board", bl["clean_on_board"] is True)
# --- LC number on all documents (47A)
nums = [inv["lc_number"], pl["lc_number"], bl["lc_number"], ins["lc_number"], co["lc_number"]]
check("LC number quoted on all documents", all(n == lc_no for n in nums))
# --- goods description
check("invoice description = LC 45A", inv["goods_description"] == lc["45A_goods_description"])

width = max(len(n) for n, _ in checks)
for n, ok in checks:
    print(("PASS  " if ok else "FAIL  ") + n)
bad = [n for n, ok in checks if not ok]
print("\n%d of %d checks passed." % (len(checks) - len(bad), len(checks)))
sys.exit(1 if bad else 0)
