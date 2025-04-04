import time
from flask import Flask, render_template, request, jsonify, send_file
import os
import tempfile
import zipfile
import fitz  # PyMuPDF
import io
import shutil
from PIL import Image, ImageEnhance
from threading import Timer
from converters.xml_to_pdf import XMLtoPDFConverter
from converters.pdf_processor import PDFProcessor
from utils.file_utils import allowed_file, validate_file_pairs, save_uploaded_files

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'pdf', 'xml'}


@app.route('/health')
def health_check():
    return "OK", 200

last_processed_file = None

def cleanup_temp_files(temp_dir):
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
    modo = request.form.get('modo', 'pares')
    color_mode = request.form.get('color_mode', 'grayscale')
    if color_mode not in ['grayscale', 'color']:
        color_mode = 'grayscale'
    grayscale = color_mode == 'grayscale'
    custom_name = request.form.get('custom_name', '').strip()

    if 'files' not in request.files:
        return jsonify({'error': 'No se seleccionaron archivos'}), 400

    files = request.files.getlist('files')
    files = [f for f in files if f and hasattr(f, 'filename') and f.filename and allowed_file(f.filename)]

    if len(files) < 1:
        return jsonify({'error': 'Debes subir al menos 1 archivo válido'}), 400

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
            file_groups = {}
            for file_path in saved_files:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                if base_name not in file_groups:
                    file_groups[base_name] = []
                file_groups[base_name].append(file_path)

            for base_name, file_group in file_groups.items():
                try:
                    output_path = os.path.join(output_dir, f"{base_name}.pdf")
                    combined_pdf = processor.combinar_archivos(
                        file_group,
                        output_path=output_path,  # Cambiado de output_dir/output_name a output_path
                        modo="pares"
                    )
                    if combined_pdf and os.path.exists(combined_pdf):
                        processed_pdf = optimize_pdf_size(
                            combined_pdf, 
                            output_dir=output_dir,
                            grayscale=grayscale
                        )
                        if processed_pdf:
                            combined_pdfs.append(processed_pdf)
                except Exception as e:
                    app.logger.error(f"Error procesando grupo {base_name}: {str(e)}")
                    continue

            zip_output_name = custom_name if custom_name else "documentos_combinados_por_pares"

        else:
            output_name = f"{custom_name}.pdf" if custom_name else "documento_completo.pdf"
            output_path = os.path.join(output_dir, output_name)
            
            try:
                combined_pdf = processor.combinar_archivos(
                    saved_files,
                    output_path=output_path,  # Cambiado de output_dir/output_name a output_path
                    modo="completo"
                )
                if combined_pdf and os.path.exists(combined_pdf):
                    processed_pdf = optimize_pdf_size(
                        combined_pdf,
                        output_dir=output_dir,
                        grayscale=grayscale
                    )
                    if processed_pdf:
                        combined_pdfs.append(processed_pdf)
                else:
                    raise Exception("No se pudo crear el PDF combinado")
                    
            except Exception as e:
                app.logger.error(f"Error combinando archivos: {str(e)}")
                return jsonify({'error': f'Error al combinar archivos: {str(e)}'}), 500

            zip_output_name = custom_name if custom_name else "documento_completo"

        if not combined_pdfs:
            return jsonify({'error': 'No se pudieron procesar los archivos'}), 500

        zip_filename = f"{zip_output_name}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
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
            'custom_name_used': bool(custom_name),
            'color_mode': color_mode
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


