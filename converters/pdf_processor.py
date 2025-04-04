import os
import shutil
from PyPDF2 import PdfMerger, PdfWriter, PdfReader
from concurrent.futures import ThreadPoolExecutor
from converters.xml_to_pdf import XMLtoPDFConverter

class PDFProcessor:
    def __init__(self):
        self.temp_dir = "temp_pdfs"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.xml_converter = XMLtoPDFConverter()
        self.merge_chunk_size = 10
        self.max_workers = 4

    def _convert_xml_to_pdf(self, xml_path, output_pdf):
        """Convierte XML a PDF con manejo de errores"""
        try:
            return self.xml_converter.convert(xml_path, output_pdf)
        except Exception as e:
            print(f"Error convirtiendo {xml_path}: {str(e)}")
            return False

    def _optimize_pdf(self, input_path):
        """Optimiza un PDF individual con parámetros compatibles"""
        try:
            reader = PdfReader(input_path)
            writer = PdfWriter()

            for page in reader.pages:
                # Versión compatible de compresión
                page.compress_content_streams()  # Sin parámetro 'level'
                writer.add_page(page)

            temp_path = os.path.join(self.temp_dir, f"opt_{os.path.basename(input_path)}")
            with open(temp_path, 'wb') as f:
                writer.write(f)
            
            return temp_path
        except Exception as e:
            print(f"Error optimizando PDF: {str(e)}")
            return input_path

    def combinar_archivos(self, archivos, output_path, modo="pares"):
        """Combina archivos en un solo PDF"""
        try:
            archivos = [f for f in archivos if os.path.exists(f)]
            if not archivos:
                raise ValueError("No hay archivos válidos para combinar")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            merger = PdfMerger()
            temp_files = []

            try:
                if modo == "pares":
                    grupos = {}
                    for archivo in archivos:
                        base = os.path.splitext(os.path.basename(archivo))[0]
                        if archivo.lower().endswith('.xml'):
                            base = base[:-4]  # Quitar .xml para agrupar bien
                        grupos.setdefault(base, []).append(archivo)

                    for grupo in grupos.values():
                        pdfs = sorted([f for f in grupo if f.lower().endswith('.pdf')])
                        xmls = sorted([f for f in grupo if f.lower().endswith('.xml')])

                        for archivo in pdfs:
                            optimized = self._optimize_pdf(archivo)
                            if optimized:
                                temp_files.append(optimized)
                                merger.append(optimized)

                        for archivo in xmls:
                            temp_pdf = os.path.join(self.temp_dir, f"temp_{os.path.basename(archivo)}.pdf")
                            if self._convert_xml_to_pdf(archivo, temp_pdf):
                                temp_files.append(temp_pdf)
                                merger.append(temp_pdf)
                else:
                    for archivo in archivos:
                        if archivo.lower().endswith('.xml'):
                            temp_pdf = os.path.join(self.temp_dir, f"temp_{os.path.basename(archivo)}.pdf")
                            if self._convert_xml_to_pdf(archivo, temp_pdf):
                                temp_files.append(temp_pdf)
                                merger.append(temp_pdf)
                        else:
                            optimized = self._optimize_pdf(archivo)
                            if optimized:
                                temp_files.append(optimized)
                                merger.append(optimized)

                merger.write(output_path)
                return output_path

            finally:
                merger.close()
                self._limpiar_temporales(temp_files)

        except Exception as e:
            print(f"Error en combinar_archivos: {str(e)}")
            return None

    def _limpiar_temporales(self, files):
        """Limpia archivos temporales de forma segura"""
        for f in files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as e:
                print(f"No se pudo eliminar {f}: {str(e)}")
