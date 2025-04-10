import time
from PyPDF2 import PdfMerger
from flask import Flask, render_template, request, jsonify, send_file, session
import os
import tempfile
import zipfile
import fitz  # PyMuPDF
import io
import shutil
from PIL import Image, ImageEnhance
from threading import Timer, Lock
import uuid
from datetime import timedelta

# Importaciones de módulos locales
from converters.optimizer import optimize_pdf_size
from converters.xml_to_pdf import XMLtoPDFConverter
from converters.pdf_processor import PDFProcessor
from utils.file_utils import allowed_file, validate_file_pairs, save_uploaded_files

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['SECRET_KEY'] = os.urandom(24)  # Clave secreta aleatoria
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
ALLOWED_EXTENSIONS = {'pdf', 'xml'}

# Sistema de manejo de archivos por usuario
processed_files_lock = Lock()
processed_files = {}

@app.route('/health')
def health_check():
    return "OK", 200

@app.before_request
def before_request():
    # Inicializar sesión si no existe
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session.permanent = True

def cleanup_user_files(user_id):
    """Limpia los archivos de un usuario específico"""
    with processed_files_lock:
        if user_id in processed_files:
            file_info = processed_files.pop(user_id)
            try:
                if os.path.exists(file_info['path']):
                    os.remove(file_info['path'])
                    temp_dir = os.path.dirname(file_info['path'])
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
            except Exception as e:
                app.logger.error(f"Error cleaning user {user_id} files: {str(e)}")

