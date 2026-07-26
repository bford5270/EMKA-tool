# web/

React front end (Vite + React + Tailwind 4). Sources are primary: verbatim
cited passages render first, the synthesized answer second and visibly
subordinate with its machine-verification status.

Features: persistent no-PHI banner; authority-tier badges and edition date on
every citation; tap-to-open PDF at the cited page; unit-shelf sources
watermarked "unit-added, not custodian-verified" in a distinct color;
conflicting sources rendered side by side under a "these sources differ"
flag; loadout availability notes with stale-data warnings; a "flag this
answer" control that posts to the maintainer queue. All state is in memory —
no browser storage of anything.

## Run

```
make serve   # FastAPI on 127.0.0.1:8000 (separate terminal)
make web     # Vite dev server, proxies /query /flag /source /health
```

`npm run build` emits a static bundle in `dist/` for serving from the device.
