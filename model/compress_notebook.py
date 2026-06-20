import json
import sys

def compress_notebook_for_llm(ipynb_path, output_md_path, max_output_lines=20):
    with open(ipynb_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    with open(output_md_path, 'w', encoding='utf-8') as out_file:
        for i, cell in enumerate(notebook.get('cells', [])):
            # 1. 处理 Markdown 单元格
            if cell['cell_type'] == 'markdown':
                out_file.write(f"### [Markdown Cell {i+1}]\n")
                out_file.write("".join(cell.get('source', [])) + "\n\n")

            # 2. 处理代码单元格
            elif cell['cell_type'] == 'code':
                out_file.write(f"### [Code Cell {i+1}]\n")
                out_file.write("```python\n")
                out_file.write("".join(cell.get('source', [])) + "\n")
                out_file.write("```\n")

                outputs = cell.get('outputs', [])
                if outputs:
                    out_file.write("**Output:**\n```text\n")
                    for out in outputs:
                        # 2.1 处理普通的 print() 终端输出 (截断超长进度条)
                        if out.get('output_type') == 'stream':
                            text_lines = out.get('text', [])
                            if len(text_lines) > max_output_lines:
                                text_lines = text_lines[:10] + [f"\n... [{len(text_lines)-20} 行冗长输出已省略] ...\n"] + text_lines[-10:]
                            out_file.write("".join(text_lines))

                        # 2.2 处理单元格执行结果 (例如 DataFrame 展示或 Metrics 输出)
                        elif out.get('output_type') in ['execute_result', 'display_data']:
                            data = out.get('data', {})
                            
                            # 如果包含图片，打个标记丢弃
                            if 'image/png' in data or 'image/jpeg' in data:
                                out_file.write("[IMAGE/PLOT REMOVED TO SAVE CONTEXT]\n")
                            
                            # 提取纯文本结果 (如 Pandas 的文字版表格)
                            if 'text/plain' in data:
                                text_lines = data['text/plain']
                                if isinstance(text_lines, str):
                                    text_lines = text_lines.splitlines(True)
                                if len(text_lines) > max_output_lines:
                                    text_lines = text_lines[:10] + [f"\n... [{len(text_lines)-20} 行表格/数据已省略] ...\n"] + text_lines[-10:]
                                out_file.write("".join(text_lines) + "\n")

                        # 2.3 报错信息必须保留
                        elif out.get('output_type') == 'error':
                            out_file.write(f"[ERROR]: {out.get('ename')}: {out.get('evalue')}\n")

                    out_file.write("```\n\n")
    
    print(f"✅ 压缩完成！请将生成的 {output_md_path} 发给 AI。")

# 使用示例
if __name__ == "__main__":
    # 替换成你的文件路径
    input_file = "model_notebook.ipynb" 
    output_file = "compressed_notebook.md"
    compress_notebook_for_llm(input_file, output_file)