def cleanup_temp_files(temp_dir):
    """Limpia archivos temporales de forma segura"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        app.logger.error(f"Error al limpiar archivos temporales: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Sesión no válida'}), 401
    
    try:
        # Validación básica de parámetros
        modo = request.form.get('modo', 'pares')
        if modo not in ['pares', 'completo', 'solopdf']:
            return jsonify({'error': 'Modo de operación no válido'}), 400

        color_mode = request.form.get('color_mode', 'grayscale')
        grayscale = color_mode == 'grayscale'
        custom_name = request.form.get('custom_name', '').strip()

        # Validación de archivos
        if 'files' not in request.files:
            return jsonify({'error': 'No se seleccionaron archivos'}), 400

        uploaded_files = request.files.getlist('files')
        if not uploaded_files:
            return jsonify({'error': 'Lista de archivos vacía'}), 400

        # Filtrar archivos válidos
        valid_files = [
            f for f in uploaded_files 
            if f and f.filename and allowed_file(f.filename)
        ]
        
        if not valid_files:
            return jsonify({'error': 'Ningún archivo válido recibido'}), 400

        # Validación específica por modo
        if modo == 'pares':
            is_valid, message = validate_file_pairs(valid_files)
            if not is_valid:
                return jsonify({'error': message}), 400
        elif modo == 'solopdf':
            valid_files = [f for f in valid_files if f.filename.lower().endswith('.pdf')]
            if not valid_files:
                return jsonify({'error': 'Se requieren archivos PDF en este modo'}), 400

        # Crear directorios temporales únicos por usuario
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_")
        output_dir = os.path.join(temp_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Guardar archivos subidos
            saved_files = []
            for file in valid_files:
                filename = file.filename
                file_path = os.path.join(temp_dir, filename)
                file.save(file_path)
                saved_files.append(file_path)

            # Procesamiento según modo
            processor = PDFProcessor()
            combined_pdfs = []

            if modo == 'pares':
                # Procesamiento para modo pares
                file_groups = {}
                for file_path in saved_files:
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    ext = os.path.splitext(file_path)[1].lower()
                    
                    if base_name not in file_groups:
                        file_groups[base_name] = {}
                    
                    if ext == '.pdf':
                        file_groups[base_name]['pdf'] = file_path
                    else:
                        file_groups[base_name]['xml'] = file_path

                for base_name, files in file_groups.items():
                    if not files.get('pdf') or not files.get('xml'):
                        continue

                    # Procesar PDF
                    pdf_output = os.path.join(output_dir, f"{base_name}_processed.pdf")
                    if grayscale:
                        optimized_pdf = optimize_pdf_size(
                            input_path=files['pdf'],
                            output_dir=output_dir,
                            grayscale=True
                        )
                        if optimized_pdf:
                            shutil.move(optimized_pdf, pdf_output)
                    else:
                        shutil.copy(files['pdf'], pdf_output)

                    # Procesar XML
                    xml_pdf = os.path.join(output_dir, f"{base_name}_xml.pdf")
                    if not processor._convert_xml_to_pdf(files['xml'], xml_pdf, is_xml_converted=True):
                        continue

                    # Combinar
                    merged_pdf = os.path.join(output_dir, f"{base_name}_merged.pdf")
                    merger = PdfMerger()
                    try:
                        merger.append(pdf_output)
                        merger.append(xml_pdf)
                        merger.write(merged_pdf)
                        combined_pdfs.append(merged_pdf)
                    finally:
                        merger.close()

                zip_output_name = custom_name or "documentos_combinados_por_pares"

            elif modo == 'solopdf':
                # Procesamiento para solo PDFs
                output_pdf = os.path.join(output_dir, custom_name + ".pdf") if custom_name else os.path.join(output_dir, "combined.pdf")
                
                try:
                    # Filtrar solo archivos PDF
                    pdf_files = [f for f in saved_files if f.lower().endswith('.pdf')]
                    if not pdf_files:
                        raise ValueError("No se encontraron archivos PDF para combinar")

                    if grayscale:
                        # Procesar cada PDF individualmente en escala de grises antes de combinar
                        processed_pdfs = []
                        for pdf_file in pdf_files:
                            gray_pdf = os.path.join(temp_dir, f"gray_{os.path.basename(pdf_file)}")
                            optimized = optimize_pdf_size(
                                input_path=pdf_file,
                                output_dir=temp_dir,
                                grayscale=True
                            )
                            if optimized:
                                processed_pdfs.append(optimized)
                        
                        if not processed_pdfs:
                            raise ValueError("Fallo al procesar PDFs en escala de grises")
                        
                        # Combinar los PDFs procesados
                        result = processor.combinar_archivos(
                            processed_pdfs,
                            output_path=output_pdf,
                            modo="solopdf",
                            grayscale=False  # Ya están procesados
                        )
                    else:
                        # Combinar directamente sin conversión
                        result = processor.combinar_archivos(
                            pdf_files,
                            output_path=output_pdf,
                            modo="solopdf",
                            grayscale=False
                        )

                    if result and os.path.exists(output_pdf):
                        combined_pdfs.append(output_pdf)
                        
                except Exception as e:
                    app.logger.error(f"Error combinando PDFs: {str(e)}")
                    raise

                zip_output_name = custom_name or "pdfs_combinados"

            else:  # Modo completo
                output_pdf = os.path.join(output_dir, custom_name + ".pdf") if custom_name else os.path.join(output_dir, "completo.pdf")
                
                try:
                    result = processor.combinar_archivos(
                        saved_files, 
                        output_path=output_pdf, 
                        modo="completo",
                        grayscale=grayscale
                    )
                    
                    if result and os.path.exists(output_pdf):
                        combined_pdfs.append(output_pdf)
                        
                except Exception as e:
                    app.logger.error(f"Error combinando archivos completos: {str(e)}")
                    raise

                zip_output_name = custom_name or "documento_completo"

            # Crear archivo ZIP resultante
            if not combined_pdfs:
                return jsonify({'error': 'No se generaron archivos de salida'}), 500

            zip_filename = f"{zip_output_name}_{user_id}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)

            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for pdf in combined_pdfs:
                    if os.path.exists(pdf):
                        zipf.write(pdf, os.path.basename(pdf))

            # Guardar referencia al archivo con lock
            with processed_files_lock:
                processed_files[user_id] = {
                    'path': zip_path,
                    'timestamp': time.time()
                }

            # Programar limpieza
            cleanup_time = 300  # 5 minutos
            Timer(cleanup_time, cleanup_user_files, args=[user_id]).start()

            return jsonify({
                'success': True,
                'filename': os.path.basename(zip_path),
                'modo': modo,
                'custom_name_used': bool(custom_name),
                'color_mode': color_mode
            })

        except Exception as e:
            app.logger.error(f"Error en el procesamiento: {str(e)}")
            cleanup_temp_files(temp_dir)
            return jsonify({'error': f'Error en el procesamiento: {str(e)}'}), 500

    except Exception as e:
        app.logger.error(f"Error general: {str(e)}")
        return jsonify({'error': f'Error en el servidor: {str(e)}'}), 500

@app.route('/download', methods=['GET'])
def download_file():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Sesión no válida'}), 401

    with processed_files_lock:
        file_info = processed_files.get(user_id)
    
    if not file_info or not os.path.exists(file_info['path']):
        return jsonify({'error': 'El archivo no está disponible o ha expirado. Por favor, procesa los archivos nuevamente.'}), 404
    
    try:
        filename = request.args.get('filename', os.path.basename(file_info['path']))
        response = send_file(
            file_info['path'],
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
        # Limpiar después de descargar
        Timer(1, cleanup_user_files, args=[user_id]).start()
        
        return response
    except Exception as e:
        app.logger.error(f"Error al descargar archivo: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)