# Daily Airline Discovery ✈️

![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI/CD-blue)
![Azure](https://img.shields.io/badge/Azure-Container%20Instances%20|%20Container%20Registry%20|%20Files%20|%20Logic%20Apps-blue)

This project automatically sends a daily email featuring a random airline from around the world. Each email includes:
- Airline name, IATA code, founding year, country, and base.
- Fleet size and composition.
- A list of all destinations served by the airline (with airport codes, city names, and country codes).
- Airline logo (if available).

The system is fully containerised and runs on **Azure**, using GitHub Actions for continuous deployment. Every push to the repository triggers a rebuild of the Docker image and an update of the Azure Container Instance.

---

## 🎯 Purpose

The goal is to learn about different airlines every day, a fun way to discover aviation facts. It also serves as a practical example of combining multiple cloud services:
- **Azure Container Instances** – serverless execution of the Python script.
- **Azure Files** – persistent storage to track which airlines have already been featured.
- **Azure Container Registry** – private storage for the Docker image.
- **Azure Logic Apps** – scheduled trigger to run the container daily.
- **GitHub Actions** – CI/CD pipeline to rebuild and redeploy on code changes.

---

## 🧱 Architecture

![Architecture Diagram](docs/rg_exp.svg)

1. **GitHub Actions** listens for pushes to the main branch.
2. It builds a new Docker image and pushes it to **Azure Container Registry** (ACR).
3. It deletes the existing **Azure Container Instance** (if any) and creates a new one with the updated image.
4. The container, when run,:
   - Fetches a random airline from [API-Ninjas Airlines API](https://api-ninjas.com/api/airlines).
   - Gets its destinations from [Amadeus for Developers](https://developers.amadeus.com/).
   - Generates an HTML email and sends it via **Mailgun API** (can be adapted for other email providers like Brevo, SendGrid, or SMTP).
   - Records the airline’s IATA code in an **Azure Files** share to avoid repetition.
5. **Azure Logic Apps** (configured separately) triggers the container group once per day.

---

## ☁️ Azure Resources Needed

| Resource | Purpose | Why It's Needed |
|----------|---------|-----------------|
| **Azure Container Registry (ACR)** | Store the Docker image. | Securely host the custom image used by ACI. |
| **Azure Container Instances (ACI)** | Run the Python script. | Serverless container execution. Pay only when the script runs. |
| **Azure Files** | Persist `sent_airlines.json`. | The container is ephemeral; this share ensures the list of already-used airlines is preserved between runs. |
| **Azure Logic Apps** | Schedule daily execution. | ACI has no built-in scheduler; Logic Apps provides a reliable, low-cost trigger. |
| **Resource Group** | Logical container for all resources. | Organises and manages permissions together. |

Optionally, you can also use a **self-hosted GitHub Actions runner** on a small Azure VM if you cannot create a service principal (see [alternative setup](docs/setup.md)).

---

## 💰 Cost Considerations

The solution is designed to be very cheap. Estimated monthly cost:

| Service | Configuration | Estimated Monthly Cost |
|---------|---------------|------------------------|
| ACI | 1 vCPU, 1.5 GB RAM, runs ~5 min/day | **$0.15 – $0.20** |
| ACR | Basic tier, one image | **~$5** (if you keep the image; many use free tier elsewhere) |
| Azure Files | 1 GB LRS | **$0.10** |
| Logic Apps | Consumption plan, 1 run/day | **$0.00** (free tier) |
| **Total** | | **~$0.30 – $0.50** (plus ACR if not in free tier) |

> 💡 **Tip**: You can minimise ACR cost by deleting old images and only keeping the latest. See [ACR cleanup instructions](docs/acr-cleanup.md).

---

## 🔑 Required API Keys & Accounts

### 1. **API-Ninjas** (Airline data)
- Go to [api-ninjas.com](https://api-ninjas.com/)
- Sign up and get a free API key (50,000 requests/month).
- Required environment variable: `NINJAS_API_KEY`.

### 2. **Amadeus for Developers** (Destination data)
- Register at [developers.amadeus.com](https://developers.amadeus.com/)
- Create a new application and get `Client ID` and `Client Secret` (Self-Service API, Test environment is free).
- Required variables: `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET`.

### 3. **Email provider**
You need an email service to send the daily message. The script is pre-configured for **Mailgun API**, but it can be adapted for other providers:

- **Mailgun** (free: 100 emails/day) – sign up at [mailgun.com](https://www.mailgun.com/), verify a domain (or use the sandbox), and generate an API key.
- **Brevo** (formerly Sendinblue) – free: 300 emails/day, SMTP or API.
- **SendGrid** – free: 100 emails/day, API.
- Any SMTP provider can be used with minor code changes.

For Mailgun you will need:
- `MAILGUN_DOMAIN` – your verified domain (e.g., `mg.yourdomain.com`).
- `SENDER_EMAIL` – a verified sender address from that domain.
- `SENDER_APP_PASSWORD` – the Mailgun API key (starts with `key-`).

### 4. **Azure Subscription**
- You’ll need an active Azure subscription.
- If you don’t have one, create a [free account](https://azure.microsoft.com/free/) ($200 credit for 30 days).

---

## ⚙️ Configuration: GitHub Secrets vs. Variables

| Name | Type | Description |
|------|------|-------------|
| `AZURE_CREDENTIALS` | **Secret** | JSON output of `az ad sp create-for-rbac` (only if using service principal). |
| `ACR_NAME` | **Variable** | Name of your Azure Container Registry (e.g., `myregistry`). |
| `ACR_PASSWORD` | **Secret** | Admin password of the registry (if using admin user). |
| `RESOURCE_GROUP` | **Variable** | Name of the resource group containing all resources. |
| `STORAGE_ACCOUNT_NAME` | **Variable** | Name of the storage account for Azure Files. |
| `STORAGE_ACCOUNT_KEY` | **Secret** | Access key for the storage account. |
| `SHARE_NAME` | **Variable** | Name of the file share (e.g., `dailyairlineshare`). |
| `NINJAS_API_KEY` | **Secret** | Your API-Ninjas key. |
| `AMADEUS_CLIENT_ID` | **Secret** | Amadeus client ID. |
| `AMADEUS_CLIENT_SECRET` | **Secret** | Amadeus client secret. |
| `MAILGUN_DOMAIN` | **Variable** | Your Mailgun domain (e.g., `mg.yourdomain.com`). |
| `SENDER_EMAIL` | **Variable** | Verified sender email (e.g., `postmaster@mg.yourdomain.com`). |
| `SENDER_APP_PASSWORD` | **Secret** | Mailgun API key (starts with `key-`). |
| `RECIPIENT_EMAILS` | **Variable** | Comma-separated list of email addresses to receive the daily airline. |
| `SENDER_NAME` | **Variable** | Display name for the sender (e.g., `Daily Airline`). |

**Where to set them**  
- Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**.  
- Add secrets under the **Secrets** tab, and variables under the **Variables** tab.

---

## Manual Build and Deployment (First Time / Testing)

Before setting up the automated CI/CD pipeline, you may want to manually build and run the container once to verify that everything works. This section walks you through building the Docker image directly in Azure Container Registry (ACR) and creating the Azure Container Instance (ACI) with all the required environment variables.

### Prerequisites

- Azure CLI installed and logged in (`az login`).
- Your repository cloned locally.
- All Azure resources already created (ACR, storage account, file share) as described in the previous sections.

---

### 1. Build and push the Docker image from the local machine

Open a terminal in VS Code (or any terminal) and navigate to your repository folder. Use the `az acr build` command to build the image directly in ACR – this does not require Docker to be installed locally.

```bash
# Build the image using ACR Tasks
az acr build --registry <acr-name> --image daily-airline:latest .

Replace `<acr-name>` with your actual ACR instance name (e.g., `acrairlines101`).  
This command uploads your source code to ACR, builds the image, and pushes it to the repository. The image will be tagged as `daily-airline:latest`.
```

---

### 2. Create (or recreate) the Container Group in Azure

Now create the container instance that will run the Python script. You can run these commands from the **Azure Cloud Shell** or any environment with the Azure CLI.

First, make sure you are working in the correct subscription:

```bash
az account set --subscription <subscription-id>
Replace `<subscription-id>` with your Azure subscription ID.
```

#### Retrieve the required secrets

You will need two secret values: the ACR password and the storage account key. Get them with these commands:

```bash
# ACR password
az acr credential show --name <acr-name> --query "passwords[0].value" -o tsv

# Storage account key
az storage account keys list --account-name <storage-account-name> --query "[0].value" -o tsv
```

Replace `<acr-name>` and `<storage-account-name>` with your actual resource names.

### Run the container creation command

The following command deletes any existing container group with the same name (to avoid conflicts) and then creates a new one. If this is your first run, the delete step will simply report that the container group was not found, that’s fine.

```bash
# Delete any previous instance (optional, but safe)
az container delete --resource-group rg_exp --name daily-airline-job --yes
```

```bash
# Create the new container group
az container create \
  --resource-group rg_exp \
  --name daily-airline-job \
  --image acrairlines101.azurecr.io/daily-airline:latest \
  --registry-login-server acrairlines101.azurecr.io \
  --registry-username acrairlines101 \
  --registry-password <acr-password> \
  --azure-file-volume-account-name saexp \
  --azure-file-volume-account-key <storage-account-key> \
  --azure-file-volume-share-name dailyairlineshare \
  --azure-file-volume-mount-path /mnt/data \
  --os-type Linux \
  --cpu 1 \
  --memory 1.5 \
  --environment-variables \
      DATA_DIR=/mnt/data \
      NINJAS_API_KEY='<your-ninjas-api-key>' \
      AMADEUS_CLIENT_ID='<your-amadeus-client-id>' \
      AMADEUS_CLIENT_SECRET='<your-amadeus-client-secret>' \
      SENDER_EMAIL='airline_exp@yourdomain.com' \
      SENDER_APP_PASSWORD='<mailgun-api-key>' \
      SENDER_NAME='Airline explorer ✈️' \
      RECIPIENT_EMAILS='dj@live.com,dj@gmail.com' \
  --restart-policy Never
```
  
**Replace all placeholders:**

- `<acr-password>` – the password you retrieved from ACR.
- `<storage-account-key>` – the key you retrieved from the storage account.
- `<your-ninjas-api-key>`, `<your-amadeus-client-id>`, `<your-amadeus-client-secret>` – your API credentials.
- `<mailgun-api-key>` – your Mailgun API key (starts with `key-`).
- The recipient emails – you can modify the list as needed.

> **Note:**  
> - The `SENDER_APP_PASSWORD` is your **Mailgun API key**, not a regular password.  
> - The `SENDER_EMAIL` must be a verified sender in your Mailgun domain.

### 3. Check the logs

After the container is created, it will start automatically, run your script once, and then exit (due to `--restart-policy Never`). You can view its output with:

```bash
az container logs --resource-group rg_exp --name daily-airline-job --container-name daily-airline-job
```

You should see the script’s output, including a success message and confirmation that the email was sent. If something went wrong, the logs will help you troubleshoot.

### 4. Next Steps
Once you have verified that the container runs correctly, you can proceed to set up the GitHub Actions workflow for continuous deployment. Every push to your repository will then automatically rebuild the image and update the container group.


