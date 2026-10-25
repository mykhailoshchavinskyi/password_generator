import os

# GUI-тести працюють без дисплея (CI, SSH)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
