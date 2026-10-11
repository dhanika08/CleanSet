"""
rules.py - the plain-code checks. No AI in here.

Each check looks at facts that were read from the documents (a dict of field_id -> value)
and answers: does this document set break the rule, yes or no?

If a fact needed for a check was not found, the check is SKIPPED and listed under
"unchecked". We never guess.

A check that finds a problem returns a "finding":
    rule_id, type="Rule", title, explanation (plain English), fields (which facts it used), fix
"""
from datetime import date


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def d(s):
    return date.fromisoformat(s)


def cents(x):
    """Money in whole cents. Avoids float errors like 1.10 x 50000 = 55000.00000000001."""
    return round(x * 100)


def norm(s):
    """Upper-case, single spaces, so 'Nordic  Textiles GmbH' == 'NORDIC TEXTILES GMBH'."""
    return " ".join(str(s).upper().split())


def place(s):
    """Compare ports by the town name only: 'TUTICORIN, INDIA' and 'Tuticorin' are the same port."""
    return norm(str(s).split(",")[0])


def money(x):
    return "{:,.2f}".format(x)


def ddmmmyyyy(iso):
    return d(iso).strftime("%d %b %Y")


FIXES = {
    "CHK-01": "Ask the buyer to extend the expiry date of the credit (an LC amendment), and present before the new date.",
    "CHK-02": "The shipping date cannot honestly be changed. Ask the buyer to amend the latest shipment date in the credit.",
    "CHK-03": "Present the documents to the bank within the allowed days after shipment. If it is already late, ask the buyer to accept the delay in writing.",
    "CHK-04": "Re-issue the invoice so the total does not exceed the credit amount, or ask the buyer to increase the credit amount.",
    "CHK-05": "Re-issue the invoice with the goods described exactly as in the credit.",
    "CHK-06": "Re-issue the invoice made out to the applicant named in the credit.",
    "CHK-07": "Re-issue the invoice in the name of the beneficiary named in the credit.",
    "CHK-08": "The port on the bill of lading must match the credit. Ask the shipping line to correct it, or ask the buyer to amend the credit if the goods really sailed from another port.",
    "CHK-09": "The port on the bill of lading must match the credit. Ask the shipping line to correct it, or ask the buyer to amend the credit.",
    "CHK-10": "Ask the shipping line for a clean bill of lading without damage remarks.",
    "CHK-11": "Ask the insurer to re-issue the certificate covering at least 110% of the CIF value.",
    "CHK-12": "Ask the insurer to re-issue the certificate with cover starting on or before the shipment date.",
    "CHK-13": "Ask the insurer to re-issue the certificate in the same currency as the credit.",
    "CHK-14": "Check the real weight and correct the wrong document so the packing list and bill of lading agree.",
    "CHK-15": "Correct the document so the number of cartons or packages is the same everywhere.",
    "CHK-16": "Obtain a certificate of origin that shows the country required by the credit.",
    "CHK-18": "Re-issue the bill of lading with a goods description that does not conflict with the invoice.",
    "CHK-19": "Re-issue the document so it quotes the documentary credit number.",
    "CHK-20": "Correct the name or address so it is not in conflict with the credit.",
}


def _finding(rule_id, title, explanation, fields):
    return {"rule_id": rule_id, "type": "Rule", "title": title, "explanation": explanation,
            "fields": fields, "fix": FIXES.get(rule_id, "")}


# ---------------------------------------------------------------------------
# The checks. Each takes V (field_id -> clean value) and returns
#   None            = passes
#   a finding dict  = breaks the rule
#   "SKIP"          = could not check because a needed fact was not found
# ---------------------------------------------------------------------------
def _need(V, *ids):
    return all(V.get(i) is not None for i in ids)


def chk01(V):
    ids = ["presentation.date", "lc.expiry_date"]
    if not _need(V, *ids):
        return "SKIP"
    if d(V["presentation.date"]) > d(V["lc.expiry_date"]):
        return _finding("CHK-01", "Credit had expired",
                        "Documents were presented on %s, after the credit expired on %s." %
                        (ddmmmyyyy(V["presentation.date"]), ddmmmyyyy(V["lc.expiry_date"])), ids)


def chk02(V):
    ids = ["bill_of_lading.shipped_on_board_date", "lc.latest_shipment_date"]
    if not _need(V, *ids):
        return "SKIP"
    if d(V["bill_of_lading.shipped_on_board_date"]) > d(V["lc.latest_shipment_date"]):
        return _finding("CHK-02", "Shipped too late",
                        "The goods were shipped on %s, after the latest allowed shipment date of %s." %
                        (ddmmmyyyy(V["bill_of_lading.shipped_on_board_date"]), ddmmmyyyy(V["lc.latest_shipment_date"])), ids)


def chk03(V):
    ids = ["presentation.date", "bill_of_lading.shipped_on_board_date", "lc.presentation_days"]
    if not _need(V, *ids):
        return "SKIP"
    days = (d(V["presentation.date"]) - d(V["bill_of_lading.shipped_on_board_date"])).days
    limit = int(V["lc.presentation_days"])
    if days > limit:
        return _finding("CHK-03", "Documents presented too late",
                        "Documents were presented %d days after shipment, but the credit allows only %d days." % (days, limit), ids)


