import os
import io
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance

def optimize_pdf_size(input_path, output_dir=None, target_dpi=150, grayscale=False, is_xml_converted=False, **kwargs):
    """
    Versión definitiva para resolver problemas de PDFs en blanco
    """
    try:
        # Validación básica
        input_path = kwargs.get('input_pdf', input_path)
    
        if not input_path or not os.path.exists(input_path):
            print(f"Archivo no encontrado: {input_path}")
            return None

        # No procesar XML convertidos
        if is_xml_converted:
            return input_path

        # Configurar rutas de salida
        output_dir = output_dir or os.path.dirname(input_path)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"processed_{os.path.basename(input_path)}")

        # Abrir documentos
        src_doc = fitz.open(input_path)
        dst_doc = fitz.open()

        # Procesar cada página
        for page in src_doc:
            # Crear nueva página con el mismo tamaño
            new_page = dst_doc.new_page(width=page.rect.width, height=page.rect.height)

            if grayscale:
                # Método seguro para escala de grises
                pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csGRAY)
                new_page.insert_image(new_page.rect, pixmap=pix)
                
                # Conservar texto vectorial por separado
                text_blocks = page.get_text("blocks")
                if text_blocks:
                    tw = fitz.TextWriter(new_page.rect)
                    for block in text_blocks:
                        if block[6]:  # Si tiene texto
                            x0, y0, _, _, text, *_ = block
                            tw.append((x0, y0), text)
                    tw.write_text(new_page, color=0)  # Texto en negro
            else:
                # Copiar página original directamente
                new_page.show_pdf_page(new_page.rect, src_doc, page.number)

        # Guardar con optimizaciones
        save_options = {
            "garbage": 4,
            "deflate": True,
            "clean": True,
            "deflate_images": True,
            "deflate_fonts": True
        }
        dst_doc.save(output_path, **save_options)
        return output_path

    except Exception as e:
        print(f"Error crítico al procesar {input_path}: {str(e)}")
        return None
    finally:
        if 'src_doc' in locals() and not src_doc.is_closed:
            src_doc.close()
        if 'dst_doc' in locals() and not dst_doc.is_closed:
            dst_doc.close()