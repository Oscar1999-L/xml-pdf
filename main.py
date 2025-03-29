import time
from flask import Flask, render_template, request, jsonify, send_file
import os
import tempfile
import zipfile
import fitz  # PyMuPDF
import io
import shutil
from PIL import Image
from threading import Timer
from converters.xml_to_pdf import XMLtoPDFConverter
from converters.pdf_processor import PDFProcessor
from utils.file_utils import allowed_file, validate_file_pairs, save_uploaded_files

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'pdf', 'xml'}

# Variable global para almacenar el último archivo procesado
last_processed_file = None

def cleanup_temp_files(temp_dir):
    """Elimina los archivos temporales después de un tiempo"""
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        app.logger.error(f"Error al limpiar archivos temporales: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    global last_processed_file

    if 'files' not in request.files:
        return jsonify({'error': 'No se seleccionaron archivos'}), 400

    files = request.files.getlist('files')
    files = [f for f in files if f and hasattr(f, 'filename') and f.filename and allowed_file(f.filename)]

    if len(files) < 1:
        return jsonify({'error': 'Debes subir al menos 1 archivo válido'}), 400

    # Obtener parámetros
    modo = request.form.get('modo', 'pares')
    custom_name = request.form.get('custom_name', '').strip()

    # Validación específica por modo
    if modo == 'pares':
        is_valid, message = validate_file_pairs(files)
        if not is_valid:
            return jsonify({'error': message}), 400

    try:
        temp_dir = tempfile.mkdtemp()
        saved_files = save_uploaded_files(files, temp_dir)

        processor = PDFProcessor()
        output_dir = os.path.join(temp_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)

        combined_pdfs = []
        
        if modo == 'pares':
            # Procesamiento por pares (PDFs mantienen sus nombres)
            file_groups = {}
            for file_path in saved_files:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                if base_name not in file_groups:
                    file_groups[base_name] = []
                file_groups[base_name].append(file_path)

            for base_name, file_group in file_groups.items():
                try:
                    output_name = f"{base_name}.pdf"  # Mantener nombre original
                    combined_pdf = processor.combinar_archivos(
                        file_group,
                        output_dir=output_dir,
                        output_name=output_name,
                        modo="pares"
                    )
                    if combined_pdf and os.path.exists(combined_pdf):
                        processed_pdf = optimize_pdf_size(combined_pdf, output_dir=output_dir)
                        if processed_pdf:
                            combined_pdfs.append(processed_pdf)
                except Exception as e:
                    app.logger.error(f"Error procesando grupo {base_name}: {str(e)}")
                    continue

            # Nombre del ZIP
            zip_output_name = custom_name if custom_name else "documentos_combinados_por_pares"

        else:  # Modo completo
            # Procesar todo en un solo PDF
            output_name = f"{custom_name}.pdf" if custom_name else "documento_completo.pdf"
            combined_pdf = processor.combinar_archivos(
                saved_files,
                output_dir=output_dir,
                output_name=output_name,
                modo="completo"
            )
            if combined_pdf and os.path.exists(combined_pdf):
                processed_pdf = optimize_pdf_size(combined_pdf, output_dir=output_dir)
                if processed_pdf:
                    combined_pdfs.append(processed_pdf)

            # Nombre del ZIP (mismo que el PDF pero sin extensión)
            zip_output_name = custom_name if custom_name else "documento_completo"

        if not combined_pdfs:
            return jsonify({'error': 'No se pudieron procesar los archivos'}), 500

        # Crear ZIP con el nombre adecuado
        zip_filename = f"{zip_output_name}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for pdf in combined_pdfs:
                if pdf and os.path.exists(pdf):
                    arcname = os.path.basename(pdf)
                    zipf.write(pdf, arcname)

        last_processed_file = zip_path
        Timer(300, cleanup_temp_files, args=[temp_dir]).start()

        return jsonify({
            'success': True,
            'filename': os.path.basename(zip_path),
            'modo': modo,
            'custom_name_used': bool(custom_name)
        })

    except Exception as e:
        app.logger.error(f'Error inesperado: {str(e)}')
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500


@app.route('/download', methods=['GET'])
def download_file():
    global last_processed_file
    
    if not last_processed_file or not os.path.exists(last_processed_file):
        return jsonify({'error': 'No hay archivos para descargar'}), 404
    
    try:
        filename = request.args.get('filename', os.path.basename(last_processed_file))
        return send_file(
            last_processed_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
    except Exception as e:
        app.logger.error(f"Error al descargar archivo: {str(e)}")
        return jsonify({'error': str(e)}), 500

def optimize_pdf_size(input_pdf, output_dir=None, target_dpi=300):
    """Optimiza el tamaño del PDF manteniendo escala de grises"""
    try:
        if not os.path.exists(input_pdf):
            app.logger.error(f"Archivo no encontrado: {input_pdf}")
            return None
        
        output_dir = output_dir or os.path.dirname(input_pdf)
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(input_pdf))[0]
        output_pdf = os.path.join(output_dir, f"{base_name}_optimized.pdf")
        
        doc = fitz.open(input_pdf)
        new_doc = fitz.open()
        
        # Fuentes seguras disponibles en PyMuPDF
        safe_fonts = {
            'helv': 'Helvetica',
            'cour': 'Courier',
            'tiro': 'Times-Roman'
        }
        
        for page in doc:
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            
            # Fondo blanco en escala de grises
            new_page.draw_rect(new_page.rect, color=(0, 0, 0), fill=(1, 1, 1))
            
            # Procesar imágenes
            for img in page.get_images(full=True):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    if not base_image or "image" not in base_image:
                        continue
                        
                    img_pil = Image.open(io.BytesIO(base_image["image"]))
                    img_pil = img_pil.convert("L")  # Escala de grises
                    
                    if max(img_pil.size) > 1200:
                        img_pil.thumbnail((1200, 1200))
                    
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_img:
                        temp_path = temp_img.name
                        img_pil.save(temp_path, "JPEG", quality=20, optimize=True)
                        
                        img_rects = page.get_image_rects(xref)
                        if img_rects:
                            new_page.insert_image(img_rects[0], filename=temp_path)
                        
                    os.unlink(temp_path)
                except Exception as e:
                    app.logger.warning(f"Error procesando imagen: {str(e)}")
                    continue
            
            # Procesar texto con manejo seguro de fuentes
            text_blocks = page.get_text("dict").get("blocks", [])
            for block in text_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            try:
                                bbox = fitz.Rect(span["bbox"])
                                new_page.draw_rect(bbox, color=(0, 0, 0), fill=(1, 1, 1))
                                
                                # Manejo seguro de fuentes
                                font_name = span.get("font", "helv").lower()
                                safe_font = safe_fonts.get(font_name, 'Helvetica')
                                
                                new_page.insert_text(
                                    span["origin"],
                                    span["text"],
                                    fontname=safe_font,
                                    fontsize=max(span.get("size", 8), 6),
                                    color=(0, 0, 0),
                                    overlay=True
                                )
                            except Exception as e:
                                app.logger.warning(f"Error insertando texto: {str(e)}")
                                continue
            
            # Procesar XML con fondo diferenciado
            xml_blocks = [b for b in text_blocks if any(tag in b.get("text", "") 
                          for tag in ["<?xml", "<cfdi:", "<tfd:", "<xs:", "<!["])]
            
            for block in xml_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            try:
                                bbox = fitz.Rect(span["bbox"])
                                new_page.draw_rect(bbox, color=(0, 0, 0), fill=(0.95, 0.95, 0.95))
                                new_page.insert_text(
                                    span["origin"],
                                    span["text"],
                                    fontname='Courier',
                                    fontsize=max(span.get("size", 8), 7),
                                    color=(0, 0, 0),
                                    overlay=True
                                )
                            except:
                                continue
            
            # Renderizar gráficos en escala de grises
            try:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(target_dpi/72, target_dpi/72),
                    colorspace=fitz.csGRAY,
                    alpha=False
                )
                new_page.insert_image(new_page.rect, pixmap=pix, overlay=True)
            except Exception as e:
                app.logger.error(f"Error renderizando gráficos: {str(e)}")

        save_options = {
            "garbage": 4,
            "deflate": True,
            "deflate_images": True,
            "deflate_fonts": True,
            "clean": True
        }
        
        new_doc.save(output_pdf, **save_options)
        new_doc.close()
        doc.close()
        
        app.logger.info(f"PDF optimizado guardado en: {output_pdf}")
        return output_pdf
        
    except Exception as e:
        app.logger.error(f"Error al optimizar PDF: {str(e)}")
        return None

if __name__ == '__main__':
    app.run(debug=True)