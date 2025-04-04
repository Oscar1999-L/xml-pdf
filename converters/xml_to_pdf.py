import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from fpdf import FPDF

class XMLtoPDFConverter:
    def __init__(self):
        # Configuración de PDF
        self.margen = 10
        self.ancho_util = 210 - 2 * self.margen  # A4 (210mm) - márgenes
        self.espaciado_lineas = 3
        self.fuente_cuerpo = "Courier"
        self.tam_fuente_cuerpo = 6
        self.fuente_titulo = "Arial"
        self.tam_fuente_titulo = 14

    def format_xml_text(self, xml_text):
        """Formatea el XML con indentación (pretty print)"""
        try:
            dom = minidom.parseString(xml_text)
            return [line.strip() for line in dom.toprettyxml(indent='  ').split("\n") if line.strip()]
        except Exception as e:
            print(f"Error al formatear XML: {str(e)}")
            return []

    def convertir_xml_a_txt(self, ruta_xml, ruta_txt):
        """Convierte XML a TXT con formato legible"""
        try:
            # Leer el contenido del XML
            with open(ruta_xml, 'r', encoding='utf-8') as archivo_xml:
                xml_content = archivo_xml.read()
            
            # Formatear el XML para que sea legible
            formatted_lines = self.format_xml_text(xml_content)
            
            # Escribir las líneas formateadas en el TXT
            with open(ruta_txt, 'w', encoding='utf-8') as archivo_txt:
                archivo_txt.write("\n".join(formatted_lines))
            
            print(f"XML convertido a TXT legible: {ruta_txt}")
            return True
        except Exception as e:
            print(f"Error al convertir XML a TXT: {str(e)}")
            return False

    def convertir_txt_a_pdf(self, ruta_txt, ruta_pdf, nombre_xml=None):
        """Convierte TXT a PDF con formato mejorado"""
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_margins(left=self.margen, top=self.margen, right=self.margen)

            # Añadir título con nombre del XML
            nombre_mostrar = nombre_xml if nombre_xml else os.path.splitext(os.path.basename(ruta_txt))[0]
            pdf.set_font(self.fuente_titulo, "B", self.tam_fuente_titulo)
            pdf.cell(0, 10, txt=f"Archivo: {nombre_mostrar}", ln=True, align="C")
            pdf.ln(6)  # Espacio después del título

            # Configurar cuerpo
            pdf.set_font(self.fuente_cuerpo, size=self.tam_fuente_cuerpo)

            with open(ruta_txt, "r", encoding="utf-8") as txt_file:
                for linea in txt_file:
                    linea = linea.strip()
                    if linea:
                        pdf.multi_cell(
                            w=self.ancho_util,
                            h=self.espaciado_lineas,
                            txt=linea,
                            border=0,
                            align="L",
                        )
                        pdf.ln(2)

            pdf.output(ruta_pdf)
            print(f"PDF generado en: {ruta_pdf}")
            return True
        except Exception as e:
            print(f"Error al convertir TXT a PDF: {str(e)}")
            return False

    def convert(self, xml_path, output_pdf):
        """Método unificado para compatibilidad con pdf_processor.py"""
        temp_txt = os.path.join(os.path.dirname(output_pdf), "temp_xml.txt")
        
        if not self.convertir_xml_a_txt(xml_path, temp_txt):
            return False
            
        # Obtener nombre del XML sin extensión
        nombre_xml = os.path.splitext(os.path.basename(xml_path))[0]
            
        if not self.convertir_txt_a_pdf(temp_txt, output_pdf, nombre_xml=nombre_xml):
            return False
            
        # Limpieza
        if os.path.exists(temp_txt):
            os.remove(temp_txt)
        return True