def optimize_pdf_size(input_pdf, output_dir=None, target_dpi=150, grayscale=False):
    """Optimiza un PDF manteniendo texto vectorial y mejorando la legibilidad."""
    try:
        if not os.path.exists(input_pdf):
            print(f"Archivo no encontrado: {input_pdf}")
            return None
        
        output_dir = output_dir or os.path.dirname(input_pdf)
        os.makedirs(output_dir, exist_ok=True)
        
        output_pdf = os.path.join(output_dir, f"opt_{os.path.basename(input_pdf)}")
        
        # Abrimos el documento original y creamos uno nuevo
        src_doc = fitz.open(input_pdf)
        dst_doc = fitz.open()
        
        for page in src_doc:
            new_page = dst_doc.new_page(width=page.rect.width, height=page.rect.height)

            if grayscale:
                # Extraer texto y bloques
                text_blocks = page.get_text("blocks")
                images = page.get_images(full=True)

                # Convertir la página completa a escala de grises (sin texto)
                pix = page.get_pixmap(dpi=max(target_dpi, 150), colorspace=fitz.csGRAY, alpha=False)
                new_page.insert_image(new_page.rect, pixmap=pix)

                # Reinsertar texto en negro sólido para mayor claridad
                tw = fitz.TextWriter(new_page.rect)
                for block in text_blocks:
                    if block[6]:  # Si el bloque contiene texto
                        x0, y0, _, _, text, *_ = block
                        tw.append((x0, y0), text)
                tw.write_text(new_page, color=(0, 0, 0))  # Texto en negro puro
                
                # Procesar imágenes individualmente con mejora de contraste y compresión
                for img in images:
                    xref = img[0]

                    try:
                        # Extraer imagen del PDF
                        base_image = src_doc.extract_image(xref)
                        if not base_image or "image" not in base_image:
                            print(f"Advertencia: Imagen en xref {xref} es nula o no extraíble, saltando...")
                            continue

                        # Añade esta validación adicional:
                        if not base_image.get("width", 0) or not base_image.get("height", 0):
                            print(f"Imagen en xref {xref} tiene dimensiones inválidas, saltando...")
                            continue

                        # Validar tamaño y formato de la imagen extraída
                        img_bytes = base_image["image"]
                        if len(img_bytes) < 100:  # Tamaño mínimo de imagen razonable
                            print(f"Imagen en xref {xref} es demasiado pequeña, ignorando...")
                            continue

                        img_pil = Image.open(io.BytesIO(img_bytes))

                        # Verificar si la imagen es un formato soportado
                        if img_pil.format not in ["JPEG", "PNG", "TIFF"]:
                            print(f"Formato de imagen en xref {xref} no soportado ({img_pil.format}), ignorando...")
                            continue

                        if img_pil.mode != "L":
                            img_pil = img_pil.convert("L")
                        
                        # Mejorar contraste para mayor legibilidad
                        enhancer = ImageEnhance.Contrast(img_pil)
                        img_pil = enhancer.enhance(1.5)

                        # Convertir a JPEG con compresión optimizada
                        img_bytes = io.BytesIO()
                        img_pil.save(img_bytes, format="JPEG", quality=85, optimize=True)
                        img_bytes.seek(0)

                        # Guardar en archivo temporal con un nombre único
                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                            tmp.write(img_bytes.read())
                            img_rect = page.get_image_bbox(xref)
                            new_page.insert_image(img_rect, filename=tmp.name)

                        os.unlink(tmp.name)  # Eliminar archivo temporal después de usarlo
                    except Exception as e:
                        print(f"Error procesando imagen en xref {xref}: {str(e)}")
            else:
                # Si no es escala de grises, copiar la página original
                new_page.show_pdf_page(new_page.rect, src_doc, page.number)
        
        # Opciones de guardado optimizadas
        save_options = {
            "garbage": 4,
            "deflate": True,
            "clean": True
        }
        
        dst_doc.save(output_pdf, **save_options)
        
        # Cerrar documentos correctamente
        src_doc.close()
        dst_doc.close()
        
        print(f"PDF optimizado guardado en: {output_pdf}")
        return output_pdf

    except Exception as e:
        print(f"Error al optimizar PDF: {str(e)}")
    finally:
        # Asegurar que los documentos se cierran en caso de error
        if 'src_doc' in locals() and not src_doc.is_closed:
            src_doc.close()
        if 'dst_doc' in locals() and not dst_doc.is_closed:
            dst_doc.close()
    
    return None
