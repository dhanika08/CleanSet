"""
render.py - turns ONE truth JSON file into a full set of trade documents.

What it makes (in the --out folder):
    lc.txt                    the letter of credit, in SWIFT MT700 style text
    invoice.html              commercial invoice
    packing_list.html         packing list
    bill_of_lading.html       bill of lading
    insurance_certificate.html
    certificate_of_origin.html
    presentation_letter.html  the cover letter that carries the presentation date
    (and a .pdf next to each .html if Google Chrome is found on this computer)

Usage:
    python3 render.py --input data/truth/base.json --out data/demo/clean

Everything printed on the documents comes from the JSON. Nothing is hard-coded,
so changing a value in the JSON changes the document. That is how we plant errors.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date

from jinja2 import Environment

DEFAULT_DATE_FORMAT = "%d %b %Y"          # e.g. 08 Nov 2026

# ----------------------------------------------------------------------------
# Shared look for all HTML documents
# ----------------------------------------------------------------------------
CSS = """
@page { size: A4; margin: 14mm; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #111; margin: 0; padding: 0; }
h1 { font-size: 20px; letter-spacing: 1.5px; margin: 0 0 2px 0; }
h2 { font-size: 12px; margin: 14px 0 4px 0; text-transform: uppercase; }
.sub { color: #555; margin-bottom: 12px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0; }
td, th { border: 1px solid #444; padding: 5px 7px; vertical-align: top; text-align: left; }
th { background: #ececec; }
.lbl { font-size: 8.5px; color: #555; text-transform: uppercase; display: block; margin-bottom: 2px; }
.r { text-align: right; }
.c { text-align: center; }
.sig { margin-top: 36px; }
.line { border-top: 1px solid #111; width: 220px; margin-top: 30px; padding-top: 3px; }
.foot { margin-top: 22px; font-size: 9px; color: #666; border-top: 1px solid #aaa; padding-top: 5px; }
.badge { display: inline-block; border: 2px solid #1b4f9c; color: #1b4f9c; padding: 3px 9px; font-weight: bold; font-size: 11px; }
.big { font-size: 13px; font-weight: bold; }
"""

PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{ title }}</title><style>""" + CSS + """</style></head>
<body>
{% block body %}{% endblock %}
<div class="foot">Sample document generated for software testing. All names, numbers and companies are fictional.</div>
</body></html>"""

# ----------------------------------------------------------------------------
# HTML templates (one string per document)
# ----------------------------------------------------------------------------
INVOICE = """
<h1>COMMERCIAL INVOICE</h1>
<div class="sub">Original</div>
<table>
<tr><td width="50%"><span class="lbl">Exporter / Seller</span><b>{{ x.issued_by.name }}</b><br>{{ x.issued_by.address }}</td>
    <td><span class="lbl">Invoice No. and date</span>{{ x.invoice_number }}<br>{{ x.invoice_date|fd('invoice') }}<br>
        <span class="lbl" style="margin-top:6px">Documentary credit no.</span>{{ x.lc_number }}</td></tr>
<tr><td><span class="lbl">Sold to / Made out to</span><b>{{ x.made_out_to.name }}</b><br>{{ x.made_out_to.address }}</td>
    <td><span class="lbl">Terms of delivery</span>{{ x.incoterm }}<br>
        <span class="lbl" style="margin-top:6px">Shipment</span>From: {{ x.shipment_from }}<br>To: {{ x.shipment_to }}</td></tr>
</table>
<table>
<tr><th>Description of goods</th><th>HS code</th><th class="r">Quantity</th><th class="r">Unit price ({{ x.currency }})</th><th class="r">Amount ({{ x.currency }})</th></tr>
<tr><td>{{ x.goods_description }}</td><td>{{ x.hs_code }}</td>
    <td class="r">{{ '{:,}'.format(x.quantity) }} {{ x.unit }}</td>
    <td class="r">{{ x.unit_price|money }}</td><td class="r">{{ x.total_amount|money }}</td></tr>
<tr><td colspan="4" class="r"><b>TOTAL {{ x.incoterm }}</b></td><td class="r big">{{ x.currency }} {{ x.total_amount|money }}</td></tr>
</table>
<p>We hereby certify that this invoice is true and correct. Number of originals issued: {{ x.number_of_originals }}.</p>
<div class="sig">For {{ x.issued_by.name }}{% if x.signed %}<div class="line">Authorised Signatory (signed)</div>{% else %}<div class="line">Authorised Signatory (NOT SIGNED)</div>{% endif %}</div>
"""

PACKING = """
<h1>PACKING LIST</h1>
<div class="sub">Packing list no. {{ x.packing_list_number }} &nbsp;|&nbsp; Date: {{ x.packing_list_date|fd('packing_list') }} &nbsp;|&nbsp; Documentary credit no.: {{ x.lc_number }}</div>
<table>
<tr><td width="50%"><span class="lbl">Exporter</span><b>{{ x.issued_by.name }}</b><br>{{ x.issued_by.address }}</td>
    <td><span class="lbl">Consignee</span><b>{{ x.consignee.name }}</b><br>{{ x.consignee.address }}</td></tr>
<tr><td colspan="2"><span class="lbl">Shipping marks</span>{{ x.shipping_marks }}</td></tr>
</table>
<p><b>Goods:</b> {{ x.goods_description }}</p>
<table>
<tr><th>Size</th><th class="r">Cartons</th><th class="r">Pieces per carton</th><th class="r">Pieces</th></tr>
{% for s in x.size_breakdown %}
<tr><td>{{ s.size }}</td><td class="r">{{ s.cartons }}</td><td class="r">{{ x.pieces_per_carton }}</td><td class="r">{{ '{:,}'.format(s.pieces) }}</td></tr>
{% endfor %}
<tr><td><b>TOTAL</b></td><td class="r"><b>{{ x.total_cartons }}</b></td><td></td><td class="r"><b>{{ '{:,}'.format(x.total_pieces) }}</b></td></tr>
</table>
<table>
<tr><td><span class="lbl">Carton size (cm)</span>{{ x.carton_size_cm }}</td>
    <td><span class="lbl">Net weight</span>{{ '{:,.1f}'.format(x.net_weight_kg) }} KGS</td>
    <td><span class="lbl">Gross weight</span><b>{{ '{:,.1f}'.format(x.gross_weight_kg) }} KGS</b></td>
    <td><span class="lbl">Volume</span>{{ '{:,.2f}'.format(x.volume_cbm) }} CBM</td></tr>
</table>
<div class="sig">For {{ x.issued_by.name }}<div class="line">Authorised Signatory</div></div>
"""

BL = """
<h1>BILL OF LADING</h1>
<div class="sub">{{ x.carrier }} &nbsp;|&nbsp; B/L no. {{ x.bl_number }} &nbsp;|&nbsp; Number of originals: {{ x.number_of_originals }}</div>
<table>
<tr><td width="50%"><span class="lbl">Shipper</span><b>{{ x.shipper.name }}</b><br>{{ x.shipper.address }}</td>
    <td><span class="lbl">Documentary credit no.</span>{{ x.lc_number }}</td></tr>
<tr><td><span class="lbl">Consignee</span><b>{{ x.consignee }}</b></td>
    <td><span class="lbl">Notify party</span><b>{{ x.notify_party.name }}</b><br>{{ x.notify_party.address }}</td></tr>
<tr><td><span class="lbl">Vessel / Voyage</span>{{ x.vessel }} / {{ x.voyage }}</td>
    <td><span class="lbl">Place of receipt</span>{{ x.place_of_receipt }}</td></tr>
<tr><td><span class="lbl">Port of loading</span><b>{{ x.port_of_loading }}</b></td>
    <td><span class="lbl">Port of discharge</span><b>{{ x.port_of_discharge }}</b></td></tr>
</table>
<table>
<tr><th>Marks and numbers</th><th>Packages and description of goods</th><th class="r">Gross weight</th><th class="r">Measurement</th></tr>
<tr><td>{{ x.marks_and_numbers }}<br>Container {{ x.container_number }}<br>Seal {{ x.seal_number }}</td>
    <td>{{ x.number_of_packages }} {{ x.package_type }}<br>{{ x.goods_description }}</td>
    <td class="r">{{ '{:,.1f}'.format(x.gross_weight_kg) }} KGS</td>
    <td class="r">{{ '{:,.2f}'.format(x.measurement_cbm) }} CBM</td></tr>
</table>
<table>
<tr><td><span class="lbl">Freight</span>{{ x.freight }}</td>
    <td><span class="lbl">Remarks</span><b>{{ x.remarks }}</b></td></tr>
<tr><td><span class="lbl">Shipped on board date</span><span class="big">{{ x.shipped_on_board_date|fd('bill_of_lading') }}</span></td>
    <td><span class="lbl">Place and date of issue</span>{{ x.place_of_issue }}, {{ x.date_of_issue|fd('bill_of_lading') }}</td></tr>
</table>
<p>SHIPPED on board in apparent good order and condition, unless otherwise noted above.</p>
<div class="sig">For the Carrier, {{ x.carrier }}<div class="line">Master / Agent</div></div>
"""

INSURANCE = """
<h1>MARINE INSURANCE CERTIFICATE</h1>
<div class="sub">Certificate no. {{ x.certificate_number }} &nbsp;|&nbsp; Issued by {{ x.insurer }}</div>
<table>
<tr><td width="50%"><span class="lbl">Insured</span><b>{{ x.insured }}</b></td>
    <td><span class="lbl">Documentary credit no.</span>{{ x.lc_number }}</td></tr>
<tr><td><span class="lbl">Date of issue</span>{{ x.date_of_issue|fd('insurance') }}</td>
    <td><span class="lbl">Cover effective from</span><b>{{ x.effective_from|fd('insurance') }}</b></td></tr>
<tr><td><span class="lbl">Voyage from</span>{{ x.from }}</td><td><span class="lbl">Voyage to</span>{{ x.to }}</td></tr>
<tr><td><span class="lbl">Vessel</span>{{ x.vessel }}</td><td><span class="lbl">Conditions</span>{{ x.cover_clauses }}</td></tr>
</table>
<p><b>Goods insured:</b> {{ x.goods_description }}</p>
<table>
<tr><td><span class="lbl">CIF invoice value</span>{{ x.currency }} {{ x.cif_invoice_value|money }}</td>
    <td><span class="lbl">Sum insured</span><span class="big">{{ x.currency }} {{ x.insured_amount|money }}</span></td>
    <td><span class="lbl">Percentage of CIF value</span>{{ (x.insured_amount / x.cif_invoice_value * 100)|round(1) }}%</td></tr>
<tr><td colspan="3"><span class="lbl">Claims payable</span>At {{ x.claims_payable_at }}, in {{ x.claims_payable_in }}</td></tr>
</table>
<div class="sig">For {{ x.insurer }}<div class="line">Authorised Signatory</div></div>
"""

ORIGIN = """
<h1>CERTIFICATE OF ORIGIN</h1>
<div class="sub">Certificate no. {{ x.certificate_number }} &nbsp;|&nbsp; Date: {{ x.date_of_issue|fd('certificate_of_origin') }} &nbsp;|&nbsp; Documentary credit no.: {{ x.lc_number }}</div>
<table>
<tr><td width="50%"><span class="lbl">Exporter</span><b>{{ x.exporter.name }}</b><br>{{ x.exporter.address }}</td>
    <td><span class="lbl">Consignee</span><b>{{ x.consignee.name }}</b><br>{{ x.consignee.address }}</td></tr>
<tr><td><span class="lbl">Port of loading</span>{{ x.port_of_loading }}</td><td><span class="lbl">Port of discharge</span>{{ x.port_of_discharge }}</td></tr>
<tr><td colspan="2"><span class="lbl">Description of goods</span>{{ x.goods_description }}</td></tr>
<tr><td colspan="2"><span class="lbl">Country of origin</span><span class="big">{{ x.country_of_origin }}</span></td></tr>
</table>
<p>{{ x.declaration }}</p>
<div class="sig">Certified by {{ x.issued_by }}<div class="line">Authorised Officer (stamp and signature)</div></div>
"""

PRESENTATION = """
<h1>COVERING SCHEDULE OF DOCUMENTS</h1>
<div class="sub">Documents presented under documentary credit no. {{ lc_no }}</div>
<table>
<tr><td width="50%"><span class="lbl">To (negotiating / nominated bank)</span><b>{{ x.presented_to }}</b></td>
    <td><span class="lbl">Date of presentation</span><span class="big">{{ x.presentation_date|fd('presentation_letter') }}</span></td></tr>
<tr><td><span class="lbl">From (beneficiary)</span><b>{{ beneficiary.name }}</b><br>{{ beneficiary.address }}</td>
    <td><span class="lbl">Issuing bank</span>{{ issuing_bank.name }}</td></tr>
</table>
<table>
<tr><th>#</th><th>Document</th><th>Originals</th></tr>
<tr><td>1</td><td>Commercial invoice no. {{ inv_no }}</td><td>{{ inv_orig }}</td></tr>
<tr><td>2</td><td>Packing list no. {{ pl_no }}</td><td>3</td></tr>
<tr><td>3</td><td>Bill of lading no. {{ bl_no }}</td><td>{{ bl_orig }}</td></tr>
<tr><td>4</td><td>Insurance certificate no. {{ ins_no }}</td><td>1</td></tr>
<tr><td>5</td><td>Certificate of origin no. {{ co_no }}</td><td>1</td></tr>
</table>
<p>We present the above documents for payment under the terms of the documentary credit.</p>
<div class="sig">For {{ beneficiary.name }}<div class="line">Authorised Signatory</div></div>
"""

# ----------------------------------------------------------------------------
# The letter of credit as MT700-style plain text
# ----------------------------------------------------------------------------
LC_TEXT = """\
MT 700  ISSUE OF A DOCUMENTARY CREDIT
(SAMPLE FOR SOFTWARE TESTING - ALL DATA FICTIONAL)

FROM: {{ x.issuing_bank.name }}
      {{ x.issuing_bank.address }}
TO:   {{ x.advising_bank.name }}
      {{ x.advising_bank.address }}

:27:  SEQUENCE OF TOTAL
      {{ x['27_sequence_of_total'] }}
:40A: FORM OF DOCUMENTARY CREDIT
      {{ x['40A_form_of_credit'] }}
:20:  DOCUMENTARY CREDIT NUMBER
      {{ x['20_documentary_credit_number'] }}
:31C: DATE OF ISSUE
      {{ x['31C_date_of_issue']|fd('lc') }}
:40E: APPLICABLE RULES
      {{ x['40E_applicable_rules'] }}
:31D: DATE AND PLACE OF EXPIRY
      {{ x['31D_expiry'].date|fd('lc') }} {{ x['31D_expiry'].place }}
:50:  APPLICANT
      {{ x['50_applicant'].name }}
      {{ x['50_applicant'].address }}
:59:  BENEFICIARY
      {{ x['59_beneficiary'].name }}
      {{ x['59_beneficiary'].address }}
:32B: CURRENCY CODE, AMOUNT
      {{ x['32B_currency_amount'].currency }} {{ x['32B_currency_amount'].amount|money }}
:39A: PERCENTAGE CREDIT AMOUNT TOLERANCE
      {{ x['39A_tolerance'].plus_percent }}/{{ x['39A_tolerance'].minus_percent }}
:41D: AVAILABLE WITH ... BY ...
      {{ x['41D_available_with'] }}
:43P: PARTIAL SHIPMENTS
      {{ x['43P_partial_shipments'] }}
:43T: TRANSSHIPMENT
      {{ x['43T_transhipment'] }}
:44E: PORT OF LOADING
      {{ x['44E_port_of_loading'] }}
:44F: PORT OF DISCHARGE
      {{ x['44F_port_of_discharge'] }}
:44C: LATEST DATE OF SHIPMENT
      {{ x['44C_latest_shipment_date']|fd('lc') }}
:45A: DESCRIPTION OF GOODS AND/OR SERVICES
      {{ x['45A_goods_description'] }}
:46A: DOCUMENTS REQUIRED
{% for d in x['46A_documents_required'] %}      +{{ d }}
{% endfor %}:47A: ADDITIONAL CONDITIONS
{% for d in x['47A_additional_conditions'] %}      +{{ d }}
{% endfor %}:48:  PERIOD FOR PRESENTATION
      DOCUMENTS MUST BE PRESENTED WITHIN {{ x['48_presentation_period_days'] }} DAYS AFTER THE DATE OF
      SHIPMENT BUT WITHIN THE VALIDITY OF THE CREDIT.
:49:  CONFIRMATION INSTRUCTIONS
      {{ x['49_confirmation'] }}
"""


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def make_env(truth, escape=True):
    """Build the Jinja2 environment with our two custom filters: money and fd.
    escape=True is for HTML pages (turns & and ' into safe codes).
    escape=False is for the plain-text LC, where we want the raw characters."""
    env = Environment(autoescape=escape, trim_blocks=True, lstrip_blocks=True)
    formats = truth.get("_render", {}).get("date_formats", {})

    def money(v):
        return "{:,.2f}".format(v)

    def fd(value, doc="default"):
        """Format an ISO date string like 2026-11-08 using this document's date format."""
        fmt = formats.get(doc, DEFAULT_DATE_FORMAT)
        return date.fromisoformat(value).strftime(fmt)

    env.filters["money"] = money
    env.filters["fd"] = fd
    return env


def find_chrome():
    """Look for Google Chrome / Chromium on this computer. Returns a path or None."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def html_to_pdf(chrome, html_path):
    pdf_path = html_path[:-5] + ".pdf"
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           "--print-to-pdf=" + pdf_path, "file://" + os.path.abspath(html_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return True
    except Exception as e:                       # PDFs are nice-to-have, never crash
        print("  warning: PDF failed for", os.path.basename(html_path), "-", e)
        return False


def render_case(truth, out_dir, make_pdf=True):
    """Render all documents for one truth dict into out_dir. Returns list of files written."""
    os.makedirs(out_dir, exist_ok=True)
    env = make_env(truth)
    written = []

    def write_html(name, body, ctx, title):
        tpl = env.from_string(PAGE.replace("{% block body %}{% endblock %}", body))
        path = os.path.join(out_dir, name + ".html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tpl.render(title=title, **ctx))
        written.append(path)

    write_html("invoice", INVOICE, {"x": truth["invoice"]}, "Commercial Invoice")
    write_html("packing_list", PACKING, {"x": truth["packing_list"]}, "Packing List")
    write_html("bill_of_lading", BL, {"x": truth["bill_of_lading"]}, "Bill of Lading")
    write_html("insurance_certificate", INSURANCE, {"x": truth["insurance"]}, "Insurance Certificate")
    write_html("certificate_of_origin", ORIGIN, {"x": truth["certificate_of_origin"]}, "Certificate of Origin")
    write_html("presentation_letter", PRESENTATION, {
        "x": truth["presentation"],
        "lc_no": truth["lc"]["20_documentary_credit_number"],
        "beneficiary": truth["lc"]["59_beneficiary"],
        "issuing_bank": truth["lc"]["issuing_bank"],
        "inv_no": truth["invoice"]["invoice_number"], "inv_orig": truth["invoice"]["number_of_originals"],
        "pl_no": truth["packing_list"]["packing_list_number"],
        "bl_no": truth["bill_of_lading"]["bl_number"], "bl_orig": truth["bill_of_lading"]["number_of_originals"],
        "ins_no": truth["insurance"]["certificate_number"],
        "co_no": truth["certificate_of_origin"]["certificate_number"],
    }, "Covering Schedule")

    lc_path = os.path.join(out_dir, "lc.txt")
    with open(lc_path, "w", encoding="utf-8") as f:
        f.write(make_env(truth, escape=False).from_string(LC_TEXT).render(x=truth["lc"]) + "\n")
    written.append(lc_path)

    if make_pdf:
        chrome = find_chrome()
        if chrome:
            for p in [w for w in written if w.endswith(".html")]:
                html_to_pdf(chrome, p)
        else:
            print("  note: Google Chrome not found, so no PDFs were made (the HTML files are fine).")
    return written


def main():
    ap = argparse.ArgumentParser(description="Render trade documents from a truth JSON file.")
    ap.add_argument("--input", required=True, help="path to the truth JSON file")
    ap.add_argument("--out", required=True, help="folder to write the documents into")
    ap.add_argument("--no-pdf", action="store_true", help="skip PDF creation")
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as f:
        truth = json.load(f)
    files = render_case(truth, args.out, make_pdf=not args.no_pdf)
    print("Wrote %d files to %s" % (len(files), args.out))
    for p in files:
        print("  ", os.path.basename(p))


if __name__ == "__main__":
    sys.exit(main())
