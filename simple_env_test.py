#!/usr/bin/env python3
"""
Simple environment test to understand what's available
"""
import os
import sys

print("=== ENVIRONMENT ANALYSIS ===")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")

print("\n=== AVAILABLE ENVIRONMENT VARIABLES ===")
# Look for anything that might be relevant
relevant_vars = []
for key, value in os.environ.items():
    if any(term in key.upper() for term in ['SUPA', 'DB', 'KEY', 'TOKEN', 'SECRET', 'URL']):
        # Mask sensitive values
        if 'KEY' in key.upper() or 'SECRET' in key.upper() or 'TOKEN' in key.upper():
            masked_value = f"{value[:8]}..." if len(value) > 8 else "***"
            relevant_vars.append(f"{key}={masked_value}")
        else:
            relevant_vars.append(f"{key}={value}")

for var in sorted(relevant_vars):
    print(f"  {var}")

print("\n=== CHECKING PYTHON PACKAGES ===")
packages_to_check = ['httpx', 'supabase', 'requests', 'urllib3']
available_packages = []

for pkg in packages_to_check:
    try:
        __import__(pkg)
        print(f"✅ {pkg} available")
        available_packages.append(pkg)
    except ImportError:
        print(f"❌ {pkg} not available")

print("\n=== GITHUB ACTIONS CONTEXT ===")
github_vars = []
for key, value in os.environ.items():
    if key.startswith('GITHUB_'):
        github_vars.append(f"{key}={value}")

for var in sorted(github_vars):
    print(f"  {var}")

print("\n=== CHECKING WORKSPACE ===")
try:
    import glob
    py_files = glob.glob("**/*.py", recursive=True)
    print(f"Python files in workspace: {len(py_files)}")
    
    # Look for any existing supabase setup
    supabase_files = [f for f in py_files if 'supa' in f.lower()]
    print(f"Supabase-related files: {supabase_files[:5]}")  # Show first 5
    
except Exception as e:
    print(f"Error checking workspace: {e}")

if 'httpx' in available_packages:
    print("\n=== TESTING HTTPX CONNECTION ===")
    try:
        import httpx
        
        # Test a simple HTTP request
        with httpx.Client(timeout=10) as client:
            r = client.get("https://httpbin.org/status/200")
            print(f"✅ HTTP test successful: {r.status_code}")
            
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")