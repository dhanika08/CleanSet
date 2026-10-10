# CleanSet Rulebook v1 (20 Core Document Checks)

| Check ID   | Document Pair / Source      | Comparison / Condition                               | Classification | Pass Condition                                                     | UCP 600 Ref. |
| ---------- | --------------------------- | ---------------------------------------------------- | -------------- | ------------------------------------------------------------------ | ------------ |
| **CHK-01** | LC 31D vs Presentation Date | Current Date <= Field 31D (Expiry Date)              | **Rule**       | Presentation date is on or before expiry.                          | Art. 6       |
| **CHK-02** | B/L vs LC 44C               | Shipped on Board Date <= Field 44C (Latest Shipment) | **Rule**       | Shipment date is on or before Field 44C.                           | Art. 14c     |
| **CHK-03** | B/L vs LC 48                | (Presentation Date - Shipment Date) <= Field 48 Days | **Rule**       | Days elapsed <= Field 48 limit (Default 21 days).                  | Art. 14c     |
| **CHK-04** | Invoice vs LC 32B           | Invoice Total Amount <= Field 32B Credit Amount      | **Rule**       | Total invoice amount does not exceed LC cap (+39A tolerance).      | Art. 18b     |
| **CHK-05** | Invoice vs LC 45A           | Product Description Text Comparison                  | **Rule**       | Invoice description matches LC Field 45A verbatim.                 | Art. 18c     |
| **CHK-06** | Invoice vs LC               | Billed Party Name & Address                          | **Rule**       | Invoice is made out to Applicant name in LC.                       | Art. 18a     |
| **CHK-07** | Invoice vs LC               | Issuer Name & Signature                              | **Rule**       | Issued and signed by the Beneficiary named in LC.                  | Art. 18a     |
| **CHK-08** | B/L vs LC 44E               | Port of Loading / Origin Airport                     | **Rule**       | Port of loading on B/L matches Field 44E exactly.                  | Art. 20a     |
| **CHK-09** | B/L vs LC 44F               | Port of Discharge / Destination                      | **Rule**       | Port of discharge on B/L matches Field 44F exactly.                | Art. 20a     |
| **CHK-10** | B/L Inspection              | Clean On Board Status                                | **Rule**       | B/L contains no clause indicating defective goods/packaging.       | Art. 27      |
| **CHK-11** | Insurance vs LC 32B         | Policy Amount Coverage Percentage                    | **Rule**       | Insured amount >= 110% of CIF/CIP invoice value.                   | Art. 28f     |
| **CHK-12** | Insurance vs B/L            | Effective Date of Insurance Policy                   | **Rule**       | Insurance start date <= B/L Shipped on Board date.                 | Art. 28e     |
| **CHK-13** | Insurance vs LC 32B         | Policy Currency                                      | **Rule**       | Insurance policy currency matches LC Field 32B currency.           | Art. 28x     |
| **CHK-14** | Packing List vs B/L         | Gross Weight & Volume Comparison                     | **Judgement**  | Weights/volumes do not conflict across PL and B/L.                 | Art. 14d     |
| **CHK-15** | Packing List vs Invoice     | Item Package Count & Marks                           | **Judgement**  | Package quantities match invoice item breakdowns.                  | Art. 14d     |
| **CHK-16** | Certificate of Origin vs LC | Country of Origin Declaration                        | **Rule**       | Country of origin matches LC requirements.                         | Art. 14d     |
| **CHK-17** | Inspection Cert vs LC       | Named Inspector Entity                               | **Rule**       | Certificate issued by agency specified in Field 46A/47A.           | Art. 14a     |
| **CHK-18** | B/L vs Invoice              | Goods Description General Consistency                | **Judgement**  | B/L general description does not conflict with Invoice.            | Art. 14e     |
| **CHK-19** | All Documents vs LC         | LC Reference Number Presence                         | **Rule**       | LC number is quoted on all presented documents if required by 47A. | Art. 14a     |
| **CHK-20** | All Documents               | Spelled Names & Addresses Consistency                | **Judgement**  | Minor address or spelling variants do not create conflict.         | ISBP 821     |
