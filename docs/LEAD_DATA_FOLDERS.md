# Lead Data Folder Discipline

Real lead files must stay local and must not be committed.

Use these local folders under `data/`, which is already ignored by Git:

- `data/raw_leads` for original operator files.
- `data/samples` for synthetic sample files only.
- `data/processed` for local processed copies.
- `data/import_reports` for local exported import reports.

The application import endpoint is dry-run by default. A commit requires an approved `import_commit` approval and never sends customer outreach.
