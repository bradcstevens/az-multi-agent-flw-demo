#!/bin/bash

# Variables
cosmosdbName=$1
databaseName=$2
containerName=$3
directoryPath=$4
resourceGroup=$5

# get parameters from azd env, if not provided
if [ -z "$cosmosdbName" ]; then
    cosmosdbName=$(azd env get-value COSMOSDB_ACCOUNT_NAME)
fi

if [ -z "$databaseName" ]; then
    databaseName=$(azd env get-value COSMOSDB_DATABASE)
fi

if [ -z "$containerName" ]; then
    containerName=$(azd env get-value COSMOSDB_CONTAINER)
fi

if [ -z "$directoryPath" ]; then
    directoryPath="data/agent_teams"
fi

if [ -z "$resourceGroup" ]; then
    resourceGroup=$(azd env get-value AZURE_RESOURCE_GROUP)
fi

azSubscriptionId=$(azd env get-value AZURE_SUBSCRIPTION_ID)

# Check if all required arguments are provided
if [ -z "$cosmosdbName" ] || [ -z "$databaseName" ] || [ -z "$containerName" ] || [ -z "$directoryPath" ]; then
    echo "Error: Missing required arguments."
    echo "Usage: $0 <cosmosdbName> <databaseName> <containerName> <directoryPath> [resourceGroupName]"
    exit 1
fi

# Authenticate with Azure
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    echo "Not authenticated with Azure. Attempting to authenticate..."
    echo "Authenticating with Azure CLI..."
    az login
fi

#check if user has selected the correct subscription
currentSubscriptionId=$(az account show --query id -o tsv)
currentSubscriptionName=$(az account show --query name -o tsv)
if [ "$currentSubscriptionId" != "$azSubscriptionId" ]; then
    echo "Current selected subscription is $currentSubscriptionName ( $currentSubscriptionId )."
    read -rp "Do you want to continue with this subscription?(y/n): " confirmation
    if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
        echo "Fetching available subscriptions..."
        availableSubscriptions=$(az account list --query "[?state=='Enabled'].[name,id]" --output tsv)
        while true; do
            echo ""
            echo "Available Subscriptions:"
            echo "========================"
            echo "$availableSubscriptions" | awk '{printf "%d. %s ( %s )\n", NR, $1, $2}'
            echo "========================"
            echo ""
            read -rp "Enter the number of the subscription (1-$(echo "$availableSubscriptions" | wc -l)) to use: " subscriptionIndex
            if [[ "$subscriptionIndex" =~ ^[0-9]+$ ]] && [ "$subscriptionIndex" -ge 1 ] && [ "$subscriptionIndex" -le $(echo "$availableSubscriptions" | wc -l) ]; then
                selectedSubscription=$(echo "$availableSubscriptions" | sed -n "${subscriptionIndex}p")
                selectedSubscriptionName=$(echo "$selectedSubscription" | cut -f1)
                selectedSubscriptionId=$(echo "$selectedSubscription" | cut -f2)

                # Set the selected subscription
                if  az account set --subscription "$selectedSubscriptionId"; then
                    echo "Switched to subscription: $selectedSubscriptionName ( $selectedSubscriptionId )"
                    break
                else
                    echo "Failed to switch to subscription: $selectedSubscriptionName ( $selectedSubscriptionId )."
                fi
            else
                echo "Invalid selection. Please try again."
            fi
        done
    else
        echo "Proceeding with the current subscription: $currentSubscriptionName ( $currentSubscriptionId )"
        az account set --subscription "$currentSubscriptionId"
    fi
else
    echo "Proceeding with the subscription: $currentSubscriptionName ( $currentSubscriptionId )"
    az account set --subscription "$currentSubscriptionId"
fi

userPrincipalId=$(az ad signed-in-user show --query id -o tsv)

cosmosIsPublicAccessDisabled=false
#Enable Public Access for cosmos
if [ -n "$resourceGroup" ]; then
    cosmosPublicAccess=$(az cosmosdb show --name "$cosmosdbName" --resource-group "$resourceGroup" --query "publicNetworkAccess" -o tsv)
    if [ "$cosmosPublicAccess" == "Disabled" ]; then
        cosmosIsPublicAccessDisabled=true
        echo "Enabling public access for cosmos DB: $cosmosdbName"
        az cosmosdb update --name "$cosmosdbName" --resource-group "$resourceGroup" --public-network-access enabled --output none
        if [ $? -ne 0 ]; then
            echo "Error: Failed to enable public access for CosmosDB."
            exit 1
        fi
        echo "Public access enabled for CosmosDB: $cosmosdbName"
    else
        echo "Public access is already enabled for CosmosDB: $cosmosdbName"
    fi
fi

# Determine the correct Python command
if command -v python && python --version &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 && python3 --version &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "Python is not installed on this system. Or it is not added in the PATH."
    exit 1
fi

# create virtual environment
if [ -d "infra/scripts/scriptenv" ]; then
    echo "Virtual environment already exists. Skipping creation."
else
    echo "Creating virtual environment"
    $PYTHON_CMD -m venv infra/scripts/scriptenv
fi

# Activate the virtual environment
if [ -f "infra/scripts/scriptenv/bin/activate" ]; then
    echo "Activating virtual environment (Linux/macOS)"
    source "infra/scripts/scriptenv/bin/activate"
elif [ -f "infra/scripts/scriptenv/Scripts/activate" ]; then
    echo "Activating virtual environment (Windows)"
    source "infra/scripts/scriptenv/Scripts/activate"
else
    echo "Error activating virtual environment. Requirements may be installed globally."
fi

# Install the requirements
echo "Installing requirements"
pip install --quiet -r infra/scripts/requirements.txt
echo "Requirements installed"

echo "Running the python script to upload team configuration"
$PYTHON_CMD infra/scripts/team-config-scripts/upload_team_config.py "$cosmosdbName" "$databaseName" "$containerName" "$directoryPath" "$userPrincipalId"
if [ $? -ne 0 ]; then
    echo "Error: Team configuration upload failed."
    exit 1
fi

#disable public access for cosmos
if [ "$cosmosIsPublicAccessDisabled" = true ]; then
    echo "Disabling public access for CosmosDB: $cosmosdbName"
    az cosmosdb update --name "$cosmosdbName" --resource-group "$resourceGroup" --public-network-access disabled --output none
    if [ $? -ne 0 ]; then
        echo "Error: Failed to disable public access for CosmosDB."
        exit 1
    fi
    echo "Public access disabled for CosmosDB: $cosmosdbName"
fi