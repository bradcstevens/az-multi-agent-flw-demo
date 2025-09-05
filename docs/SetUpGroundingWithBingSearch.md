# Grounding with Bing Search — Quick Setup

This guide shows how to **create a Grounding with Bing Search resource** and **connect it to your Azure AI Foundry project through the portal**.

---

## Prerequisites

* An **Azure subscription**
* **Azure CLI** installed and logged in (`az login`)
* A **resource group** already created
* Register the Bing provider:

  ```bash
  az provider register --namespace Microsoft.Bing
  ```

⚠️ **Important:**  
Bing Search grounding only works with **API key authentication**.  
Make sure your **Azure AI Foundry account has Local Authentication enabled**.  
If local auth is disabled, you will not be able to create a Bing Search connection.


## 1) Create the Bing Search Grounding resource

### Option A — Using Azure Portal

1. In the [Azure Portal](https://portal.azure.com), search for **Bing Search (Grounding)**.  
2. Click **Create**.  
3. Select the **Subscription** and **Resource Group**.  
4. Enter the **Resource Name** and select a **Pricing Tier (SKU)**.  
5. ⚠️ At the bottom of the creation form, you will see a required checkbox:  
   - You must enable: ✅ *“I confirm I have read and understood the notice above.”*  
   - Without checking this, you cannot proceed.  
6. Click **Review + Create** → **Create**. 

### Option B — Using Azure CLI

Set the variables (replace values with your own):

```bash
RESOURCE_GROUP="<your-resource-group>"
ACCOUNT_NAME="<unique-bing-resource-name>"
LOCATION="global"   # must be 'global'
SKU="G1"
KIND="Bing.Grounding"

SUBSCRIPTION_ID=$(az account show --query id --output tsv)
RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/microsoft.bing/accounts/$ACCOUNT_NAME"
```

Create the resource:

```bash
az rest --method put \
  --url "https://management.azure.com$RESOURCE_ID?api-version=2020-06-10" \
  --body '{
    "location": "'$LOCATION'",
    "kind": "'$KIND'",
    "sku": { "name": "'$SKU'" },
    "properties": {}
  }'
```

Verify:

```bash
az resource show --ids "$RESOURCE_ID" --api-version 2020-06-10 -o table
```

---

## 2) Connect the Bing resource to your Azure AI Foundry project (Portal)

1. Go to your **Azure AI Foundry project** in the portal.
2. Open **Management center** → **Connected resources**.
3. Click **+ Add connection**.
4. Select **Grounding with Bing Search**.
5. Choose the Bing resource you created and click **Create**.

---

## 💡 Why Use Bing Search Grounding?

* Provides **real-time information** to enrich AI responses.
* Helps LLMs answer with **up-to-date knowledge** beyond training data.
* Useful for scenarios like **news, research, or dynamic data queries**.

---

## 📚 Additional Resources

* [Use Bing Search grounding with Azure AI Foundry (official docs)](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/bing-code-samples?source=recommendations&pivots=portal)

```

---