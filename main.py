import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QTextEdit, QSplitter, QListWidgetItem,
    QPushButton, QInputDialog, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QFileInfo

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('CardNotes')
        self.setGeometry(100, 100, 900, 700)
        self.notes_file = 'notes.json'
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.js_to_run_on_load = ""
        
        # 在UI构建前，一次性加载所有资源到内存
        self.load_katex_resources()
        self.load_notes()
        self.init_ui()

        # 连接预览区域的加载完成信号
        self.preview_area.page().loadFinished.connect(self.on_preview_load_finished)

        if self.notes_list.count() > 0:
            self.notes_list.setCurrentRow(0)
        else:
            self.update_editor_placeholder()

    def on_preview_load_finished(self, ok):
        """当预览的HTML页面加载完成后执行JS。"""
        if ok and self.js_to_run_on_load:
            self.preview_area.page().runJavaScript(self.js_to_run_on_load)
            self.js_to_run_on_load = "" # 执行后清空

    def load_katex_resources(self):
        """在程序启动时，将KaTeX的CSS和JS文件内容读入内存。"""
        self.katex_css = ""
        self.katex_js = ""
        self.auto_render_js = ""
        try:
            # 使用脚本的绝对路径来定位资源，更稳定
            katex_base_path = os.path.join(self.script_dir, 'katex')
            with open(os.path.join(katex_base_path, 'katex.min.css'), 'r', encoding='utf-8') as f:
                self.katex_css = f.read()
            with open(os.path.join(katex_base_path, 'katex.min.js'), 'r', encoding='utf-8') as f:
                self.katex_js = f.read()
            with open(os.path.join(katex_base_path, 'contrib', 'auto-render.min.js'), 'r', encoding='utf-8') as f:
                self.auto_render_js = f.read()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Fatal Error", f"Could not load KaTeX resource file: {e}\nPlease ensure the 'katex' folder is complete and in the same directory as the script.")
        except Exception as e:
            QMessageBox.critical(self, "Fatal Error", f"An unexpected error occurred while loading KaTeX resources: {e}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)

        self.notes_list = QListWidget()
        self.notes_list.addItems(self.notes_data.keys())
        self.notes_list.currentItemChanged.connect(self.display_note_content)
        left_layout.addWidget(self.notes_list)

        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        new_note_btn = QPushButton("New Note")
        new_note_btn.clicked.connect(self.new_note)
        delete_note_btn = QPushButton("Delete Note")
        delete_note_btn.clicked.connect(self.delete_note)
        button_layout.addWidget(new_note_btn)
        button_layout.addWidget(delete_note_btn)
        left_layout.addWidget(button_widget)

        # --- Right Panel (Editor and Preview) ---
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.note_editor = QTextEdit()
        self.note_editor.textChanged.connect(self.on_text_changed)

        self.preview_area = QWebEngineView()
        self.preview_area.setHtml("<h1>Select or create a note</h1>")

        right_splitter.addWidget(self.note_editor)
        right_splitter.addWidget(self.preview_area)
        right_splitter.setSizes([350, 350])

        # --- Main Splitter ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([250, 650])

        main_layout.addWidget(main_splitter)

    def get_html_template(self, content):
        # 新模板：直接内联预先加载到内存的CSS和JS内容
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self.katex_css}</style>
            <script>{self.katex_js}</script>
            <script>{self.auto_render_js}</script>
        </head>
        <body>
            {content.replace('\\n', '<br>')}
        </body>
        </html>
        """
        return html

    def on_text_changed(self):
        self.save_current_note_content()
        self.update_preview()

    def update_preview(self):
        current_item = self.notes_list.currentItem()
        if current_item:
            text = self.note_editor.toPlainText()
            html_content = self.get_html_template(text)
            
            js_code = """
            renderMathInElement(document.body, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false}
                ]
            });
            """
            # 将JS代码存储起来，等待页面加载完成后再执行
            self.js_to_run_on_load = js_code
            # 设置HTML内容，并提供一个正确的本地文件系统基础URL
            # 这对于KaTeX加载字体文件至关重要
            base_url = QUrl.fromLocalFile(os.path.join(self.script_dir, 'katex') + os.path.sep)
            self.preview_area.setHtml(html_content, baseUrl=base_url)

    def update_editor_placeholder(self):
        if self.notes_list.count() == 0:
            self.note_editor.clear()
            self.note_editor.setPlaceholderText("Create your first note!")
        else:
             self.note_editor.setPlaceholderText("Select a note on the left, or create a new one.")

    def load_notes(self):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    self.notes_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.notes_data = self.get_default_notes()
        else:
            self.notes_data = self.get_default_notes()
        self.save_notes()

    def get_default_notes(self):
        return {
            "入门指南": "欢迎使用 CardNotes！\n\n- 在左侧选择笔记。\n- 尝试输入LaTeX公式，例如：$E=mc^2$ 或者 $$\\sum_{i=1}^n i = \\frac{n(n+1)}{2}$$",
            "Python学习笔记": "# Python 字典\n\ndict = {'key': 'value'}",
            "项目构想": "- [ ] 支持 Markdown\n- [ ] 支持 LaTeX\n- [ ] 标签系统"
        }

    def save_notes(self):
        try:
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                json.dump(self.notes_data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Could not save notes: {e}")

    def display_note_content(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        self.note_editor.blockSignals(True)
        if current_item:
            title = current_item.text()
            self.note_editor.setText(self.notes_data.get(title, ""))
            self.update_preview()
        else:
            self.note_editor.clear()
            self.update_editor_placeholder()
        self.note_editor.blockSignals(False)

    def save_current_note_content(self):
        current_item = self.notes_list.currentItem()
        if current_item:
            title = current_item.text()
            content = self.note_editor.toPlainText()
            if title in self.notes_data and self.notes_data[title] != content:
                self.notes_data[title] = content
                self.save_notes()

    def new_note(self):
        title, ok = QInputDialog.getText(self, "New Note", "Enter note title:")
        if ok and title and title.strip():
            if title in self.notes_data:
                QMessageBox.warning(self, "Warning", "A note with this title already exists.")
                return
            
            self.notes_data[title] = ""
            self.notes_list.addItem(title)
            self.notes_list.setCurrentRow(self.notes_list.count() - 1)
            self.note_editor.setFocus()
            self.save_notes()

    def delete_note(self):
        current_item = self.notes_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Info", "Please select a note to delete.")
            return

        title = current_item.text()
        reply = QMessageBox.question(self, 'Delete Note', 
                                     f"Are you sure you want to delete '{title}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            row = self.notes_list.row(current_item)
            self.notes_list.takeItem(row)
            if title in self.notes_data:
                del self.notes_data[title]
            
            self.save_notes()
            
            if self.notes_list.count() == 0:
                self.update_editor_placeholder()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
