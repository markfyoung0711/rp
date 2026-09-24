# PII in Rental Transactions: What We Test

> Reference grouping supplied during review (not legal advice; definitions vary by state and statute). Each category is planted in [`tests/pii_cases.jsonl`](../tests/pii_cases.jsonl) and detected by [`outreach/pii.py`](../outreach/pii.py). The bot must **withhold** it from every output field. `tests/test_bot.py` and `scripts/run_checks.py` enforce this, and RUN STATS reports the counts per run.

| Tier | Category (as reported in RUN STATS) | Examples planted |
|---|---|---|
| Highest | government ID (SSN/ITIN/license/passport) | SSN, ITIN, driver's license, passport; SSN typed into the first-name field |
| Highest | bank / payment card | bank account, routing number, card number, disbursement account |
| Highest | credit / screening / eviction | credit score, background check, eviction history, adverse action |
| Highest | income / employment | income, employer, pay stubs, tax returns |
| Highest | health / disability / accommodation | medical note, accommodation request, assistance animal; health words in free text |
| Highest | immigration / domestic-violence status | immigration status, VAWA; "domestic violence" in free text |
| Highest | household members (occupants, children) | occupants with DOB, children's names |
| Direct | email, phone, date of birth, address (current/former), last/full name | profile fields, top-level fields, inside notes |
| Direct | signature / photo / ID image | signature data, photo URL, ID scan |
| Direct | emergency contact / guarantor / co-signer | nested contact and guarantor objects |
| Context | unit / lease data | unit number, lease dates, rent amount, move-out date |
| Context | payment / ledger / delinquency | ledger, balance, past due, payment history |
| Context | access / device / vehicle / recordings | access code, smart-lock log, plate, vehicle, voicemail, IP, device ID |
| Context | derived scores / inferences | sentiment score, risk score |
| Owner/vendor | owner / vendor tax ID (EIN, TIN, W-9) | EIN, tax ID, W-9 |
| Owner/vendor | owner identity (LLC / trust members) | beneficial owners, trustee |
| Related | protected-class details (counted separately, fair housing) | race, religion, familial status, has_children, national origin, marital status, age, veteran |

**How the bot applies "minimum necessary"**
- **Output:** only the first name (in the greeting, as in the samples) and the caller's `task_id`. Every other category above stays out of the body, subject, `why` and warnings. A rejected first name is never echoed.
- **Weak channels (SMS/email):** messages never carry money amounts, balances, lease terms, or account- or ID-like numbers. A guard blocks `$`, decimal amounts and 8+ digit runs. The rent reminder says "your payment", not the amount.
- **Model prompts (`--llm`):** only allow-listed fields (first name, property, interests, move timing, CTA type). A test checks that none of the planted data reaches the prompt.
- **Wrong-number risk:** a reassigned number would still receive the greeting and the property name, which is inherent in the expected outputs. Messages carry no case details beyond that.
- **Storage:** the bot keeps no logs of records. Output files contain only the fields above. The `--llm` cache stores only model answers, keyed by a hash.
