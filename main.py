# main.py
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit

class CardNotesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CardNotes')
        self.setGeometry(100, 100, 800, 600)  # x, y, width, height

        # 创建一个简单的文本编辑器区域
        self.editor = QTextEdit()
        self.setCentralWidget(self.editor)

def main():
    app = QApplication(sys.argv)
    main_window = CardNotesApp()
    main_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
