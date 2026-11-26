# TeamMind corpus — dataset v1.1

Fictional company: Nimbleleaf Software (see `../company_description.md`). Not a real company's records.

## Folders

| Folder | Chroma collection | Who can retrieve | Files |
|---|---|---|---|
| `shared/` | `shared` | every team | 1 (company overview) |
| `dev/` | `team_dev` | Development | 12 |
| `sales/` | `team_sales` | Sales | 13 |
| `social/` | `team_social` | Social Media | 12 |

`manifest.csv` has one row per file. Its columns are `source_file`, `collection`, `chroma_collection`, `access`, `document_title`, `document_date`, `writer`, `classification`, `doc_status`, `illustrative_data`, `has_confidential_paragraphs`, `whole_document_restricted` and `words`. Attach these to every chunk as metadata.

## Special documents

- **Superseded** (`doc_status=superseded`): `dev/11`, `sales/13` and `social/10` contain old, wrong values on purpose, for example Standard at PKR 2,000 and the `#DukaanSmart` hashtag. Exclude them from retrieval by default.
- **Illustrative** (`illustrative_data=yes`): `sales/12`, `social/11` and `social/12` hold synthetic figures. Any answer that uses them must say they are illustrative.
- **Newer records override older ones**:
  - `dev/12` confirms v3.3 shipped on January 18, 2027, while older files still say "scheduled". It also moves the RC review to January 27.
  - `social/12` moves a TikTok post from February 18 to February 19.

## Confidential content

- Each paragraph starting `CONFIDENTIAL —` should become its own chunk with `confidential=true`.
- `dev/09` is RESTRICTED, so every chunk from it is confidential.
- Confidential chunks can be used for the owning team's own members. They are never used in a cross-team answer or a client-facing draft.
- The labels are data only. The backend must enforce access.

## Loading notes

- Remove the repeated header lines (company name and disclaimer sentence) before embedding.
- Tables: turn each row into text with its headers, for example `Field: value; Field: value`.
- Build one BM25 index per collection, never one across teams.

All invented values are listed in `../../docs/governance/TeamMind_Master_Fact_and_Extension_Register.docx`.
