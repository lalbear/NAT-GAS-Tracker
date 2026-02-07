
# Google Cloud Platform (GCP) Setup Guide

Follow these steps exactly to generate the credentials needed for the automation.

## Step 1: Create a Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Sign in with your Google Account.
3. In the top-left (next to the Google Cloud logo), click the dropdown menu (it might say "Select a project").
4. Click **New Project** (top right of the popup).
5. **Project Name**: Enter `ETF-Tracker` (or similar).
6. Click **Create**.
7. Wait a few seconds, then click **Select Project** from the notification bell or the top dropdown.

## Step 2: Enable Google Sheets API
1. In the search bar at the very top, type: `Google Sheets API`.
2. Click on "Google Sheets API" (Marketplace).
3. Click the blue **ENABLE** button.
4. Wait for it to finish loading.

## Step 3: Create a Service Account
1. In the top-left menu (Navigation Menu / Burger icon), go to **IAM & Admin** > **Service Accounts**.
2. Click **+ CREATE SERVICE ACCOUNT** (top center).
3. **Service account details**:
   - **Name**: `etf-tracker`.
   - Click **Create and Continue**.
4. **Grant access to project**:
   - Click "Select a role".
   - Choose **Basic** > **Editor**.
   - Click **Continue**.
5. Click **Done**.

## Step 4: Generate the Key (JSON)
1. You should now see your service account in the list (e.g., `etf-tracker@etf-tracker-123.iam.gserviceaccount.com`).
2. Click on the **Email address** link.
3. Click the **KEYS** tab (top menu bar, usually the 3rd or 4th tab).
4. Click **ADD KEY** > **Create new key**.
5. Select **JSON** (Radio button).
6. Click **CREATE**.
7. A file will automatically download to your computer (e.g., `etf-tracker-123456789.json`).
   - **KEEP THIS FILE SAFE.** This is your `GCP_SA_KEY`.

## Step 5: Share your Google Sheet
1. Open your downloaded JSON key file using a text editor (Notepad, TextEdit, VS Code).
2. Look for the field `"client_email"`. It looks like: `"etf-tracker@etf-tracker-123.iam.gserviceaccount.com"`.
3. **Copy** that email address.
4. Go to your **Google Sheet** in your browser.
5. Click the big green **Share** button (top right).
6. **Paste** the email address you copied.
7. Ensure "Editor" is selected.
8. Click **Send**.
   - *Note: Uncheck "Notify people" if you don't want an email bounce setup, but it doesn't matter much.*

## Step 6: Add to GitHub
1. Copy the **entire contents** of your JSON file.
2. Go to your GitHub Repo > Settings > Secrets and variables > Actions.
3. creates a New Secret named `GCP_SA_KEY` and paste the content.
