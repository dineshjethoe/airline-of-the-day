
# Alternative CI/CD with Self-Hosted Runner (No Service Principal)

If you cannot create a service principal (e.g., no Azure AD permissions), you can use a small Azure VM with a managed identity as a self‑hosted GitHub Actions runner.

## Step 1: Create a Linux VM with Managed Identity

1. In the Azure portal, create a new **Ubuntu Server 22.04 LTS** VM (size B1s is sufficient and low cost).
2. Under the **Management** tab, enable a **system-assigned managed identity**.
3. After creation, go to the VM’s **Access control (IAM)** and assign the **Contributor** role to the VM’s managed identity on your resource group (or the specific resources like ACR, ACI, Storage).

## Step 2: Install Docker and Azure CLI on the VM

SSH into the VM and run:

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect

# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Log in using the managed identity (no password needed)
az login --identity
```

Verify that Azure CLI works (e.g., `az group list`).

### Step 3: Add the VM as a Self-Hosted Runner

Follow the official GitHub documentation: [Adding self-hosted runners](https://docs.github.com/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners).

1. In your GitHub repository, go to **Settings** → **Actions** → **Runners** → **New self-hosted runner**.
2. Choose the appropriate OS (Linux) and architecture (x64).
3. Run the provided commands on the VM to download and configure the runner.
4. After configuration, start the runner as a service:

   ```bash
   sudo ./svc.sh install
   sudo ./svc.sh start
   ```

### Step 4: Update the workflow

In `.github/workflows/deploy.yml`, change `runs-on: ubuntu-latest` to `runs-on: self-hosted`. Remove the `azure/login` step entirely because the VM is already authenticated via its managed identity.

The workflow will now run on your VM, using its managed identity to manage Azure resources.