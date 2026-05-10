@echo off
cd /d "c:\Users\Sonia_Ye\Documents\trae_projects\GBA TransPilot"
set FLASK_APP=app.py
set FLASK_ENV=development
python -m flask run --host=0.0.0.0 --port=5000
pause