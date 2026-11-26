# Evaluation datasets — never ingest anything in this folder

| Folder | What | Who sees it |
|---|---|---|
| `dev/` | `teammind_eval_v1.1.jsonl` (+ `.csv`): 222 questions with gold answers | Builder. Use it for tuning and quick checks. |
| `test/` | Hidden test questions written by Teammates A and B (Feb 2027) | Teammates only, until the final run. Use it only for final results. |
| `tricks/` | 4 prompt-injection documents (`INJ_01`–`INJ_04`) | Upload them only during injection tests, never into the team collections. |

## Fields in `dev/teammind_eval_v1.1.jsonl`

- **`id`**: question ID.
- **`target_collection`** (`shared`, `dev`, `sales`, `social`): the collection whose data the question is about.
- **`asker_team`** (`dev`, `sales`, `social`, `any`): the team of the user asking. When it differs from `target_collection`, it is a cross-team question.
- **`type`**: one of `in_scope`, `table`, `multi_hop`, `temporal`, `style`, `confidential_probe`, `cross_team_allowed`, `cross_team_denied`, `leakage_probe`, `out_of_scope`, `injection`.
- **`expected_behavior`**: one of `answer`, `answer_without_confidential`, `draft_for_approval`, `refuse`, `say_unknown`, `ignore_injection`.
- **`gold_answer`**: the reference answer.
- **`key_facts`**: facts a correct answer must contain.
- **`forbidden_facts`**: facts the answer and the retrieved context must not contain (leakage canaries and superseded values).
- **`evidence`**: exact text in the source document.
- **`acceptable_sources`**: every current corpus file that contains the evidence. Use it for hit rate and recall@k.
- **`note`**: extra context for the question.

Readable Word versions are in `../../docs/eval_readable/`.
