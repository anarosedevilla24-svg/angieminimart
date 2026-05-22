import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtGui import QFont, QPixmap, QPainter, QPainterPath
from PyQt5.QtCore import Qt

from backend import DB


PHOTO_FILENAME = "angie.png"


class RoundedRightImage(QLabel):
    def __init__(self, image_path, radius=15):
        super().__init__()
        self.image_path = image_path
        self.radius = radius
        self.pixmap = QPixmap(image_path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        w = self.width()
        h = self.height()
        r = self.radius

        path.moveTo(0, 0)
        path.lineTo(w - r, 0)
        path.quadTo(w, 0, w, r)
        path.lineTo(w, h - r)
        path.quadTo(w, h, w - r, h)
        path.lineTo(0, h)
        path.lineTo(0, 0)

        painter.setClipPath(path)

        if not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)


class SignupUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Angie's Mini Mart Sign up")
        self.setFixedSize(1366, 768)
        self.setStyleSheet("background-color: #f49aa3;")

        self.init_ui()

    def init_ui(self):
        main_card = QFrame(self)
        main_card.setGeometry(157, 77, 1051, 614)
        main_card.setStyleSheet("""
            QFrame {
                background-color: #fde5df;
                border-radius: 15px;
            }
        """)

        main_layout = QHBoxLayout(main_card)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left signup panel
        left_panel = QFrame()
        left_panel.setFixedSize(518, 614)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #fde5df;
                border-top-left-radius: 15px;
                border-bottom-left-radius: 15px;
            }
        """)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(55, 10, 65, 25)
        left_layout.setSpacing(12)

        title = QLabel("Angie's Mini Mart")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe Script", 25))
        title.setStyleSheet("""
            QLabel {
                color: #ff9aa5;
                background: transparent;
            }
        """)
        left_layout.addWidget(title)

        signup_title = QLabel("Sign up")
        signup_title.setAlignment(Qt.AlignCenter)
        signup_title.setFont(QFont("Poppins", 30, QFont.Bold))
        signup_title.setStyleSheet("""
            QLabel {
                color: #f59aa5;
                background: transparent;
            }
        """)
        left_layout.addWidget(signup_title)

        username_label = QLabel("Username")
        username_label.setFont(QFont("Poppins", 11, QFont.Bold))
        username_label.setStyleSheet("color: #9b827e; background: transparent;")
        left_layout.addWidget(username_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(39)
        self.username_input.setStyleSheet(self.input_style())
        left_layout.addWidget(self.username_input)

        email_label = QLabel("Email")
        email_label.setFont(QFont("Poppins", 11, QFont.Bold))
        email_label.setStyleSheet("color: #9b827e; background: transparent;")
        left_layout.addWidget(email_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter your email")
        self.email_input.setFixedHeight(39)
        self.email_input.setStyleSheet(self.input_style())
        left_layout.addWidget(self.email_input)

        password_label = QLabel("Password")
        password_label.setFont(QFont("Poppins", 11, QFont.Bold))
        password_label.setStyleSheet("color: #9b827e; background: transparent;")
        left_layout.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(39)
        self.password_input.setStyleSheet(self.input_style())
        left_layout.addWidget(self.password_input)

        left_layout.addSpacing(8)

        signup_button = QPushButton("Sign up")
        self.signup_button = signup_button
        signup_button.setFixedSize(222, 43)
        signup_button.setCursor(Qt.PointingHandCursor)
        signup_button.setFont(QFont("Poppins", 11, QFont.Bold))
        signup_button.setStyleSheet("""
            QPushButton {
                background-color: #f59aa5;
                border: none;
                border-radius: 20px;
                color: black;
            }

            QPushButton:hover {
                background-color: #f57f8c;
            }
        """)
        left_layout.addWidget(signup_button, alignment=Qt.AlignCenter)

        or_label = QLabel("or")
        or_label.setAlignment(Qt.AlignCenter)
        or_label.setFont(QFont("Poppins", 11, QFont.Bold))
        or_label.setStyleSheet("color: #9b827e; background: transparent;")
        left_layout.addWidget(or_label)

        login_button = QPushButton("Login")
        self.login_button = login_button
        login_button.setFixedSize(222, 43)
        login_button.setCursor(Qt.PointingHandCursor)
        login_button.setFont(QFont("Poppins", 11, QFont.Bold))
        login_button.setStyleSheet("""
            QPushButton {
                background-color: #ff7f7f;
                border: none;
                border-radius: 20px;
                color: black;
            }

            QPushButton:hover {
                background-color: #ff6b6b;
            }
        """)
        left_layout.addWidget(login_button, alignment=Qt.AlignCenter)

        left_layout.addStretch()

        # Right image panel
        image_path = os.path.join(os.path.dirname(__file__), "assets", PHOTO_FILENAME)

        photo_area = RoundedRightImage(image_path)
        photo_area.setFixedSize(533, 614)
        photo_area.setStyleSheet("""
            QLabel {
                background-color: white;
                border-top-right-radius: 15px;
                border-bottom-right-radius: 15px;
            }
        """)

        self.signup_button.clicked.connect(self.handle_signup)
        self.password_input.returnPressed.connect(self.handle_signup)
        self.login_button.clicked.connect(self.open_login)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(photo_area)

    def handle_signup(self):
        ok, message = DB.create_user(
            self.username_input.text().strip(),
            self.email_input.text().strip(),
            self.password_input.text()
        )
        if not ok:
            QMessageBox.warning(self, "Sign up", message)
            return
        QMessageBox.information(self, "Sign up", message + " You can now log in.")
        self.open_login()

    def open_login(self):
        from login import LoginUI
        self.login_window = LoginUI()
        self.login_window.show()
        self.close()

    def input_style(self):
        return """
            QLineEdit {
                background-color: #f8bfc0;
                border: none;
                border-radius: 10px;
                padding-left: 15px;
                font-size: 16px;
                color: #6f5f5f;
            }

            QLineEdit::placeholder {
                color: #c89c9c;
            }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SignupUI()
    window.show()
    sys.exit(app.exec_())