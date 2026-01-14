from io import BytesIO
import fitz  # PyMuPDF
import docx

def extract_text_from_pdf(uploaded_file):
    # read bytes from the uploaded file (stream)
    file_bytes = uploaded_file.read()
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text

def extract_text_from_docx(uploaded_file):
    file_bytes = uploaded_file.read()
    doc_obj = docx.Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc_obj.paragraphs)
