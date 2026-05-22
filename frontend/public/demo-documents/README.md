# Resolvly demo documents

Place sample PDFs here so visitors can try analysis without uploading their own files.

## Folder layout

Each **case** is a folder with exactly three files (fixed names):

```
demo-documents/
  case-default/
    denial.pdf          ← Denial letter
    eob.pdf             ← Explanation of benefits
    medical-bill.pdf    ← Medical bill / itemized statement
  case-fontaine/
    denial.pdf
    eob.pdf
    medical-bill.pdf
  case-nguyen/
    denial.pdf
    eob.pdf
    medical-bill.pdf
```

## Adding or replacing files

1. Pick a case folder (or create a new one, e.g. `case-myname/`).
2. Drop in three PDFs using the names above.
3. Register the case in `src/lib/demoDocuments.ts` (`DEMO_CASES`).

Files are served from `/demo-documents/...` in dev and production (Vite `public/`).

## Current sets (pre-loaded)

| Folder          | Description              |
|-----------------|--------------------------|
| `case-default`  | Original sample trio     |
| `case-fontaine` | Fontaine demo set        |
| `case-nguyen`   | Nguyen demo set          |
