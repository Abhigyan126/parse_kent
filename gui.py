import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QCompleter, QListWidget, QHBoxLayout
)
from PyQt6.QtCore import Qt
from tabulate import tabulate
from collections import defaultdict

class KentRepertoryApp(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.setWindowTitle("Kent Repertory Browser")
        self.setGeometry(100, 100, 1000, 700)
        self.db_path = db_path
        self.symptom_suggestions = self.fetch_all_symptoms()
        self.selected_symptoms = []
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout()

        self.search_label = QLabel("Enter Rubric:")
        layout.addWidget(self.search_label)

        self.search_input = QLineEdit()
        completer = QCompleter(self.symptom_suggestions)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_input.setCompleter(completer)
        layout.addWidget(self.search_input)

        button_layout = QHBoxLayout()

        self.add_button = QPushButton("Add Rubric")
        self.add_button.clicked.connect(self.add_symptom)
        button_layout.addWidget(self.add_button)

        self.calculate_button = QPushButton("Calculate Remedies")
        self.calculate_button.clicked.connect(self.calculate_remedies)
        button_layout.addWidget(self.calculate_button)

        self.drill_button = QPushButton("Drill Down Selected")
        self.drill_button.clicked.connect(self.drill_down_symptom)
        button_layout.addWidget(self.drill_button)

        layout.addLayout(button_layout)

        self.symptom_list = QListWidget()
        layout.addWidget(self.symptom_list)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def fetch_all_symptoms(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT name FROM subsymptoms")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def add_symptom(self):
        symptom = self.search_input.text().strip()
        if symptom and symptom not in self.selected_symptoms:
            self.selected_symptoms.append(symptom)
            self.symptom_list.addItem(symptom)
        self.search_input.clear()

    def calculate_remedies(self):
        if not self.selected_symptoms:
            self.result_area.setText("No rubrics selected.")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        remedy_scores = defaultdict(int)
        all_rows = []

        for symptom in self.selected_symptoms:
            # Only fetch the first exact match for the symptom name
            cursor.execute("""
                SELECT 
                s.id AS subsymptom_id,
                s.name AS symptom,
                s.depth,
                s.name AS hierarchy_path,
                sec.name AS section,
                r.name AS remedy,
                r.grade AS remedy_grade
                FROM subsymptoms s
                LEFT JOIN remedies r ON r.subsymptom_id = s.id
                LEFT JOIN sections sec ON sec.id = s.section_id
                WHERE s.name = ?
                GROUP BY s.id, r.name
            """, (symptom,))
            rows = cursor.fetchall()
            all_rows.extend(rows)
            for row in rows:
                remedy = row[5]
                grade = row[6] if row[6] else 0
                if remedy:
                    remedy_scores[remedy] += grade

        sorted_remedies = sorted(remedy_scores.items(), key=lambda x: x[1], reverse=True)

        result_text = f"=== Remedies for Selected Rubrics: {', '.join(self.selected_symptoms)} ===\n\n"
        if all_rows:
            headers = ["subsymptom_id", "symptom", "depth", "hierarchy_path", "section", "remedy", "remedy_grade"]
            table_str = tabulate(all_rows, headers=headers, tablefmt="grid")
            result_text += table_str
            result_text += "\n\n=== Suggested Remedies (Ranked by Total Grade) ===\n"
            for i, (remedy, total_grade) in enumerate(sorted_remedies[:10], 1):
                result_text += f"{i}. {remedy} (Score: {total_grade})\n"
        else:
            result_text += "No remedies found for selected rubrics."

        self.result_area.setText(result_text)
        conn.close()

    def drill_down_symptom(self):
        selected_items = self.symptom_list.selectedItems()
        if not selected_items:
            self.result_area.setText("Please select a rubric to drill down.")
            return

        symptom_name = selected_items[0].text()

        query = self.get_hierarchy_query()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, (symptom_name,))
        rows = cursor.fetchall()
        conn.close()

        sub_symptoms = sorted(set(row[1] for row in rows if row[1] != symptom_name))

        if sub_symptoms:
            result_text = f"=== Drill Down for '{symptom_name}' ===\n\n"
            for sub in sub_symptoms:
                result_text += f"→ {sub}\n"
        else:
            result_text = f"No modifiers or child symptoms found for '{symptom_name}'."

        self.result_area.setText(result_text)

    def get_hierarchy_query(self):
        return """
        WITH RECURSIVE hierarchy AS (
            SELECT 
                s.id AS subsymptom_id,
                s.name AS subsymptom_name,
                s.parent_subsymptom_id,
                s.section_id,
                s.depth,
                s.name AS full_path
            FROM subsymptoms s
            WHERE s.name = ?

            UNION ALL

            SELECT 
                c.id AS subsymptom_id,
                c.name AS subsymptom_name,
                c.parent_subsymptom_id,
                c.section_id,
                c.depth,
                h.full_path || ' → ' || c.name
            FROM subsymptoms c
            JOIN hierarchy h ON c.parent_subsymptom_id = h.subsymptom_id
        )

        SELECT 
            h.subsymptom_id,
            h.subsymptom_name AS symptom,
            h.depth,
            h.full_path AS hierarchy_path,
            sections.name AS section,
            remedies.name AS remedy,
            remedies.grade AS remedy_grade
        FROM hierarchy h
        LEFT JOIN sections ON h.section_id = sections.id
        LEFT JOIN remedies ON remedies.subsymptom_id = h.subsymptom_id
        ORDER BY h.depth, h.full_path
        """

if __name__ == '__main__':
    app = QApplication(sys.argv)
    db_path = "kent_repertory.db"
    main_window = KentRepertoryApp(db_path)
    main_window.show()
    sys.exit(app.exec())
