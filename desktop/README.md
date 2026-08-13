# BioStonk Desktop Builds

Build both desktop packages from this directory:

```bash
npm install
npm run build
```

Upload the generated files to the `desktop` folder in Firebase Storage using
these exact object names:

- `desktop/BioStonk-macOS.dmg`
- `desktop/BioStonk-Windows.zip`

Deploy the scoped public-download rules with:

```bash
firebase deploy --only storage --project biostonk
```

The macOS package targets Apple silicon. The Windows ZIP targets 64-bit Windows;
users extract it and run `BioStonk.exe` with the other packaged files present.