# Minimising Azure Container Registry costs

Azure Container Registry (ACR) charges for storage based on the amount of data you keep. If you push a new image on every code change, old image layers accumulate and increase your monthly bill.

## Tip: Delete old images and keep only the latest

### Option 1: Manual cleanup with Azure CLI

List all tags in your repository:

```bash
az acr repository show-tags --name <acr-name> --repository <image-name> --orderby time_desc
```

### Option 2: Automate with an ACR Task
You can create a scheduled task that runs weekly and cleans up old images. For example, keep the last 10 tags:

```bash
az acr task create \
  --registry <acr-name> \
  --name cleanup-<image-name>-images \
  --context /dev/null \
  --file acr-cleanup.yaml \
  --schedule "0 0 * * 0" # every Sunday at midnight
```

The acr-cleanup.yaml task file would contain:

```yaml
version: v1.1.0
steps:
  - cmd: |
      tags=$(az acr repository show-tags --name {{.Run.Registry}} --repository <image-name> --orderby time_desc --output tsv | tail -n +10)
      for tag in $tags; do
        az acr repository delete --name {{.Run.Registry}} --image <image-name>:$tag --yes
      done
```

### Option 3: Use GitHub Actions to delete old images after each push
Add a step in the workflow that removes images older than, say, 7 days. Example:

```yaml
- name: Clean up old ACR images
  run: |
    # Get all tags older than 7 days and delete them
    threshold=$(date -d '7 days ago' +%Y%m%d)
    tags=$(az acr repository show-tags --name ${{ vars.ACR_NAME }} --repository <image-name> --orderby time_desc --output tsv)
    for tag in $tags; do
      # Assuming tags contain the commit date or you can parse manifest time
      # This is a simplified example; implement your own logic
      az acr repository delete --name ${{ vars.ACR_NAME }} --image <image-name>:$tag --yes || true
    done
```

> **Note:** Always test deletion commands in a non-production environment first. Keep at least one image to ensure your container can still run.

By regularly purging old images, you keep storage costs to a minimum.