def chk04(V):
    ids = ["invoice.total_amount", "lc.amount"]
    if not _need(V, *ids):
        return "SKIP"
    tol = V.get("lc.tolerance_plus_pct") or 0
    cap = V["lc.amount"] * (1 + tol / 100.0)
    if cents(V["invoice.total_amount"]) > cents(cap):
        return _finding("CHK-04", "Invoice total exceeds the credit",
                        "The invoice total is %s, which is more than the credit amount of %s." %
                        (money(V["invoice.total_amount"]), money(cap)), ids)


def chk06(V):
    ids = ["invoice.made_out_to_name", "lc.applicant_name"]
    if not _need(V, *ids):
        return "SKIP"
    if norm(V["invoice.made_out_to_name"]) != norm(V["lc.applicant_name"]):
        return _finding("CHK-06", "Invoice made out to the wrong company",
                        "The invoice is made out to '%s', but the buyer named in the credit is '%s'." %
                        (V["invoice.made_out_to_name"], V["lc.applicant_name"]), ids)


def chk07(V):
    ids = ["invoice.issued_by_name", "lc.beneficiary_name"]
    if not _need(V, *ids):
        return "SKIP"
    if norm(V["invoice.issued_by_name"]) != norm(V["lc.beneficiary_name"]):
        return _finding("CHK-07", "Invoice issued by the wrong company",
                        "The invoice was issued by '%s', but the beneficiary in the credit is '%s'." %
                        (V["invoice.issued_by_name"], V["lc.beneficiary_name"]), ids)


def chk08(V):
    ids = ["bill_of_lading.port_of_loading", "lc.port_of_loading"]
    if not _need(V, *ids):
        return "SKIP"
    if place(V[ids[0]]) != place(V[ids[1]]):
        return _finding("CHK-08", "Wrong port of loading",
                        "The bill of lading shows the goods loaded at %s, but the credit requires %s." %
                        (V[ids[0]], V[ids[1]]), ids)


def chk09(V):
    ids = ["bill_of_lading.port_of_discharge", "lc.port_of_discharge"]
    if not _need(V, *ids):
        return "SKIP"
    if place(V[ids[0]]) != place(V[ids[1]]):
        return _finding("CHK-09", "Wrong port of discharge",
                        "The bill of lading shows the goods going to %s, but the credit requires %s." %
                        (V[ids[0]], V[ids[1]]), ids)


def chk10(V):
    ids = ["bill_of_lading.clean_on_board"]
    if not _need(V, *ids):
        return "SKIP"
    if V[ids[0]] is False:
        return _finding("CHK-10", "Bill of lading is not clean",
                        "The bill of lading carries a remark about damaged or defective goods or packaging.", ids)


def chk11(V):
    ids = ["insurance.insured_amount", "insurance.cif_invoice_value"]
    if not _need(V, *ids):
        return "SKIP"
    need = V["insurance.cif_invoice_value"] * 1.10
    if cents(V["insurance.insured_amount"]) < cents(need):
        pct = V["insurance.insured_amount"] / V["insurance.cif_invoice_value"] * 100
        return _finding("CHK-11", "Insurance cover too low",
                        "Insurance covers %.0f%% of the goods' value (%s), but the credit requires at least 110%% (%s)." %
                        (pct, money(V["insurance.insured_amount"]), money(need)), ids)


def chk12(V):
    ids = ["insurance.effective_from", "bill_of_lading.shipped_on_board_date"]
    if not _need(V, *ids):
        return "SKIP"
    if d(V[ids[0]]) > d(V[ids[1]]):
        return _finding("CHK-12", "Insurance starts after shipment",
                        "Insurance cover starts on %s, but the goods were shipped on %s." %
                        (ddmmmyyyy(V[ids[0]]), ddmmmyyyy(V[ids[1]])), ids)


def chk13(V):
    ids = ["insurance.currency", "lc.currency"]
    if not _need(V, *ids):
        return "SKIP"
    if norm(V[ids[0]]) != norm(V[ids[1]]):
        return _finding("CHK-13", "Insurance in the wrong currency",
                        "Insurance is in %s, but the credit is in %s." % (V[ids[0]], V[ids[1]]), ids)


def chk14(V):
    w = ["packing_list.gross_weight_kg", "bill_of_lading.gross_weight_kg"]
    v = ["packing_list.volume_cbm", "bill_of_lading.measurement_cbm"]
    if _need(V, *w) and V[w[0]] != V[w[1]]:
        return _finding("CHK-14", "Weights do not agree",
                        "The packing list shows a gross weight of %s kg, but the bill of lading shows %s kg." %
                        ("{:,.1f}".format(V[w[0]]), "{:,.1f}".format(V[w[1]])), w)
    if _need(V, *v) and V[v[0]] != V[v[1]]:
        return _finding("CHK-14", "Volumes do not agree",
                        "The packing list shows %s CBM, but the bill of lading shows %s CBM." % (V[v[0]], V[v[1]]), v)
    if not _need(V, *w) and not _need(V, *v):
        return "SKIP"


