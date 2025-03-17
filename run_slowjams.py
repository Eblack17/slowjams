#!/usr/bin/env python3
"""
SlowJams Runner Script

This script provides a simple way to run the SlowJams application
without requiring installation.
"""

import os
import sys
import platform
import subprocess

# Ensure we can import from the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Try to import the main entry point
try:
    from slowjams_app import main
    HAS_DIRECT_IMPORT = True
except ImportError:
    HAS_DIRECT_IMPORT = False


def check_requirements():
    """
    Check if requirements are installed.
    
    Returns:
        True if all requirements are installed, False otherwise.
    """
    try:
        # Check if requirements.txt exists
        requirements_path = os.path.join(current_dir, 'requirements.txt')
        if not os.path.exists(requirements_path):
            print("Error: requirements.txt not found")
            return False
        
        # Read requirements
        with open(requirements_path, 'r', encoding='utf-8') as f:
            requirements = [line.strip() for line in f 
                           if line.strip() and not line.startswith('#')]
        
        # Check each requirement
        import importlib
        missing = []
        
        for req in requirements:
            # Extract the package name (remove version info)
            package = req.split('==')[0].split('>=')[0].split('<=')[0].strip()
            
            try:
                importlib.import_module(package)
            except ImportError:
                missing.append(req)
        
        if missing:
            print("Missing requirements:")
            for req in missing:
                print(f"  - {req}")
            print("\nWould you like to install them now? (y/n)")
            choice = input().strip().lower()
            
            if choice == 'y':
                print("Installing requirements...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements_path])
                return True
            else:
                print("Requirements not installed. Application may not function correctly.")
                return False
        
        return True
    
    except Exception as e:
        print(f"Error checking requirements: {str(e)}")
        return False


def run_slowjams():
    """Run the SlowJams application."""
    if HAS_DIRECT_IMPORT:
        # Run directly if we can import the main function
        sys.exit(main())
    else:
        # Otherwise, run as a subprocess
        cmd = [sys.executable, os.path.join(current_dir, 'slowjams_app.py')]
        cmd.extend(sys.argv[1:])
        
        try:
            print(f"Starting SlowJams...")
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f"Error running SlowJams: {str(e)}")
            sys.exit(e.returncode)
        except KeyboardInterrupt:
            print("\nSlowJams was interrupted by user")
            sys.exit(130)  # Standard exit code for SIGINT


def show_platform_info():
    """Show information about the platform."""
    print(f"Platform: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"Executable: {sys.executable}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Script directory: {current_dir}")


if __name__ == "__main__":
    # Show header
    print("=" * 60)
    print("SlowJams - Audio Extraction and Manipulation Tool")
    print("=" * 60)
    
    # Show platform info in debug mode
    if '--debug' in sys.argv:
        show_platform_info()
        print("-" * 60)
    
    # Check requirements
    if check_requirements():
        # Run the application
        run_slowjams()
    else:
        sys.exit(1)