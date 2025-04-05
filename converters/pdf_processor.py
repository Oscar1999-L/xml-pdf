import os
import shutil
from PyPDF2 import PdfMerger, PdfWriter, PdfReader
from converters.xml_to_pdf import XMLtoPDFConverter
from converters.optimizer import optimize_pdf_size

class PDFProcessor:
    def __init__(self):
        self.temp_dir = "temp_pdfs"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.xml_converter = XMLtoPDFConverter()

    def _convert_xml_to_pdf(self, xml_path, output_pdf, is_xml_converted=False):  # <- Parámetro añadido
        """Convierte XML a PDF manteniendo texto vectorial"""
        try:
            return self.xml_converter.convert(xml_path, output_pdf, is_xml_converted)  # <- Pasar parámetro
        except Exception as e:
            print(f"Error convirtiendo {xml_path}: {str(e)}")
            return False

        
    def combinar_archivos(self, archivos, output_path, modo="pares", grayscale=False):
        """Combina archivos garantizando orden y sin conversión a imagen"""
        try:
            archivos = [f for f in archivos if os.path.exists(f)]
            if not archivos:
                raise ValueError("No hay archivos válidos para combinar")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Ordenar archivos
            archivos_ordenados = sorted(archivos, key=lambda x: (
                os.path.splitext(os.path.basename(x))[0],
                not x.lower().endswith('.pdf')
            ))

            merger = PdfMerger()
            temp_files = []

            try:
                for archivo in archivos_ordenados:
                    if archivo.lower().endswith('.pdf'):
                        if grayscale:
                            # Procesar PDF en escala de grises antes de agregar
                            temp_pdf = os.path.join(self.temp_dir, f"gray_{os.path.basename(archivo)}")
                            optimized = optimize_pdf_size(
                                input_path=archivo,  # Cambiado a input_path
                                output_dir=self.temp_dir,  # Cambiado a output_dir
                                grayscale=True
                            )
                            if optimized:
                                temp_files.append(optimized)  # Usamos el path retornado
                                merger.append(optimized)
                            else:
                                merger.append(archivo)
                        else:
                            merger.append(archivo)
                    elif archivo.lower().endswith('.xml'):
                        temp_pdf = os.path.join(self.temp_dir, f"temp_{os.path.basename(archivo)}.pdf")
                        if self._convert_xml_to_pdf(archivo, temp_pdf, is_xml_converted=True):
                            temp_files.append(temp_pdf)
                            merger.append(temp_pdf)

                merger.write(output_path)
                return output_path
            finally:
                merger.close()
                self._limpiar_temporales(temp_files)
        
        except Exception as e:
            print(f"Error en combinar_archivos: {str(e)}")
            return None

    def _limpiar_temporales(self, files):
        """Limpia archivos temporales"""
        for f in files:
            try:
                if os.path.exists(f) and f.startswith(self.temp_dir):
                    os.remove(f)
            except Exception as e:
                print(f"No se pudo eliminar {f}: {str(e)}")