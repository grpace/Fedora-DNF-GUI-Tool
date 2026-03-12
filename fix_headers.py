import glob
import os

files = glob.glob('src/dnf_gui/ui/pages/*.py')
for fn in files:
    with open(fn, 'r') as f:
        content = f.read()
    
    # Remove header.setContentsMargins(0, 24, 0, 0)
    content = content.replace("header.setContentsMargins(0, 24, 0, 0)\n", "")
    
    with open(fn, 'w') as f:
        f.write(content)
