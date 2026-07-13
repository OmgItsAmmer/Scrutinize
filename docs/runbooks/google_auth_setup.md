# Runbook: Setting Up Google Authentication Flow

This document details the configuration required in the Google Cloud Console and application environment to support Google OAuth 2.0.

---

## Step 1: Configure Google Cloud Console

1. **Go to Google Cloud Console**:
   Open [Google Cloud Console Credentials Page](https://console.cloud.google.com/apis/credentials).

2. **Select or Create a Project**:
   Ensure you are working within the correct Google Cloud Project.

3. **Configure OAuth Consent Screen** (if not already done):
   * Select **External** (unless you want to restrict login solely to Google Workspace members inside your own organization).
   * Fill out the app name (e.g., `Scrutinize`), user support email, and developer contact information.
   * Add the scope `.../auth/userinfo.email` and `.../auth/userinfo.profile`.
   * Under **Test users**, add the email addresses you want to use for testing before publishing the app.

4. **Create OAuth Client Credentials**:
   * Navigate to **Credentials** -> Click **+ Create Credentials** -> Select **OAuth client ID**.
   * Choose **Web application** as the application type.
   * Set the name (e.g., `Scrutinize Web`).
   * Add **Authorized JavaScript origins**:
     * `http://localhost:5173` (for frontend dev server)
     * Production domain (e.g., `https://scrutinize.fly.dev` or custom domains)
   * Add **Authorized redirect URIs** (only needed if using server-side redirects, but good to add for standard setups):
     * `http://localhost:5173`
   * Click **Create**.
   * Note down the generated **Client ID** (looks like `YOUR_CLIENT_ID.apps.googleusercontent.com`).

---

## Step 2: Update Application Settings & Environment Variables

### 1. Backend Configuration
Update your `.env` file (at the repository root or backend folder):

```env
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
```

### 2. Frontend Configuration
Add the client ID to the frontend environment. Create or modify `frontend/.env`:

```env
VITE_GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
```

---

## Step 3: Run Database Migrations

Apply the migration to make `password_hash` nullable in the database:

```powershell
python scripts/apply_migrations.py
```

Verify that the `011_google_auth.sql` migration runs and successfully alters the `users` table.

---

## Step 4: Verification

1. Start both the backend and frontend servers.
2. Navigate to the login page on the frontend.
3. Click the Google Sign-in button.
4. Complete the authorization. Upon success, you will be redirected to the main dashboard and a default project named `"My First Project"` will be automatically set up if this is your first sign-in.
