import glob

files = glob.glob('src/dnf_gui/ui/pages/*.py')
for fn in files:
    with open(fn, 'r') as f:
        content = f.read()
    
    # Replace 16 spaces before layout.addWidget(header) with 8 spaces
    # It might be 8 spaces + 8 spaces because the string removed the text but left the 8 spaces indentation of that line
    content = content.replace("                layout.addWidget(header)", "        layout.addWidget(header)")
    
    with open(fn, 'w') as f:
        f.write(content)
