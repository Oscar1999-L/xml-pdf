import os
import time
import shutil
import io
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from .xml_to_pdf import XMLtoPDFConverter
from PIL import Image

class PDFProcessor:
    def __init__(self):
        self.temp_dir = "temp_pdfs"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.xml_converter = XMLtoPDFConverter()
        self.min_image_size = 10000  # Solo comprimir imágenes >100KB
        self.max_image_dimension = 800  # Máximo 800px en ancho/alto
        self.image_quality = 20  # Calidad JPEG (0-100)
    
    def _optimize_pdf(self, input_path, output_path):
        """Versión final corregida del optimizador"""
        try:
            reader = PdfReader(input_path)
            writer = PdfWriter()

            for page in reader.pages:
                # Método seguro para comprimir contenido
                self._safe_compress_page(page)
                writer.add_page(page)

            # Escribir con compresión
            with open(output_path, "wb") as f:
                writer.write(f)
            
            return True
        except Exception as e:
            print(f"Error en optimización: {str(e)}")
            return False

    def _safe_compress_page(self, page):
        """Compresión segura que evita el error IndirectObject"""
        try:
            if hasattr(page, 'compress_content_streams'):
                page.compress_content_streams()
            
            if '/Resources' in page:
                resources = page['/Resources'].get_object()
                if '/XObject' in resources:
                    x_objects = resources['/XObject'].get_object()
                    for obj in x_objects:
                        x_object = x_objects[obj].get_object()
                        if '/Subtype' in x_object and x_object['/Subtype'] == '/Image':
                            self._process_image_object(x_object)
        except Exception as e:
            print(f"Advertencia en compresión de página: {str(e)}")

    def _process_image_object(self, image_obj):
        """Procesamiento seguro de imágenes en PDF"""
        try:
            if '/Filter' in image_obj and image_obj['/Filter'] != '/FlateDecode':
                return

            if hasattr(image_obj, '_data'):
                original_data = image_obj._data
            else:
                original_data = image_obj.get_data()

            if len(original_data) > self.min_image_size:
                compressed_data = self._compress_with_pillow(original_data)
                if compressed_data and len(compressed_data) < len(original_data):
                    image_obj._data = compressed_data
                    image_obj.update({
                        '/Filter': '/FlateDecode',
                        '/Length': str(len(compressed_data))
                    })
        except Exception as e:
            print(f"Advertencia en procesamiento de imagen: {str(e)}")

    def _compress_with_pillow(self, image_data):
        """Compresión de imagen usando Pillow"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # Conversión a escala de grises para mayor compresión
            if img.mode != 'L':
                img = img.convert('L')
            
            # Reducción de tamaño
            if max(img.size) > self.max_image_dimension:
                img.thumbnail((self.max_image_dimension, self.max_image_dimension))
            
            # Guardar con compresión
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=self.image_quality, optimize=True)
            return output.getvalue()
        except Exception as e:
            print(f"Error en compresión Pillow: {str(e)}")
            return image_data

    def combinar_archivos(self, archivos, output_dir="resultados", modo="pares", output_name=None):
        """Versión final del método de combinación"""
        try:
            # Validación y preparación
            archivos = [f for f in archivos if os.path.exists(f)]
            if not archivos:
                print("Error: No se encontraron archivos válidos")
                return None

            os.makedirs(output_dir, exist_ok=True)
            output_name = output_name or "combinado.pdf"
            if not output_name.lower().endswith('.pdf'):
                output_name += '.pdf'

            output_path = os.path.join(output_dir, output_name)
            temp_files = []

            # Procesamiento según el modo
            merger = PdfMerger()
            temp_combined = os.path.join(self.temp_dir, "temp_combined.pdf")
            temp_files.append(temp_combined)

            if modo == "pares":
                self._process_pair_mode(merger, archivos, temp_files)
            else:
                self._process_full_mode(merger, archivos, temp_files)

            # Generar PDF combinado
            with open(temp_combined, "wb") as f:
                merger.write(f)

            # Optimización final
            if not self._optimize_pdf(temp_combined, output_path):
                shutil.copy(temp_combined, output_path)

            return output_path

        except Exception as e:
            print(f"Error crítico al combinar archivos: {str(e)}")
            return None
        finally:
            # Limpieza garantizada
            if 'merger' in locals():
                merger.close()
            self._cleanup_files(temp_files)

    def _process_pair_mode(self, merger, archivos, temp_files):
        """Procesamiento para modo pares"""
        grupos = {}
        for archivo in archivos:
            base = os.path.splitext(os.path.basename(archivo))[0]
            grupos.setdefault(base, []).append(archivo)

        for base, grupo in grupos.items():
            grupo.sort(key=lambda x: not x.lower().endswith('.pdf'))
            for archivo in grupo:
                if archivo.lower().endswith('.xml'):
                    temp_pdf = os.path.join(self.temp_dir, f"{base}_temp.pdf")
                    if self.xml_converter.convert(archivo, temp_pdf):
                        merger.append(temp_pdf)
                        temp_files.append(temp_pdf)
                else:
                    merger.append(archivo)

    def _process_full_mode(self, merger, archivos, temp_files):
        """Procesamiento para modo completo"""
        archivos.sort(key=lambda x: (
            os.path.splitext(os.path.basename(x))[0],
            not x.lower().endswith('.pdf')
        ))
        for archivo in archivos:
            if archivo.lower().endswith('.xml'):
                base = os.path.splitext(os.path.basename(archivo))[0]
                temp_pdf = os.path.join(self.temp_dir, f"{base}_temp.pdf")
                if self.xml_converter.convert(archivo, temp_pdf):
                    merger.append(temp_pdf)
                    temp_files.append(temp_pdf)
            else:
                merger.append(archivo)

    def _cleanup_files(self, temp_files):
        """Limpieza robusta de archivos temporales"""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    for _ in range(3):  # 3 intentos
                        try:
                            os.remove(temp_file)
                            break
                        except:
                            time.sleep(0.3)
            except:
                continue