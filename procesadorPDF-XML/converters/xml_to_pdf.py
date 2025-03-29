import os
import xml.dom.minidom
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import mm
from reportlab.lib.colors import blue, green, purple, black

class XMLtoPDFConverter:
    def __init__(self):
        self.PAGE_WIDTH, self.PAGE_HEIGHT = 215.9 * mm, 279.4 * mm
        self.MARGIN_LEFT, self.MARGIN_TOP = 15 * mm, 15 * mm
        self.FONT_SIZE, self.LINE_HEIGHT, self.TAB_SIZE = 6, 8, 6
        self.MAX_LINE_LENGTH = 150
        self.TITLE_FONT_SIZE = 14

    def format_xml_text(self, xml_text):
        try:
            dom = xml.dom.minidom.parseString(xml_text)
            return [line for line in dom.toprettyxml(indent="  ").split("\n") if line.strip()]
        except Exception as e:
            print(f"Error al formatear XML: {str(e)}")
            return []

    def draw_colored_text(self, c, text, x, y):
        current_x = x
        for word in text.split():
            word = word.strip()
            if word.startswith("<") and word.endswith(">"):
                c.setFillColor(blue)
            elif "=" in word:
                c.setFillColor(green)
            elif word.startswith('"') and word.endswith('"'):
                c.setFillColor(green)
            else:
                c.setFillColor(purple)
            c.drawString(current_x, y, word)
            current_x += c.stringWidth(word, "Courier", self.FONT_SIZE) + 3
        c.setFillColor(black)

    def convert(self, xml_path, output_pdf):
        if not os.path.exists(xml_path):
            print(f"Error: Archivo XML no encontrado en {xml_path}")
            return False
        
        with open(xml_path, "r", encoding="utf-8") as file:
            formatted_lines = self.format_xml_text(file.read())

        if not formatted_lines:
            print("Error: No se pudo formatear el XML")
            return False

        c = canvas.Canvas(output_pdf, 
                     pagesize=(self.PAGE_WIDTH, self.PAGE_HEIGHT),
                     pageCompression=1)
        
        # 1. Agregar título centrado en negritas
        file_name = os.path.splitext(os.path.basename(xml_path))[0]
        c.setFont("Helvetica-Bold", self.TITLE_FONT_SIZE)
        title_width = c.stringWidth(file_name, "Helvetica-Bold", self.TITLE_FONT_SIZE)
        title_x = (self.PAGE_WIDTH - title_width) / 2
        title_y = self.PAGE_HEIGHT - self.MARGIN_TOP - 10
        
        c.drawString(title_x, title_y, file_name)
        
        # 2. Dibujar línea separadora
        c.line(self.MARGIN_LEFT, title_y - 5, 
              self.PAGE_WIDTH - self.MARGIN_LEFT, title_y - 5)
        
        # 3. Configurar para el contenido XML
        c.setFont("Courier", self.FONT_SIZE)
        x, y = self.MARGIN_LEFT, title_y - 15

        for line in formatted_lines:
            indent = line.count("  ") * self.TAB_SIZE
            adjusted_x = x + indent
            while len(line) > self.MAX_LINE_LENGTH:
                self.draw_colored_text(c, line[:self.MAX_LINE_LENGTH], x, y)
                line = line[self.MAX_LINE_LENGTH:]
                y -= self.LINE_HEIGHT
                if y < self.MARGIN_LEFT:
                    c.showPage()
                    c.setFont("Courier", self.FONT_SIZE)
                    y = self.PAGE_HEIGHT - self.MARGIN_LEFT
            if y < self.MARGIN_TOP:
                c.showPage()
                c.setFont("Courier", self.FONT_SIZE)
                y = self.PAGE_HEIGHT - self.MARGIN_TOP
            self.draw_colored_text(c, line.strip(), adjusted_x, y)
            y -= self.LINE_HEIGHT

        c.save()
        print(f"PDF generado en: {os.path.abspath(output_pdf)}")
        return True