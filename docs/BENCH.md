### v0 baseline — 1/7 correct

| Invoice | Seeded | Expected | Actual | Time | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `acme-corp_000` | clean | auto_approve | hold | 6.6s | MISS |
| `acme-corp_001` | duplicate | reject | hold | 2.9s | MISS |
| `acme-corp_002` | clean | auto_approve | hold | 6.1s | MISS |
| `acme-corp_003` | clean | auto_approve | hold | 2.9s | MISS |
| `acme-corp_004` | price_variance | hold | hold | 5.7s | OK |
| `acme-corp_005` | clean | auto_approve | hold | 5.4s | MISS |
| `acme-corp_006` | clean | auto_approve | hold | 5.6s | MISS |


## hand-built loop vs create_agent

| implementation | policy acc | investigated | agent agreed | unparsed | wall clock | per invoice |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| handbuilt | 10/20 | 3 | 1/3 | 0 | 8.4s | 0.4s |
| harness | 10/20 | 3 | 2/3 | 0 | 8.7s | 0.4s |