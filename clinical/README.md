# Clinical Trial Data

`import_trials.py` converts `.xlsx` workbooks containing `nct_id`, `emb_0` through
`emb_127`, and binary `sentiment` labels (`0.0` or `1.0`) into a compressed
`trials.npz` dataset. Raw workbooks remain outside the repository because they
are large source data.

Install the importer dependencies and run it against the attached data folder:

```bash
venv/bin/python -m pip install -r clinical/requirements.txt
venv/bin/python clinical/import_trials.py /Users/kevinguillermo/Downloads/Emde
```

The output contains trial IDs, a `float32` embedding matrix (`X`), integer labels
(`y`), matching label names, and `source_workbook`. NCT IDs may occur in multiple
workbooks because each source is a separate annotation set; the importer retains
every valid source row. It rejects missing columns, incomplete embedding rows,
and malformed non-binary sentiment labels, reporting skipped rows for review.