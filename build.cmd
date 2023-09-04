rem pyinstaller --onefile -i .\bounds.ico -w .\bounds.py
rem pyinstaller minipdftools.spec
pyinstaller -i .\images\pdf.ico -w -y -n minipdftools --version-file versionfile.txt --add-binary add_bins\*.*;. --add-data add_datas\*.*;. .\main.py
