import pyinstaller_versionfile

pyinstaller_versionfile.create_versionfile(
    output_file="pdfviewer\\versionfile.txt",
    version="0.0.1.1",
    company_name="Igor Stepanenkov",
    file_description="Mini PDF Tools",
    internal_name="Mini PDF Tools",
    legal_copyright="© Igor Stepanenkov. All rights reserved.",
    original_filename="minipdftools.exe",
    product_name="Mini PDF Tools",
    translations=[0x419, 1251]
)