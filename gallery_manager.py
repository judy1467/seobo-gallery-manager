#!/usr/bin/env python3
"""
서보테크놀로지 갤러리 관리 프로그램
라즈베리파이 SSH 연결 → 이미지 WebP 변환 → 업로드 → gallery.html 자동 수정
"""

import sys
import os

# PySide6 Import 확인
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6가 설치되어 있지 않습니다.")
    print("설치: pip install PySide6 paramiko Pillow")
    sys.exit(1)

from main_window import GalleryManager


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("서보테크놀로지 갤러리 관리")
    app.setOrganizationName("ServoGallery")

    window = GalleryManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
