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

## Login gate

The clinical UI now requires authentication before showing the dashboard.

### Demo login (default)

A built-in demo account is active by default and works without any Firebase configuration:

- **Username:** `pharmachute`
- **Password:** `123`

The demo session persists across page refreshes using `localStorage`.

### Enabling Firebase Authentication

To replace the demo account with real Google and email/password sign-in, enable Firebase Auth providers and add the project's web config.

1. In the [Firebase Console](https://console.firebase.google.com/project/biostonk/authentication), go to **Authentication** → **Sign-in method**.
2. Enable **Email/Password** and **Google**.
3. Go to **Authentication** → **Settings** → **Authorized domains** and add:
   - `localhost`
   - `biostonk.web.app`
4. Go to **Project settings** → **General** → **Your apps**, create a Web app if needed, and copy the Firebase config object.
5. Paste the config into `clinical/static/auth.js`:

```js
const AUTH_CONFIG = {
  demo: { ... },
  firebase: {
    apiKey: "YOUR_API_KEY",
    authDomain: "biostonk.firebaseapp.com",
    projectId: "biostonk",
    storageBucket: "biostonk.appspot.com",
    messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
    appId: "YOUR_APP_ID",
  },
};
```

Once `apiKey` is set, `auth.js` automatically switches from demo mode to Firebase Auth.

## GitHub Actions deploy

The workflow in `.github/workflows/firebase-hosting-deploy.yml` deploys on pushes to `main` when static files or Firebase config change.

Required repository secret:

- `FIREBASE_SERVICE_ACCOUNT_BIOSTONK`: JSON service account key with Firebase Hosting deploy access.
