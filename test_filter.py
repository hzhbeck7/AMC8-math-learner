import os
import sys
from PIL import Image
import io

def analyze_pdf_images(pdf_path):
    """
    分析 PDF 中的所有图片，打印详细信息用于调试
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("请先安装 PyMuPDF: pip install PyMuPDF")
        return

    doc = fitz.open(pdf_path)
    print(f"PDF 文件: {pdf_path}")
    print(f"总页数: {len(doc)}\n")

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)
        print(f"第 {page_num + 1} 页: {len(image_list)} 张图片")

        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            size_kb = len(image_bytes) / 1024
            width = height = 0

            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    width, height = img.size
            except Exception:
                pass

            print(f"  图片 {img_index + 1}: {size_kb:.2f} KB, {width}x{height} 像素")
            if size_kb < 10 and width < 200 and height < 200:
                print(f"    -> 可能是 logo，会被筛选掉")
        print()

    doc.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_filter.py <pdf文件路径>")
        print("示例: python test_filter.py \"P:\\documents\\AMC8\\AMC8 L02.pdf\"")
    else:
        pdf_path = sys.argv[1]
        if os.path.exists(pdf_path):
            analyze_pdf_images(pdf_path)
        else:
            print(f"文件不存在: {pdf_path}")
