# Clinical Trial Data

`import_trials.py` converts the tracked `data/Emde/` `.xlsx` workbooks containing `nct_id`, `emb_0` through
`emb_127`, and binary `sentiment` labels (`0.0` or `1.0`) into a compressed
`trials.npz` dataset. The generated dataset remains untracked.

Install the importer dependencies and run it against the attached data folder:

```bash
venv/bin/python -m pip install -r clinical/requirements.txt
venv/bin/python clinical/import_trials.py clinical/data/Emde
```

The output contains trial IDs, a `float32` embedding matrix (`X`), integer labels
(`y`), matching label names, and `source_workbook`. NCT IDs may occur in multiple
workbooks because each source is a separate annotation set; the importer retains
every valid source row. It rejects missing columns, incomplete embedding rows,
and malformed non-binary sentiment labels, reporting skipped rows for review.

## Similarity Retrieval

`trial_search.py` performs local cosine-similarity retrieval over the generated
dataset. It accepts a known `nct_id` and returns comparable trial records with
their sentiment label and source workbook. This is the initial evidence-retrieval
component; it does not yet claim clinical comparability beyond embedding
similarity.

Run the API after generating `trials.npz`:

```bash
venv/bin/uvicorn clinical.api:app --reload
```

For example, `GET /trials/NCT05071248/comparables?limit=10` returns the nearest
stored trial embeddings along with their source provenance.