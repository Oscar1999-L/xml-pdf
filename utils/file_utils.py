import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'xml'}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    if not filename or not isinstance(filename, str):
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_pairs(files):
    if not files:
        return False, "No se recibieron archivos"
    
    file_groups = {}
    for file in files:
        if not file or not file.filename:
            continue
            
        base_name = os.path.splitext(file.filename)[0]
        ext = os.path.splitext(file.filename)[1][1:].lower()
        
        if base_name not in file_groups:
            file_groups[base_name] = {}
        file_groups[base_name][ext] = file
    
    for base_name, extensions in file_groups.items():
        if 'pdf' not in extensions or 'xml' not in extensions:
            return False, f"El archivo {base_name} no tiene su par correspondiente (PDF y XML)"
    
    return True, ""

def save_uploaded_files(files, temp_dir):
    saved_files = []
    for file in files:
        if not file or not file.filename:
            continue
            
        filename = secure_filename(file.filename)
        if not filename:
            continue
            
        file_path = os.path.join(temp_dir, filename)
        try:
            file.save(file_path)
            saved_files.append(file_path)
        except Exception as e:
            print(f"Error guardando archivo {filename}: {str(e)}")
            continue
            
    return saved_files