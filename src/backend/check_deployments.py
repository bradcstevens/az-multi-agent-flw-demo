import asyncio
import sys
import os

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, backend_path)

try:
    from v3.common.services.foundry_service import FoundryService

    async def check_deployments():
        try:
            print("🔍 Checking Azure AI Foundry model deployments...")
            foundry_service = FoundryService()
            deployments = await foundry_service.list_model_deployments()
            
            print("\n📋 Raw deployments found:")
            for i, deployment in enumerate(deployments, 1):
                name = deployment.get('name', 'Unknown')
                status = deployment.get('status', 'Unknown')
                model_name = deployment.get('model', {}).get('name', 'Unknown')
                print(f"  {i}. Name: {name}, Status: {status}, Model: {model_name}")
            
            print(f"\n✅ Total deployments: {len(deployments)}")
            
            # Filter successful deployments
            successful_deployments = [
                d for d in deployments 
                if d.get('status') == 'Succeeded'
            ]
            
            print(f"✅ Successful deployments: {len(successful_deployments)}")
            
            available_models = [
                d.get('name', '').lower()
                for d in successful_deployments
            ]
            
            print(f"\n🎯 Available model names (lowercase): {available_models}")
            
            # Check what we're looking for
            required_models = ['gpt-4o', 'o3', 'gpt-4', 'gpt-35-turbo']
            print(f"\n🔍 Checking for required models: {required_models}")
            
            for model in required_models:
                if model.lower() in available_models:
                    print(f'✅ {model} is available')
                else:
                    print(f'❌ {model} is NOT found in available models')
                    
        except Exception as e:
            print(f'❌ Error: {e}')
            import traceback
            traceback.print_exc()

    if __name__ == "__main__":
        asyncio.run(check_deployments())
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the correct directory with the virtual environment activated.")
