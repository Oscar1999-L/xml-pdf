import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from fpdf import FPDF

class XMLtoPDFConverter:
    def __init__(self):
        self.margen = 10
        self.ancho_util = 210 - 2 * self.margen
        self.espaciado_lineas = 2
        self.fuente_cuerpo = "Courier"
        self.tam_fuente_cuerpo = 6
        self.fuente_titulo = "Arial"
        self.tam_fuente_titulo = 10
        self.max_titulo_ancho = 180

    def format_xml_text(self, xml_text):
        """Formatea el XML manteniendo estructura"""
        try:
            dom = minidom.parseString(xml_text)
            return [line.strip() for line in dom.toprettyxml(indent='  ').split("\n") if line.strip()]
        except Exception as e:
            print(f"Error al formatear XML: {str(e)}")
            return []
        
    def convertir_lineas_a_pdf(self, lineas, ruta_pdf, nombre_xml=None, is_xml_converted=False):
        """Convierte una lista de líneas a PDF manteniendo texto vectorial"""
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_margins(left=self.margen, top=self.margen, right=self.margen)

            # Título
            nombre_mostrar = nombre_xml if nombre_xml else "Archivo XML"
            pdf.set_font(self.fuente_titulo, "B", self.tam_fuente_titulo)
            titulo = f"Archivo: {nombre_mostrar}"
            if pdf.get_string_width(titulo) > self.max_titulo_ancho:
                palabras = titulo.split(' ')
                linea_actual = ""
                lineas_titulo = []
                for palabra in palabras:
                    if pdf.get_string_width(linea_actual + palabra) <= self.max_titulo_ancho:
                        linea_actual += palabra + " "
                    else:
                        lineas_titulo.append(linea_actual)
                        linea_actual = palabra + " "
                if linea_actual:
                    lineas_titulo.append(linea_actual)
                for linea in lineas_titulo:
                    pdf.cell(0, 5, txt=linea.strip(), ln=True, align="C")
            else:
                pdf.cell(0, 5, txt=titulo, ln=True, align="C")

            pdf.ln(3)

            # Contenido
            pdf.set_font("Courier", size=self.tam_fuente_cuerpo)
            for linea in lineas:
                linea = linea.strip()
                if linea:
                    pdf.multi_cell(
                        w=self.ancho_util,
                        h=self.espaciado_lineas,
                        txt=linea,
                        border=0,
                        align="L"
                    )
                    pdf.ln(1)
            
            if is_xml_converted:
                pdf.set_creator("XMLtoPDF Converter (Vector)")
            else:
                pdf.set_creator("XMLtoPDF Converter")

            pdf.set_creator("XMLtoPDF Converter")
            pdf.set_compression(True)
            pdf.output(ruta_pdf)
            return True
        except Exception as e:
            print(f"Error al generar PDF: {str(e)}")
            return False



    def convertir_txt_a_pdf(self, ruta_txt, ruta_pdf, nombre_xml=None):
        """Convierte TXT a PDF manteniendo texto vectorial"""
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_margins(left=self.margen, top=self.margen, right=self.margen)
            
            # Título ajustado
            nombre_mostrar = nombre_xml if nombre_xml else os.path.splitext(os.path.basename(ruta_txt))[0]
            pdf.set_font("Courier", size=self.tam_fuente_cuerpo)
            
            # Dividir título si es muy largo
            titulo = f"Archivo: {nombre_mostrar}"
            if pdf.get_string_width(titulo) > self.max_titulo_ancho:
                palabras = titulo.split(' ')
                lineas = []
                linea_actual = ""
                
                for palabra in palabras:
                    if pdf.get_string_width(linea_actual + palabra) <= self.max_titulo_ancho:
                        linea_actual += palabra + " "
                    else:
                        lineas.append(linea_actual)
                        linea_actual = palabra + " "
                
                if linea_actual:
                    lineas.append(linea_actual)
                
                for linea in lineas:
                    pdf.cell(0, 5, txt=linea.strip(), ln=True, align="C")
            else:
                pdf.cell(0, 5, txt=titulo, ln=True, align="C")
            
            pdf.ln(3)

            # Contenido con formato compacto
            pdf.set_font("Courier", size=self.tam_fuente_cuerpo)
            
            with open(ruta_txt, "r", encoding="utf-8") as txt_file:
                for linea in txt_file:
                    linea = linea.strip()
                    if linea:
                        pdf.multi_cell(
                            w=self.ancho_util,
                            h=self.espaciado_lineas,
                            txt=linea,
                            border=0,
                            align="L"
                        )
                        pdf.ln(1)

            # Guardar directamente sin conversión a imagen
            pdf.set_creator("XMLtoPDF Converter")
            pdf.set_compression(True)
            pdf.output(ruta_pdf)
            
            return True
        except Exception as e:
            print(f"Error al convertir TXT a PDF: {str(e)}")
            return False

    def convert(self, xml_path, output_pdf, is_xml_converted=False):  # <- Parámetro añadido
        """Método principal de conversión"""
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Formatear XML
            formatted_lines = self.format_xml_text(xml_content)

            # Convertir directamente a PDF sin crear archivo TXT
            nombre_xml = os.path.splitext(os.path.basename(xml_path))[0]
            if not self.convertir_lineas_a_pdf(formatted_lines, output_pdf, nombre_xml, is_xml_converted):  # <- Modificación
                return False

            return True
        except Exception as e:
            print(f"Error en convert: {str(e)}")
            return False
