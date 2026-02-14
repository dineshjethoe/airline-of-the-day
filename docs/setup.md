# Azure Setup (Service Principal)

This guide walks you through creating all required Azure resources and configuring GitHub Actions using a service principal.  
You need **Azure AD permissions** to create a service principal – if you don’t have them, see the [alternative setup](alternative-setup.md).

## 1. Create Azure Resources

Run the following commands in the Azure CLI. Replace placeholders (e.g., `your-resource-group`) with your own values.

```bash
# Variables
RESOURCE_GROUP="rg_exp"
LOCATION="westeurope"
ACR_NAME="acrairlines101" # globally unique
STORAGE_ACCOUNT="saexp" # globally unique
SHARE_NAME="dailyairlineshare"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry (Basic tier, admin enabled for simplicity)
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true

# Create storage account and file share (for sent_airlines.json)
az storage account create --resource-group $RESOURCE_GROUP --name $STORAGE_ACCOUNT --location $LOCATION --sku Standard_LRS
az storage share create --name $SHARE_NAME --account-name $STORAGE_ACCOUNT

# Retrieve and save the following values (you’ll need them later):
echo "Storage account key:"
az storage account keys list --account-name $STORAGE_ACCOUNT --query "[0].value" -o tsv

echo "ACR password:"
az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
```

## 2. Create a Service Principal for GitHub Actions

Run this command to create a service principal with Contributor rights on your resource group:

```bash
az ad sp create-for-rbac --name "github-actions-dailyairline" \
  --role contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
  ```

  > Copy the entire JSON output, this will be stored as the GitHub secret AZURE_CREDENTIALS.

### 3. Configure GitHub Secrets and Variables

In your GitHub repository, go to **Settings** → **Secrets and variables** → **Actions** and add the following:

#### Secrets (encrypted)

| Name | Value |
|------|-------|
| `AZURE_CREDENTIALS` | The JSON from step 2 |
| `ACR_PASSWORD` | The ACR admin password from step 1 |
| `STORAGE_ACCOUNT_KEY` | The storage account key from step 1 |
| `NINJAS_API_KEY` | Your API‑Ninjas key |
| `AMADEUS_CLIENT_ID` | Your Amadeus client ID |
| `AMADEUS_CLIENT_SECRET` | Your Amadeus client secret |
| `SENDER_APP_PASSWORD` | Your Mailgun API key (starts with `key-`) |

#### Variables (plain text)

| Name | Value |
|------|-------|
| `ACR_NAME` | Your ACR name (e.g., `dailyairlineacr`) |
| `RESOURCE_GROUP` | Your resource group name |
| `STORAGE_ACCOUNT_NAME` | Your storage account name |
| `SHARE_NAME` | Your file share name (e.g., `dailyairlineshare`) |
| `MAILGUN_DOMAIN` | Your Mailgun domain (e.g., `mg.yourdomain.com`) |
| `SENDER_EMAIL` | Verified sender email (e.g., `newsletter@mg.yourdomain.com`) |
| `RECIPIENT_EMAILS` | Comma‑separated list of recipient emails |
| `SENDER_NAME` | Display name for the sender (e.g., `Daily Airline`) |

---

### 4. Deploy the Logic App Scheduler

Once the GitHub Actions workflow has run at least once (creating the container group), set up a Logic App to trigger it daily:

1. In the Azure portal, create a new **Logic App** (Consumption plan).
2. Use the **Recurrence** trigger (set your desired time).
3. Add an action: **Azure Container Instances – Start container group**.
   - Select your subscription, resource group, and the container group name **`<container-name>`**.
4. Save and enable the Logic App.

The container group will now start automatically every day, run your script, and exit.

---

### 5. First GitHub Actions Run

Push your code to the `main` branch. The workflow will:

- Build the Docker image **`<repo-name>:commit-sha`**.
- Push it to ACR.
- Delete any existing container group named **`<container-name>`**.
- Create a new container group with the latest image and all environment variables.

After creation, the container runs once. Check the logs with:

```bash
az container logs --resource-group $RESOURCE_GROUP --name <container-name>

