import os
import sys
from PIL import Image
import io

def analyze_image(image_path):
    """
    分析单张图片，判断是否会被识别为 logo
    """
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        size_kb = len(image_bytes) / 1024
        
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            aspect_ratio = width / height if height > 0 else 0
            
            img = img.convert('RGB')
            pixels = img.getcolors(width * height)
            color_count = len(pixels) if pixels else 0
            
            total_pixels = width * height
            dominant_color, count = pixels[0] if pixels else (None, 0)
            dominant_ratio = count / total_pixels if total_pixels > 0 else 0
        
        print(f"图片: {image_path}")
        print(f"  大小: {size_kb:.2f} KB")
        print(f"  尺寸: {width} x {height}")
        print(f"  宽高比: {aspect_ratio:.2f}")
        print(f"  颜色数量: {color_count}")
        print(f"  主色占比: {dominant_ratio:.2%}")
        
        is_logo = False
        reasons = []
        
        if size_kb < 10:
            is_logo = True
            reasons.append("文件太小 (<10KB)")
        if width < 200 and height < 200:
            is_logo = True
            reasons.append("尺寸太小 (<200x200)")
        if aspect_ratio > 2.5 or aspect_ratio < 0.4:
            is_logo = True
            reasons.append(f"宽高比极端 ({aspect_ratio:.2f})")
        if color_count < 10:
            is_logo = True
            reasons.append(f"颜色太少 (<10种)")
        if dominant_ratio > 0.7:
            is_logo = True
            reasons.append(f"主色占比太高 ({dominant_ratio:.2%})")
        
        if is_logo:
            print(f"  结果: 会被识别为 logo 并筛选掉")
            print(f"  原因: {', '.join(reasons)}")
        else:
            print(f"  结果: 不会被筛选")
        
        return is_logo
        
    except Exception as e:
        print(f"分析失败: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_logo_detection.py <图片文件路径>")
        print("示例: python test_logo_detection.py \"P:\\documents\\AMC8\\dist\\images\\L02\\page_3_1.png\"")
    else:
        image_path = sys.argv[1]
        if os.path.exists(image_path):
            analyze_image(image_path)
        else:
            print(f"文件不存在: {image_path}")