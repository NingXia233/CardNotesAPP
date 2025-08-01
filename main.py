import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QTextEdit, QSplitter, QListWidgetItem,
    QPushButton, QInputDialog, QMessageBox, QLabel, QLineEdit
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QFileInfo
from tag_map_view import TagMapWindow

# Helper function to determine the correct path for resources
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('CardNotes')
        self.setGeometry(100, 100, 900, 700)

        # Determine the base path for read/write data files
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle, the data files should be
            # in the same directory as the executable
            self.data_path = os.path.dirname(sys.executable)
        else:
            # In a normal environment, the data files are in the script's directory
            self.data_path = os.path.dirname(os.path.abspath(__file__))

        self.notes_file = os.path.join(self.data_path, 'notes.json')
        self.tag_map_file = os.path.join(self.data_path, 'tag_map_data.json')
        
        self.js_to_run_on_load = ""
        self.tag_map_win = None
        
        # Load resources before building the UI
        self.load_katex_resources()
        self.load_notes()
        self.init_ui()

        # Connect the preview area's load finished signal
        self.preview_area.page().loadFinished.connect(self.on_preview_load_finished)

        self.filter_notes() # Apply filter on initial load (shows all)

        if self.notes_list.count() > 0:
            self.notes_list.setCurrentRow(0)
        else:
            self.update_editor_placeholder()

    def on_preview_load_finished(self, ok):
        """Execute JS after the preview HTML page has finished loading."""
        if ok and self.js_to_run_on_load:
            self.preview_area.page().runJavaScript(self.js_to_run_on_load)
            self.js_to_run_on_load = "" # Clear after execution

    def load_katex_resources(self):
        """Load KaTeX CSS and JS file contents into memory on startup."""
        self.katex_css = ""
        self.katex_js = ""
        self.auto_render_js = ""
        try:
            # Use the resource_path helper to find KaTeX files
            katex_base_path = resource_path('katex')
            with open(os.path.join(katex_base_path, 'katex.min.css'), 'r', encoding='utf-8') as f:
                self.katex_css = f.read()
            with open(os.path.join(katex_base_path, 'katex.min.js'), 'r', encoding='utf-8') as f:
                self.katex_js = f.read()
            with open(os.path.join(katex_base_path, 'contrib', 'auto-render.min.js'), 'r', encoding='utf-8') as f:
                self.auto_render_js = f.read()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Fatal Error", f"Could not load KaTeX resource file: {e}\nPlease ensure the 'katex' folder is complete and included in the build.")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "Fatal Error", f"An unexpected error occurred while loading KaTeX resources: {e}")
            sys.exit(1)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)

        # --- Search Bar ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search notes by title or tag...")
        self.search_bar.textChanged.connect(self.filter_notes)
        left_layout.addWidget(self.search_bar)

        # --- Notes List ---
        self.notes_list = QListWidget()
        self.notes_list.currentItemChanged.connect(self.display_note_content)
        left_layout.addWidget(self.notes_list)

        # --- Tag Display ---
        self.tag_label = QLabel("Tags: No tags")
        self.tag_label.setWordWrap(True)
        left_layout.addWidget(self.tag_label)

        # --- Buttons ---
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        new_note_btn = QPushButton("New")
        new_note_btn.clicked.connect(self.new_note)
        rename_note_btn = QPushButton("Rename")
        rename_note_btn.clicked.connect(self.rename_note)
        delete_note_btn = QPushButton("Delete")
        delete_note_btn.clicked.connect(self.delete_note)
        tag_note_btn = QPushButton("Tag")
        tag_note_btn.clicked.connect(self.manage_tags)
        tag_map_btn = QPushButton("Tag Map")
        tag_map_btn.clicked.connect(self.open_tag_map)
        button_layout.addWidget(new_note_btn)
        button_layout.addWidget(rename_note_btn)
        button_layout.addWidget(delete_note_btn)
        button_layout.addWidget(tag_note_btn)
        button_layout.addWidget(tag_map_btn)
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
        # New template: directly inline pre-loaded CSS and JS content
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
            # Store the JS code to be executed after the page loads
            self.js_to_run_on_load = js_code
            # Set the HTML content and provide a correct local file system base URL
            # This is crucial for KaTeX to load its font files
            base_url = QUrl.fromLocalFile(resource_path('katex') + os.path.sep)
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
                # --- Data Structure Migration ---
                # Check if migration is needed
                if self.notes_data and isinstance(next(iter(self.notes_data.values())), str):
                    self.migrate_notes_data()
            except (json.JSONDecodeError, IOError):
                self.notes_data = self.get_default_notes()
        else:
            self.notes_data = self.get_default_notes()
        self.save_notes()

    def migrate_notes_data(self):
        """Converts old data format (str) to new format (dict with content/tags)."""
        migrated_data = {}
        for title, content in self.notes_data.items():
            migrated_data[title] = {"content": content, "tags": []}
        self.notes_data = migrated_data
        self.save_notes()
        QMessageBox.information(self, "Data Migration", "Your notes have been updated to support tags.")

    def get_default_notes(self):
        return {
            "入门指南": {
                "content": "欢迎使用 CardNotes！\n\n- 在左侧选择笔记。\n- 尝试输入LaTeX公式，例如：$E=mc^2$ 或者 $$\\sum_{i=1}^n i = \\frac{n(n+1)}{2}$$",
                "tags": ["welcome", "guide"]
            },
            "Python学习笔记": {
                "content": "# Python 字典\n\ndict = {'key': 'value'}",
                "tags": ["python", "code"]
            },
            "项目构想": {
                "content": "- [ ] 支持 Markdown\n- [ ] 支持 LaTeX\n- [ ] 标签系统",
                "tags": ["todo", "feature"]
            }
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
            note = self.notes_data.get(title, {})
            self.note_editor.setText(note.get("content", ""))
            
            # Update tag display
            tags = note.get("tags", [])
            if tags:
                self.tag_label.setText(f"Tags: {', '.join(tags)}")
            else:
                self.tag_label.setText("Tags: No tags")

            self.update_preview()
        else:
            self.note_editor.clear()
            self.tag_label.setText("Tags: No tags")
            self.preview_area.setHtml("<h1>Select or create a note</h1>") # Clear preview
            self.update_editor_placeholder()
        self.note_editor.blockSignals(False)

    def save_current_note_content(self):
        current_item = self.notes_list.currentItem()
        if current_item:
            title = current_item.text()
            content = self.note_editor.toPlainText()
            if title in self.notes_data and self.notes_data[title].get("content") != content:
                self.notes_data[title]["content"] = content
                self.save_notes()

    def new_note(self):
        title, ok = QInputDialog.getText(self, "New Note", "Enter note title:")
        if ok and title and title.strip():
            if title in self.notes_data:
                QMessageBox.warning(self, "Warning", "A note with this title already exists.")
                return
            
            self.notes_data[title] = {"content": "", "tags": []}
            self.save_notes()
            self.filter_notes() # Use filter_notes to add and display
            
            # Find and select the new note
            for i in range(self.notes_list.count()):
                if self.notes_list.item(i).text() == title:
                    self.notes_list.setCurrentRow(i)
                    break
            
            self.note_editor.setFocus()

    def rename_note(self):
        current_item = self.notes_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Info", "Please select a note to rename.")
            return

        old_title = current_item.text()
        new_title, ok = QInputDialog.getText(self, "Rename Note", "Enter new title:", text=old_title)

        if ok and new_title and new_title.strip():
            new_title = new_title.strip()
            if new_title == old_title:
                return # No change
            
            if new_title in self.notes_data:
                QMessageBox.warning(self, "Warning", "A note with this title already exists.")
                return

            # Update data and UI
            self.notes_data[new_title] = self.notes_data.pop(old_title)
            self.save_notes()
            
            # Refresh the list to show the new title
            self.filter_notes()

            # Find and re-select the renamed note
            for i in range(self.notes_list.count()):
                if self.notes_list.item(i).text() == new_title:
                    self.notes_list.setCurrentRow(i)
                    break

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
            if title in self.notes_data:
                del self.notes_data[title]
            
            self.save_notes()
            self.filter_notes() # Re-filter the list
            
            if self.notes_list.count() == 0:
                self.update_editor_placeholder()

    def manage_tags(self):
        current_item = self.notes_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Info", "Please select a note to manage its tags.")
            return

        title = current_item.text()
        note = self.notes_data.get(title)
        if not note: return

        current_tags = ", ".join(note.get("tags", []))
        new_tags_str, ok = QInputDialog.getText(self, "Manage Tags", 
                                                f"Edit tags for '{title}' (comma-separated):", 
                                                text=current_tags)

        if ok:
            # Clean user input, split, and remove whitespace
            new_tags = [tag.strip() for tag in new_tags_str.split(',') if tag.strip()]
            note["tags"] = new_tags
            self.save_notes()
            self.display_note_content(current_item, None) # Refresh tag display
            self.filter_notes() # The list needs to be updated if the search involves tags
            
            # If the tag map window is open, update it
            if self.tag_map_win and self.tag_map_win.isVisible():
                all_tags = self._get_all_tags()
                self.tag_map_win.update_tags(all_tags)

    def filter_notes(self):
        search_text = self.search_bar.text().lower()
        self.notes_list.blockSignals(True) # Avoid triggering unnecessary actions while updating the list
        self.notes_list.clear()
        
        # Get the title of the currently selected note to try to restore the selection after filtering
        current_title = self.notes_list.currentItem().text() if self.notes_list.currentItem() else None
        
        sorted_titles = sorted(self.notes_data.keys())

        for title in sorted_titles:
            data = self.notes_data[title]
            # Check if the title matches
            if search_text in title.lower():
                self.notes_list.addItem(title)
                continue 
            
            # Check if the tags match
            tags = data.get("tags", [])
            for tag in tags:
                if search_text in tag.lower():
                    self.notes_list.addItem(title)
                    break 
        
        self.notes_list.blockSignals(False)

        # Try to restore the previous selection, or select the first item by default
        if current_title and self.search_bar.text() == "":
             for i in range(self.notes_list.count()):
                if self.notes_list.item(i).text() == current_title:
                    self.notes_list.setCurrentRow(i)
                    return

        if self.notes_list.count() > 0:
            self.notes_list.setCurrentRow(0)
        else:
            # If there are no matches, clear the right panel
            self.display_note_content(None, None)

    def load_tag_map_data(self):
        """Loads the tag map layout data from a JSON file."""
        if os.path.exists(self.tag_map_file):
            try:
                with open(self.tag_map_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save_tag_map_data(self, layout_data):
        """Saves the tag map layout data to a JSON file."""
        try:
            with open(self.tag_map_file, 'w', encoding='utf-8') as f:
                json.dump(layout_data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Could not save tag map data: {e}")

    def _get_all_tags(self):
        """Helper function to get all unique tags from notes."""
        all_tags = set()
        for note in self.notes_data.values():
            for tag in note.get("tags", []):
                all_tags.add(tag)
        return list(all_tags)

    def open_tag_map(self):
        """Open or update the tag map window."""
        all_tags = self._get_all_tags()

        if self.tag_map_win and self.tag_map_win.isVisible():
            self.tag_map_win.update_tags(all_tags)
            self.tag_map_win.activateWindow()
        else:
            layout_data = self.load_tag_map_data()
            self.tag_map_win = TagMapWindow(all_tags, layout_data, self.save_tag_map_data)
            self.tag_map_win.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
