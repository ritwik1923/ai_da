#!/usr/bin/env python
"""
Test script to verify Ollama connection and API
Run this inside the Docker container to debug connectivity
"""
import requests
import json

BASE_URL = "http://host.docker.internal:11434"

def test_ollama_root():
    """Test basic connectivity"""
    print("Testing root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}", timeout=5)
        print(f"✓ Root endpoint: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ Root endpoint failed: {e}")
        return False

def test_ollama_models():
    """Test getting available models"""
    print("\nTesting /api/tags endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/tags", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"Available models: {[m['name'] for m in models]}")
            return True
        return False
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_ollama_chat():
    """Test chat endpoint with a simple message"""
    print("\nTesting /api/chat endpoint with POST...")
    
    payload = {
        "model": "llama3",
        "messages": [
            {"role": "user", "content": "Hello, what is 2+2?"}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=120
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("message", {}).get("content", "")
            print(f"✓ Response: {content[:100]}")
            return True
        else:
            print(f"✗ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Ollama Connection Test")
    print("=" * 60)
    
    results = [
        test_ollama_root(),
        test_ollama_models(),
        test_ollama_chat()
    ]
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ All tests passed! Ollama is configured correctly.")
    else:
        print("✗ Some tests failed. Check the errors above.")
    print("=" * 60)
