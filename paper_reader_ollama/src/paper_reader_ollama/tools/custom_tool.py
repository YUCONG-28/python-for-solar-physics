import os

import fitz  # PyMuPDF
from crewai.tools import BaseTool


class LocalPDFReaderTool(BaseTool):
    name: str = "本地论文PDF阅读器(带图)"
    description: str = (
        "读取PDF全文，提取文本并自动保存图片。返回包含[图表: 编号]标记的文本。"
    )

    def _run(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在。"

        # 创建图片保存目录
        doc_name = os.path.basename(file_path).replace(".pdf", "")
        img_dir = os.path.join("output_images", doc_name)
        os.makedirs(img_dir, exist_ok=True)

        try:
            doc = fitz.open(file_path)
            full_text = ""

            for page_index in range(len(doc)):
                page = doc[page_index]
                text = page.get_text()

                # 提取该页图片
                image_list = page.get_images(full=True)
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    ext = base_image["ext"]
                    img_filename = f"page{page_index+1}_img{img_index+1}.{ext}"
                    img_path_abs = os.path.abspath(
                        os.path.join(img_dir, img_filename)
                    ).replace("\\", "/")

                    with open(img_path_abs, "wb") as f:
                        f.write(image_bytes)

                    # 在文本中插入图片标记，帮助智能体理解图文关系
                    text += f"\n\n[本地图片路径: {img_path_abs}]\n\n"

                full_text += text + "\n"

            return full_text
        except Exception as e:
            return f"深度读取PDF时出错: {str(e)}"
