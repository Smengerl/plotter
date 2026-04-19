#!/usr/bin/env python3
"""
setup_hf_token.py - Configure HuggingFace authentication token

Usage:
    python setup_hf_token.py
    ./setup_hf_token.py

This script will:
1. Prompt for your HuggingFace token
2. Save it to ~/.huggingface/token
3. Verify the authentication works
"""

import json
import sys
from pathlib import Path
from getpass import getpass

def setup_hf_token():
    """Interactively setup HuggingFace token."""
    
    print("=" * 70)
    print("🤗 HuggingFace Authentication Setup")
    print("=" * 70)
    print()
    
    # Step 1: Get token from user
    print("Step 1: Get your HuggingFace token")
    print("-" * 70)
    print("  1. Go to: https://huggingface.co/settings/tokens")
    print("  2. Click 'New token'")
    print("  3. Name: 'plotter-pipeline' (or anything)")
    print("  4. Type: 'read' (minimum for accessing models)")
    print("  5. Copy the token (starts with 'hf_')")
    print()
    
    token = getpass("Paste your HuggingFace token here: ").strip()
    
    if not token:
        print("❌ No token provided. Exiting.")
        return False
    
    if not token.startswith("hf_"):
        print("⚠️  Token should start with 'hf_'. Are you sure it's correct?")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != "y":
            return False
    
    # Step 2: Save token
    print()
    print("Step 2: Saving token...")
    print("-" * 70)
    
    hf_dir = Path.home() / ".huggingface"
    hf_dir.mkdir(exist_ok=True, parents=True)
    
    token_file = hf_dir / "token"
    token_file.write_text(token)
    token_file.chmod(0o600)  # Read-write for owner only
    
    print(f"✅ Token saved to: {token_file}")
    
    # Step 3: Verify authentication
    print()
    print("Step 3: Verifying authentication...")
    print("-" * 70)
    
    try:
        from huggingface_hub import whoami
        user_info = whoami(token=token)
        print(f"✅ Authentication successful!")
        print(f"   User: {user_info.get('name', 'Unknown')}")
        print(f"   ID: {user_info.get('user_id', 'Unknown')}")
        return True
    except Exception as e:
        print(f"⚠️  Could not verify token: {e}")
        print("   Token is saved, but you may need to accept gated model licenses.")
        print("   Go to each model page and click 'Access repository' first.")
        return True

def main():
    try:
        success = setup_hf_token()
        if success:
            print()
            print("=" * 70)
            print("🎉 Setup complete!")
            print("=" * 70)
            print()
            print("You can now use gated models like:")
            print("  • stable-diffusion-v1-5/stable-diffusion-v1-5")
            print("  • black-forest-labs/FLUX.1-dev")
            print()
            print("Next: Run your pipeline scripts")
            print("  ./pipeline/examples/run_img2img_example.py")
            print("  ./pipeline/examples/run_controlnet_example.py")
            return 0
        else:
            return 1
    except KeyboardInterrupt:
        print()
        print("❌ Cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
