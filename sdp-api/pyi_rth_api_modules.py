# Runtime hook to load API modules dynamically
import sys
import os
import importlib.util
import types

print("[API HOOK] Loading missing API modules...")

# Get the base path where PyInstaller extracts files
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Reload core.security to ensure all functions are available
core_path = os.path.join(base_path, 'core')
security_file = os.path.join(core_path, 'security.py')

if os.path.exists(security_file):
    print(f"[API HOOK] Reloading core.security from {security_file}")
    spec = importlib.util.spec_from_file_location('core.security', security_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules['core.security'] = module
    spec.loader.exec_module(module)
    print(f"[API HOOK] core.security reloaded successfully")

api_path = os.path.join(base_path, 'api')

# List of modules to load (auth must be reloaded to use correct SECRET_KEY)
modules_to_load = ['auth', 'flows', 'tasks', 'reportistica', 'repo_update', 'settings_path', 'banks']

for module_name in modules_to_load:
    module_file = os.path.join(api_path, f'{module_name}.py')

    if os.path.exists(module_file):
        print(f"[API HOOK] Loading api.{module_name} from {module_file}")

        # Load the module using importlib
        spec = importlib.util.spec_from_file_location(f'api.{module_name}', module_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f'api.{module_name}'] = module
        spec.loader.exec_module(module)

        print(f"[API HOOK] Successfully loaded api.{module_name}")
    else:
        print(f"[API HOOK] WARNING: Could not find {module_file}")

print("[API HOOK] API modules loaded successfully!")
