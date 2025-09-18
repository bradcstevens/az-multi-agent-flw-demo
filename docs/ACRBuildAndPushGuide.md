# Azure Container Registry (ACR) – Build & Push Guide

This guide provides step-by-step instructions to build and push Docker images for **WebApp** and **Backend** services into Azure Container Registry (ACR).

## 📋 Prerequisites
Before starting, ensure you have:
- An active [Azure Subscription](https://portal.azure.com/)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in
- [Docker](https://docs.docker.com/get-docker/) installed and running
- Access to your Azure Container Registry (ACR)

---

## 🚀 Build and Push Images

Login to ACR :
``` bash
az acr login --name $ACR_NAME
```
Command Build and Push Images to Backend : 
 
 ```bash 
 az acr login --name <containerregname>
docker build --no-cache -f docker/Frontend.Dockerfile -t <acrloginserver>/<repo>:<tagname> .
docker push <acrloginserver>/<repo>:<tagname>
 ```

## ✅ Verification

Run the following command to verify that images were pushed successfully:
```bash
az acr repository list --name $ACR_NAME --output table
```

You should see repositories in the output.

## 📝 Notes

- Always use meaningful tags (v1.0.0, staging, prod) instead of just latest.

- If you are pushing from a CI/CD pipeline, make sure the pipeline agent has access to Docker and ACR.

- For private images, ensure your services (e.g., Azure Container Apps, AKS, App Service) are configured with appropriate ACR pull permissions.



