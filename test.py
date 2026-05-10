print("Testing Python environment...")
import sys
print(f"Python version: {sys.version}")

try:
    from flask import Flask
    print("Flask imported successfully")
except ImportError as e:
    print(f"Flask import error: {e}")

try:
    import google.generativeai as genai
    print("Google Generative AI imported successfully")
except ImportError as e:
    print(f"Google AI import error: {e}")