# Firebase Hosting Setup

This repository can deploy the clinical UI at [https://biostonk.web.app](https://biostonk.web.app).

## Local deploy

1. Install Firebase CLI.
2. Authenticate and select the project.
3. Deploy Hosting.

```bash
firebase login
firebase use biostonk
firebase deploy --only hosting
```

## Hosting root

- Hosting site: `biostonk`
- Public directory: `clinical`
- UI entry path: `/static/index.html`

Only static files in `clinical/static` should be deployed. Python sources and dataset artifacts are excluded by `firebase.json` and `.firebaseignore`.

## GitHub Actions deploy

The workflow in `.github/workflows/firebase-hosting-deploy.yml` deploys on pushes to `main` when static files or Firebase config change.

Required repository secret:

- `FIREBASE_SERVICE_ACCOUNT_BIOSTONK`: JSON service account key with Firebase Hosting deploy access.