def chk15(V):
    ids = ["packing_list.total_cartons", "bill_of_lading.number_of_packages"]
    if not _need(V, *ids):
        return "SKIP"
    if V[ids[0]] != V[ids[1]]:
        return _finding("CHK-15", "Package counts do not agree",
                        "The packing list shows %d cartons, but the bill of lading shows %d packages." %
                        (V[ids[0]], V[ids[1]]), ids)


def chk16(V):
    ids = ["certificate_of_origin.country_of_origin"]
    if not _need(V, *ids):
        return "SKIP"
    if norm(V[ids[0]]) != "INDIA":
        return _finding("CHK-16", "Wrong country of origin",
                        "The certificate of origin shows '%s', but the credit requires India." % V[ids[0]], ids)


def chk19(V):
    ids = ["lc.number", "invoice.lc_number", "packing_list.lc_number", "bill_of_lading.lc_number",
           "insurance.lc_number", "certificate_of_origin.lc_number"]
    if V.get("lc.number") is None:
        return "SKIP"
    present = [i for i in ids if V.get(i) is not None]
    wrong = [i for i in present[1:] if norm(V[i]) != norm(V["lc.number"])]
    if wrong:
        docs = ", ".join(i.split(".")[0].replace("_", " ") for i in wrong)
        return _finding("CHK-19", "Credit number missing or wrong",
                        "The credit number %s is not quoted correctly on: %s." % (V["lc.number"], docs), ["lc.number"] + wrong)


ALL_RULES = [chk01, chk02, chk03, chk04, chk06, chk07, chk08, chk09, chk10, chk11,
             chk12, chk13, chk14, chk15, chk16, chk19]


def run_rules(V):
    """Run every plain-code check. Returns (findings, unchecked_rule_ids)."""
    findings, unchecked = [], []
    for fn in ALL_RULES:
        r = fn(V)
        if r == "SKIP":
            unchecked.append(fn.__name__.replace("chk", "CHK-"))
        elif r is not None:
            findings.append(r)
    return findings, unchecked


# ---------------------------------------------------------------------------
# Judgement questions: the cases where wording matters. These go to Gemini,
# but only when a simple text comparison cannot settle the question.
# ---------------------------------------------------------------------------
def judgement_items(V):
    """Return the list of questions that need judgement, skipping the ones plain text can settle."""
    items = []

    def add(rule_id, a, b, question, fix_key=None):
        if V.get(a) is None or V.get(b) is None:
            return
        items.append({"rule_id": rule_id, "a_id": a, "b_id": b, "a_text": V[a], "b_text": V[b],
                      "question": question})

    # CHK-05: invoice goods vs credit goods
    if V.get("lc.goods_description") is not None and V.get("invoice.goods_description") is not None:
        if norm(V["lc.goods_description"]) != norm(V["invoice.goods_description"]):
            add("CHK-05", "lc.goods_description", "invoice.goods_description",
                "Does the invoice goods description correspond to the goods description in the credit? "
                "The invoice must correspond to the credit. If the credit says ABOUT a quantity, a quantity "
                "within 10 percent more or less is allowed. A different price or different goods is a conflict.")
    # CHK-18: bill of lading goods vs invoice goods
    if V.get("invoice.goods_description") is not None and V.get("bill_of_lading.goods_description") is not None:
        if norm(V["bill_of_lading.goods_description"]) not in norm(V["invoice.goods_description"]):
            add("CHK-18", "invoice.goods_description", "bill_of_lading.goods_description",
                "Documents other than the invoice may describe the goods in general terms, as long as the "
                "description does not conflict with the invoice. Does the bill of lading description conflict "
                "with the invoice description?")
    # CHK-20: address of consignee vs applicant
    if V.get("lc.applicant_address") is not None and V.get("packing_list.consignee_address") is not None:
        if norm(V["lc.applicant_address"]) != norm(V["packing_list.consignee_address"]):
            add("CHK-20", "lc.applicant_address", "packing_list.consignee_address",
                "Address details in other documents need not be identical to the credit, but must not conflict "
                "and must be in the same country. Does the packing list address conflict with the credit address?")
    return items


def judgement_finding(item, verdict):
    """Build a finding from a Gemini judgement that said CONFLICT."""
    titles = {"CHK-05": "Invoice description does not match the credit",
              "CHK-18": "Bill of lading description conflicts with the invoice",
              "CHK-20": "Address conflicts with the credit"}
    return {"rule_id": item["rule_id"], "type": "Judgement", "title": titles.get(item["rule_id"], "Documents conflict"),
            "explanation": verdict.get("reason", ""), "fields": verdict.get("cited_fields") or [item["a_id"], item["b_id"]],
            "fix": FIXES.get(item["rule_id"], ""), "article": verdict.get("article", "")}
