/**
 * BioStonk authentication gate.
 *
 * Supports a built-in demo login (username/password) and Firebase Auth
 * (Google + email/password). Additional profile data is stored in Firestore.
 * Demo mode is active by default; Firebase Auth is enabled once a project web
 * config is added below.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const AUTH_CONFIG = {
  demo: {
    username: "pharmachute",
    password: "123",
    storageKey: "biostonk_demo_session",
  },
  // Paste your Firebase project web app config here to enable real auth.
  // Leave apiKey as null to stay in demo mode.
  firebase: {
    apiKey: "AIzaSyAPb1zfqmLAL_yJu_XFDHXFANf5VaxMMCU",
    authDomain: "biostonk.firebaseapp.com",
    projectId: "biostonk",
    storageBucket: "biostonk.firebasestorage.app",
    messagingSenderId: "559267443625",
    appId: "1:559267443625:web:811a6ce247890464214ab8",
  },
};

// ---------------------------------------------------------------------------
// Demo auth provider (localStorage-backed, always available fallback)
// ---------------------------------------------------------------------------

class DemoAuth {
  constructor(config) {
    this.config = config;
    this.currentUser = null;
  }

  init() {
    const raw = localStorage.getItem(this.config.storageKey);
    if (!raw) return false;
    try {
      const session = JSON.parse(raw);
      if (session && session.authenticated) {
        this.currentUser = this.userRecord();
        return true;
      }
    } catch {
      // corrupt session
    }
    localStorage.removeItem(this.config.storageKey);
    return false;
  }

  login(username, password) {
    if (username === this.config.username && password === this.config.password) {
      this.currentUser = this.userRecord();
      localStorage.setItem(
        this.config.storageKey,
        JSON.stringify({ authenticated: true, timestamp: Date.now() })
      );
      return { success: true, user: this.currentUser };
    }
    return { success: false, error: "Invalid username or password." };
  }

  logout() {
    this.currentUser = null;
    localStorage.removeItem(this.config.storageKey);
  }

  userRecord() {
    return {
      uid: "demo-user",
      email: "demo@pharmachute.com",
      displayName: "Demo User",
      provider: "demo",
    };
  }
}

// ---------------------------------------------------------------------------
// Firebase SDK loader
// ---------------------------------------------------------------------------

class FirebaseServices {
  constructor(config) {
    this.config = config;
    this.app = null;
    this.auth = null;
    this.db = null;
    this.functions = null;
    this.googleProvider = null;
  }

  isConfigured() {
    return Boolean(this.config.apiKey);
  }

  async load() {
    if (this.app) return this;

    const [{ initializeApp }, firebaseAuth, firebaseFirestore] = await Promise.all([
      import("https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js"),
      import("https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js"),
    ]);

    const { getAuth, GoogleAuthProvider, onAuthStateChanged, signOut } = firebaseAuth;
    const { getFirestore, doc, setDoc, serverTimestamp } = firebaseFirestore;

    this.app = initializeApp(this.config);
    this.auth = getAuth(this.app);
    this.db = getFirestore(this.app);
    this.googleProvider = new GoogleAuthProvider();

    this.functions = {
      signInWithPopup: firebaseAuth.signInWithPopup,
      signInWithEmailAndPassword: firebaseAuth.signInWithEmailAndPassword,
      createUserWithEmailAndPassword: firebaseAuth.createUserWithEmailAndPassword,
      updateProfile: firebaseAuth.updateProfile,
      signOut,
      onAuthStateChanged,
      doc,
      setDoc,
      serverTimestamp,
    };

    return this;
  }
}

// ---------------------------------------------------------------------------
// Firestore user profile store
// ---------------------------------------------------------------------------

class UserProfileStore {
  constructor(services) {
    this.services = services;
  }

  async create(uid, { name, email }) {
    const { doc, setDoc, serverTimestamp } = this.services.functions;
    const userRef = doc(this.services.db, "users", uid);
    await setDoc(userRef, {
      name: name || "",
      email: email || "",
      createdAt: serverTimestamp(),
    });
  }
}

// ---------------------------------------------------------------------------
// Firebase auth provider
// ---------------------------------------------------------------------------

class FirebaseAuthProvider {
  constructor(config) {
    this.config = config;
    this.services = new FirebaseServices(config);
    this.profileStore = null;
    this.unsubscribe = null;
  }

  isConfigured() {
    return this.services.isConfigured();
  }

  async init(onStateChange) {
    if (!this.isConfigured()) {
      throw new Error("Firebase web config is not set in auth.js");
    }

    await this.services.load();
    this.profileStore = new UserProfileStore(this.services);

    this.unsubscribe = this.services.functions.onAuthStateChanged(
      this.services.auth,
      (user) => onStateChange(user)
    );
  }

  async signInWithGoogle() {
    try {
      const { user } = await this.services.functions.signInWithPopup(
        this.services.auth,
        this.services.googleProvider
      );
      return { success: true, user };
    } catch (error) {
      return { success: false, error: this.formatError(error) };
    }
  }

  async signInWithEmail(email, password) {
    try {
      const { user } = await this.services.functions.signInWithEmailAndPassword(
        this.services.auth,
        email,
        password
      );
      return { success: true, user };
    } catch (error) {
      return { success: false, error: this.formatError(error) };
    }
  }

  async createAccount(email, password, name) {
    try {
      const { user } = await this.services.functions.createUserWithEmailAndPassword(
        this.services.auth,
        email,
        password
      );

      if (name) {
        await this.services.functions.updateProfile(user, { displayName: name });
      }

      await this.profileStore.create(user.uid, { name, email });

      return { success: true, user };
    } catch (error) {
      return { success: false, error: this.formatError(error) };
    }
  }

  async logout() {
    if (this.services.auth) {
      await this.services.functions.signOut(this.services.auth);
    }
  }

  formatError(error) {
    const map = {
      "auth/user-not-found": "No account found with this email.",
      "auth/wrong-password": "Incorrect password.",
      "auth/invalid-email": "Please enter a valid email address.",
      "auth/weak-password": "Password should be at least 6 characters.",
      "auth/email-already-in-use": "An account already exists with this email.",
      "auth/popup-closed-by-user": "Sign-in popup closed before completing.",
      "auth/cancelled-popup-request": "Sign-in popup was cancelled.",
      "auth/account-exists-with-different-credential":
        "An account already exists with the same email using different credentials.",
      "auth/network-request-failed": "Network error. Please check your connection.",
      "auth/invalid-credential": "Invalid email or password.",
      "auth/configuration-not-found":
        "Firebase Authentication is not enabled for this project or provider.",
      "permission-denied":
        "Firestore permission denied. Check your Firestore security rules.",
    };
    return map[error.code] || error.message || "An error occurred during sign in.";
  }
}

// ---------------------------------------------------------------------------
// Auth manager
// ---------------------------------------------------------------------------

class AuthManager {
  constructor() {
    this.demo = new DemoAuth(AUTH_CONFIG.demo);
    this.firebase = new FirebaseAuthProvider(AUTH_CONFIG.firebase);
    this.mode = "demo";
    this.onChange = null;
  }

  async init(onChange) {
    this.onChange = onChange;

    if (this.firebase.isConfigured()) {
      try {
        await this.firebase.init((user) => {
          if (user) this.mode = "firebase";
          onChange(user);
        });
        this.mode = "firebase";
        return;
      } catch (error) {
        // eslint-disable-next-line no-console
        console.warn("Firebase auth initialization failed, using demo mode:", error.message);
      }
    }

    this.mode = "demo";
    const demoActive = this.demo.init();
    onChange(demoActive ? this.demo.userRecord() : null);
  }

  async demoLogin(username, password) {
    const result = this.demo.login(username, password);
    if (result.success) {
      this.mode = "demo";
      this.onChange(result.user);
    }
    return result;
  }

  async firebaseGoogleLogin() {
    const result = await this.firebase.signInWithGoogle();
    if (result.success) this.onChange(result.user);
    return result;
  }

  async firebaseEmailLogin(email, password) {
    const result = await this.firebase.signInWithEmail(email, password);
    if (result.success) this.onChange(result.user);
    return result;
  }

  async firebaseCreateAccount(email, password, name) {
    const result = await this.firebase.createAccount(email, password, name);
    if (result.success) this.onChange(result.user);
    return result;
  }

  async logout() {
    if (this.mode === "firebase" && this.firebase.isConfigured()) {
      await this.firebase.logout();
      // onAuthStateChanged will call onChange(null)
    } else {
      this.demo.logout();
      this.onChange(null);
    }
  }
}

const authManager = new AuthManager();

// ---------------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------------

function getValue(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}

function setError(id, message) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message || "";
  el.hidden = !message;
}

function updateAuthUI(user) {
  const loginShell = document.getElementById("login-shell");
  const dashboardShell = document.getElementById("dashboard-shell");
  const userDisplay = document.getElementById("user-display");

  if (!loginShell || !dashboardShell) return;

  if (user) {
    loginShell.classList.add("hidden");
    dashboardShell.classList.remove("hidden");
    if (userDisplay) {
      userDisplay.textContent = user.displayName || user.email || "Authenticated";
    }
    if (typeof window.onBiostonkAuthenticated === "function") {
      window.onBiostonkAuthenticated(user);
    }
  } else {
    loginShell.classList.remove("hidden");
    dashboardShell.classList.add("hidden");
    if (userDisplay) userDisplay.textContent = "";
    setError("demo-login-error", "");
    setError("create-account-error", "");
  }
}

function attachDemoLogin() {
  const demoForm = document.getElementById("demo-login-form");
  if (!demoForm) return;

  demoForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setError("demo-login-error", "");
    const result = await authManager.demoLogin(
      getValue("demo-username"),
      getValue("demo-password")
    );
    if (!result.success) setError("demo-login-error", result.error);
  });
}

function attachCreateAccount() {
  const googleButton = document.getElementById("google-signin-button");
  if (googleButton) {
    googleButton.addEventListener("click", async () => {
      setError("create-account-error", "");
      const result = await authManager.firebaseGoogleLogin();
      if (!result.success) setError("create-account-error", result.error);
    });
  }

  const createAccountForm = document.getElementById("create-account-form");
  if (createAccountForm) {
    createAccountForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      setError("create-account-error", "");
      const result = await authManager.firebaseCreateAccount(
        getValue("create-account-email"),
        getValue("create-account-password"),
        getValue("create-account-name")
      );
      if (!result.success) setError("create-account-error", result.error);
    });
  }
}

function attachSignOut() {
  const signOutButton = document.getElementById("sign-out-button");
  if (signOutButton) {
    signOutButton.addEventListener("click", async () => {
      await authManager.logout();
    });
  }
}

function initAuthUI() {
  authManager.init(updateAuthUI);
  attachDemoLogin();
  attachCreateAccount();
  attachSignOut();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAuthUI);
} else {
  initAuthUI();
}
