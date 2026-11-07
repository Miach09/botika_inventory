# Test Cases and Results

Automated results come from `python -m pytest -v` (run it again on your own computer and update the Actual Result column if anything differs).

| No. | Area | Test Case | Test Input / Action | Expected Result | Actual Result | Pass/Fail |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | CRUD | Create medicine | Add Biogesic / acetaminophen / 500 mg with valid data | Record saved and shown in the table | As expected (automated test) | Pass |
| 2 | CRUD | Read / search | Search 'bio', 'IBUPRO', 'zzz' | Matches brand or generic (case-insensitive); no match gives an empty table | As expected (automated test) | Pass |
| 3 | CRUD | Filter by category | Choose Allergy, then Antibiotic | Only medicines in that category are shown | As expected (automated test) | Pass |
| 4 | CRUD | Update medicine | Change brand name to 'Biogesic Plus' | Updated value shown after saving | As expected (automated test) | Pass |
| 5 | CRUD | Delete medicine | Delete a medicine with no batches | Record removed | As expected (automated test) | Pass |
| 6 | CRUD | Delete missing record | Delete an id that does not exist | Clear 'no longer exists' error, no crash | As expected (automated test) | Pass |
| 7 | CRUD | Duplicate medicine | Add the same brand + strength + form twice | Second add rejected with a friendly message | As expected (automated test) | Pass |
| 8 | CRUD | Delete protected by stock | Delete a medicine that has stock batches | Delete blocked; medicine kept | As expected (automated test) | Pass |
| 9 | CRUD | Supplier CRUD | Add, rename, search, delete a supplier | Each step succeeds | As expected (automated test) | Pass |
| 10 | CRUD | Persistence | Close and reopen the database file | Saved records are still there | As expected (automated test) | Pass |
| 11 | Security | SQL injection text | Search for `'; DROP TABLE medicines; --` | Treated as plain text; table still exists | As expected (automated test) | Pass |
| 12 | Stock | Receive stock | Receive 50 units with a valid expiry date | Batch created, stock = 50, RECEIVED movement logged | As expected (automated test) | Pass |
| 13 | Stock | Issue stock | Issue 5 from a batch of 50 | Quantity becomes 45 | As expected (automated test) | Pass |
| 14 | Stock | Issue too much | Issue 51 from a batch of 50 | Rejected; quantity stays 50 | As expected (automated test) | Pass |
| 15 | Stock | Adjustment needs a reason | Adjust down without a reason, then with one | First rejected, second accepted (48 left) | As expected (automated test) | Pass |
| 16 | Stock | Delete batch | Delete a batch | Batch and its movement history removed | As expected (automated test) | Pass |
| 17 | Stock | Expired stock not usable | A batch that expired yesterday (30 units) | Usable stock 0, expired stock 30, status OUT | As expected (automated test) | Pass |
| 18 | Rules | Expiry boundaries | Dates -1, 0, 30, 31, 60, 61, 90, 91 days from today | Expired / 30 / 30 / 60 / 60 / 90 / OK classification | As expected (automated test) | Pass |
| 19 | Rules | Stock status | Usable stock 0, 10, 11 with reorder level 10 | OUT / LOW / OK | As expected (automated test) | Pass |
| 20 | Rules | Batch filters and dashboard | Batches expiring in -2, 10, 50, 300 days | Filters, dashboard counts and alert order are correct | As expected (automated test) | Pass |
| 21 | Validation | Required medicine names | Blank brand and generic names | Two error messages, nothing saved | As expected (automated test) | Pass |
| 22 | Validation | Bad numbers | Reorder level 'abc' or -1; unit cost 'free' or -5 | Each rejected with a message | As expected (automated test) | Pass |
| 23 | Validation | Defaults and trimming | '  Biogesic ' with no reorder level | Spaces trimmed, reorder level defaults to 10 | As expected (automated test) | Pass |
| 24 | Validation | Quotes in generic name | Generic name `bad"name` | Rejected (protects the API search) | As expected (automated test) | Pass |
| 25 | Validation | Supplier phone and name | '0917 123 4567', 'call me', blank name | Valid number accepted; others rejected | As expected (automated test) | Pass |
| 26 | Validation | Incomplete batch | No medicine, blank batch no., quantity 0, date 2025-13-45 | At least four error messages | As expected (automated test) | Pass |
| 27 | Validation | Expired / wrong-order dates | Expiry in the past; expiry before date received | Both rejected | As expected (automated test) | Pass |
| 28 | Validation | Valid batch | Valid batch with no supplier | Accepted; supplier is empty | As expected (automated test) | Pass |
| 29 | Validation | Movement input | Type RECEIVED, quantity 0, quantity 2 | First two rejected, last accepted | As expected (automated test) | Pass |
| 30 | API | API success | Fetch 'ibuprofen' (mocked 200 response) | JSON parsed; brand, indications, warnings shown; correct query and 10 s timeout sent | As expected (automated test) | Pass |
| 31 | API | Drug not found (404) | Fetch 'paracetamol' (mocked 404) | Friendly 'no label found' message mentioning U.S. generic names | As expected (automated test) | Pass |
| 32 | API | Empty results | 200 response with an empty list | 'No results' message | As expected (automated test) | Pass |
| 33 | API | Rate limit (429) | Service answers 429 | 'Too many requests' message | As expected (automated test) | Pass |
| 34 | API | Server error (500) | Service answers 500 | Message shows HTTP 500 | As expected (automated test) | Pass |
| 35 | API | Timeout | Request times out (also a connect timeout) | 'Took too long' message | As expected (automated test) | Pass |
| 36 | API | No internet | Connection error | 'Check your internet connection' message | As expected (automated test) | Pass |
| 37 | API | Invalid JSON | 200 response that is not JSON | 'Could not be read' message | As expected (automated test) | Pass |
| 38 | API | Label without text | Label has no usable sections | Friendly message, no crash | As expected (automated test) | Pass |
| 39 | API | Blank generic name | Click lookup with an empty name | No request is sent | As expected (automated test) | Pass |
| 40 | File | CSV export | Export medicines, batches, movements | Files created with headers and correct rows | As expected (automated test) | Pass |
| 41 | File | Expiry report | Report for 30 days with batches at -1, 20, 200 days | Only the 2 batches in the window are exported | As expected (automated test) | Pass |
| 42 | File | Missing folder | Export to a folder that does not exist | 'Folder does not exist' message | As expected (automated test) | Pass |
| 43 | File | Permission denied | Export to a read-only folder | 'Permission denied' message | Skipped in the build environment (it ran as root); run it on your computer | Run locally |
| 44 | File | CSV import | File with 1 good row, 1 duplicate, 1 missing brand, 1 bad number | 1 added, 3 skipped, 3 line-numbered errors | As expected (automated test) | Pass |
| 45 | File | Bad import files | Wrong columns; missing file; empty file; binary file | Friendly error for each, no crash | As expected (automated test) | Pass |
| 46 | File | Template round trip | Save template, then import it | 1 medicine imported | As expected (automated test) | Pass |
| 47 | GUI | Form validation message | Click Add with an empty form | Warning lists 'Brand name is required' | As expected (automated test) | Pass |
| 48 | GUI | Add / search / update / delete | Use the Medicines tab controls | Table and form behave correctly | As expected (automated test) | Pass |
| 49 | GUI | Receive and issue stock | Stock tab: batch expiring in 10 days, issue 5 | Row shows 40 units with expiring colour; 35 after issuing | As expected (automated test) | Pass |
| 50 | GUI | Dashboard and tabs | Switch through every tab | No errors; alert counts correct | As expected (automated test) | Pass |
| 51 | GUI | Drug info success and failure | Simulate a successful and a failed lookup | Text shown and saved; warning on failure; button re-enabled | As expected (automated test) | Pass |

## Manual tests (fill in on your own computer)

These need the real internet connection or a person at the keyboard, so they were not run in the build environment.

| No. | Test Case | Test Input / Action | Expected Result | Actual Result | Pass/Fail |
| --- | --- | --- | --- | --- | --- |
| 52 | Live openFDA success | Medicines tab: select a medicine with generic name `ibuprofen`, click Get Drug Info | Label text appears and is saved with the medicine | | |
| 53 | Live openFDA not found | Select a medicine with generic name `paracetamol`, click Get Drug Info | 'No drug label was found' warning | | |
| 54 | Disconnected internet | Turn off Wi-Fi, click Get Drug Info | 'Check your internet connection' warning; app stays responsive | | |
| 55 | Export opens in Excel | Reports tab: export medicines, open in Excel | Columns display correctly | | |
| 56 | Restart persistence | Add a medicine, close the app, reopen it | Medicine is still listed | | |
