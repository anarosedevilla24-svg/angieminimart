import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout, QMessageBox
)
import os
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt

from backend import DB
from pages.dashboard import DashboardWindow


class LoginUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Angie's Mini Mart")
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

        layout = QHBoxLayout(main_card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Photo area
        photo_area = QLabel()
        photo_area.setFixedSize(535, 614)
        photo_area.setAlignment(Qt.AlignCenter)
        photo_area.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border-top-left-radius: 15px;
                border-bottom-left-radius: 15px;
            }
        """)

        image_path = os.path.join(os.path.dirname(__file__), "assets", "angie.png")

        pixmap = QPixmap(image_path)
        pixmap = pixmap.scaled(
            photo_area.width(),
            photo_area.height(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        photo_area.setPixmap(pixmap)

        layout.addWidget(photo_area)

        # Right login panel
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #fde5df;
                border-top-right-radius: 15px;
                border-bottom-right-radius: 15px;
            }
        """)

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(45, 35, 45, 35)
        right_layout.setSpacing(15)

        title = QLabel("Angie's Mini Mart")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe Script", 25))
        title.setStyleSheet("color: #ff9aa5; background: transparent;")
        right_layout.addWidget(title)

        login_title = QLabel("Login")
        login_title.setAlignment(Qt.AlignCenter)
        login_title.setFont(QFont("Poppins", 30, QFont.Bold))
        login_title.setStyleSheet("color: #f59aa5; background: transparent;")
        right_layout.addWidget(login_title)

        username_label = QLabel("Username")
        username_label.setFont(QFont("Poppins", 11, QFont.Bold))
        username_label.setStyleSheet("color: #9b827e; background: transparent;")
        right_layout.addWidget(username_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(39)
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8bfc0;
                border: none;
                border-radius: 10px;
                padding-left: 20px;
                font-size: 16px;
                color: #6f5f5f;
            }
        """)
        right_layout.addWidget(self.username_input)

        password_label = QLabel("Password")
        password_label.setFont(QFont("Poppins", 11, QFont.Bold))
        password_label.setStyleSheet("color: #9b827e; background: transparent;")
        right_layout.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(39)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8bfc0;
                border: none;
                border-radius: 10px;
                padding-left: 20px;
                font-size: 16px;
                color: #6f5f5f;
            }
        """)
        right_layout.addWidget(self.password_input)

        forgot = QLabel("<u>Forgot your password?</u>")
        forgot.setAlignment(Qt.AlignRight)
        forgot.setFont(QFont("Poppins", 11))
        forgot.setStyleSheet("color: #9b827e; background: transparent;")
        right_layout.addWidget(forgot)

        login_button = QPushButton("Login")
        self.login_button = login_button
        login_button.setFixedSize(222, 43)
        login_button.setCursor(Qt.PointingHandCursor)
        login_button.setFont(QFont("Poppins", 11, QFont.Bold))
        login_button.setStyleSheet("""
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
        right_layout.addWidget(login_button, alignment=Qt.AlignCenter)

        or_label = QLabel("or")
        or_label.setAlignment(Qt.AlignCenter)
        or_label.setFont(QFont("Poppins", 11, QFont.Bold))
        or_label.setStyleSheet("color: #9b827e; background: transparent;")
        right_layout.addWidget(or_label)

        signup_button = QPushButton("Sign up")
        self.signup_button = signup_button
        signup_button.setFixedSize(222, 43)
        signup_button.setCursor(Qt.PointingHandCursor)
        signup_button.setFont(QFont("Poppins", 11, QFont.Bold))
        signup_button.setStyleSheet("""
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
        right_layout.addWidget(signup_button, alignment=Qt.AlignCenter)

        self.login_button.clicked.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)
        self.signup_button.clicked.connect(self.open_signup)

        right_layout.addStretch()
        layout.addWidget(right_panel)

    def handle_login(self):
        user = DB.authenticate_user(self.username_input.text().strip(), self.password_input.text())
        if not user:
            QMessageBox.warning(self, "Login", "Invalid username or password.")
            return
        self.dashboard = DashboardWindow(current_user=user)
        self.dashboard.show()
        self.close()

    def open_signup(self):
        from signup import SignupUI
        self.signup_window = SignupUI()
        self.signup_window.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginUI()
    window.show()
    sys.exit(app.exec_())