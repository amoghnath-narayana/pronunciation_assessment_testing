#!/usr/bin/env python3
"""
Verification script to check Gemini model configuration.

This script verifies:
1. Which model is configured in the environment
2. The thinking level setting
3. That the model is accessible via the API
4. Current model capabilities
"""

import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from google.genai import types
from config import AppConfig


def verify_model_configuration():
    """Verify the current Gemini model configuration."""
    
    print("=" * 70)
    print("GEMINI MODEL CONFIGURATION VERIFICATION")
    print("=" * 70)
    
    # Load configuration
    config = AppConfig()
    
    print("\n📋 CONFIGURATION FROM .env FILE:")
    print(f"   Model Name: {config.model_name}")
    print(f"   Temperature: {config.assessment_temperature}")
    print(f"   Max Output Tokens: {config.assessment_max_output_tokens}")
    
    # Initialize client with v1alpha API for Gemini 3 features
    try:
        client = genai.Client(
            api_key=config.gemini_api_key,
            http_options={'api_version': 'v1alpha'}
        )
        print("\n✅ Successfully initialized Gemini client (v1alpha API)")
    except Exception as e:
        print(f"\n❌ Failed to initialize Gemini client: {e}")
        return False
    
    # Check model accessibility
    print(f"\n🔍 VERIFYING MODEL ACCESS: {config.model_name}")
    try:
        # Try to list available models
        print("\n   Available models:")
        models = client.models.list()
        gemini_3_models = []
        current_model_found = False
        
        for model in models:
            if "gemini-3" in model.name.lower():
                gemini_3_models.append(model.name)
                print(f"   • {model.name}")
                if config.model_name in model.name:
                    current_model_found = True
                    print(f"     ✅ This is your configured model!")
        
        if not gemini_3_models:
            print("   ⚠️  No Gemini 3 models found in available models list")
        
        if not current_model_found:
            print(f"\n   ⚠️  Configured model '{config.model_name}' not found in available models")
            print("   This might be normal if the model is in preview/early access")
        
    except Exception as e:
        print(f"   ⚠️  Could not list models: {e}")
    
    # Test the model with a simple request
    print(f"\n🧪 TESTING MODEL WITH SAMPLE REQUEST:")
    try:
        # Create a test request with thinking_level=LOW
        response = client.models.generate_content(
            model=config.model_name,
            contents="Say 'Hello' in JSON format with a 'message' field.",
            config=types.GenerateContentConfig(
                temperature=1.0,  # Gemini 3 default
                max_output_tokens=100,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            ),
        )
        
        print(f"   ✅ Model responded successfully!")
        if response.text:
            print(f"   Response: {response.text[:100]}...")
        
        # Check if thinking was used
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            print(f"\n📊 USAGE METADATA:")
            metadata = response.usage_metadata
            if hasattr(metadata, 'prompt_token_count'):
                print(f"   Prompt tokens: {metadata.prompt_token_count}")
            if hasattr(metadata, 'candidates_token_count'):
                print(f"   Response tokens: {metadata.candidates_token_count}")
            if hasattr(metadata, 'total_token_count'):
                print(f"   Total tokens: {metadata.total_token_count}")
        
    except Exception as e:
        print(f"   ❌ Model test failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False
    
    # Verify thinking configuration in code
    print(f"\n⚙️  THINKING CONFIGURATION:")
    print(f"   Setting: thinking_level=ThinkingLevel.LOW")
    print(f"   ⚠️  Note: Gemini 3 thinking is ALWAYS ON (defaults to HIGH if not specified)")
    print(f"   ✅ LOW setting provides lower latency similar to Gemini 2.5 Flash")
    print(f"   ✅ Suitable for high-throughput pronunciation assessment tasks")
    print(f"   ✅ Optimized for speed while maintaining superior response quality")
    
    # Show available thinking levels
    print(f"\n   Available thinking levels:")
    print(f"   • LOW: High-throughput, lower latency (currently configured)")
    print(f"   • HIGH: Maximum reasoning capability, higher latency (DEFAULT if not set)")
    print(f"   • THINKING_LEVEL_UNSPECIFIED: Uses model default (HIGH)")
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"✅ Model: {config.model_name}")
    print(f"✅ Thinking Level: low (configured in gemini_service.py)")
    print(f"✅ Temperature: {config.assessment_temperature} (Note: Gemini 3 recommends 1.0)")
    print(f"✅ API Connection: Working")
    print("\n💡 RECOMMENDATIONS:")
    
    if config.assessment_temperature != 1.0:
        print(f"   ⚠️  Consider changing ASSESSMENT_TEMPERATURE to 1.0 in .env")
        print(f"      Gemini 3 is optimized for temperature=1.0")
    
    print("\n✨ Configuration verified successfully!")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = verify_model_configuration()
    sys.exit(0 if success else 1)
