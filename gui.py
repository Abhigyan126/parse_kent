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

    def get_best_symptom_entry(self, symptom_name):
        """Get the symptom entry with the highest total remedy grade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all entries for this symptom name and calculate their total remedy grades
        cursor.execute("""
            SELECT 
                s.id,
                s.name,
                s.depth,
                s.section_id,
                COALESCE(SUM(r.grade), 0) as total_grade
            FROM subsymptoms s
            LEFT JOIN remedies r ON r.subsymptom_id = s.id
            WHERE s.name = ?
            GROUP BY s.id, s.name, s.depth, s.section_id
            ORDER BY total_grade DESC, s.id ASC
            LIMIT 1
        """, (symptom_name,))
        
        result = cursor.fetchone()
        conn.close()
        return result

    def get_parent_symptoms_from_db(self, symptom_name):
        """Get parent symptoms using database hierarchy navigation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all instances of the symptom name
        cursor.execute("""
            SELECT id, parent_subsymptom_id, section_id, depth
            FROM subsymptoms 
            WHERE name = ?
        """, (symptom_name,))
        
        symptom_instances = cursor.fetchall()
        parent_symptoms = set()
        
        for symptom_id, parent_id, section_id, depth in symptom_instances:
            if parent_id:  # If this symptom has a parent
                # Get the parent symptom name
                cursor.execute("""
                    SELECT name 
                    FROM subsymptoms 
                    WHERE id = ?
                """, (parent_id,))
                
                parent_result = cursor.fetchone()
                if parent_result:
                    parent_symptoms.add(parent_result[0])
        
        conn.close()
        return list(parent_symptoms)

    def get_all_symptom_variants(self, symptom_name):
        """Get all variants/instances of symptoms with the same name using hierarchy navigation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Use the hierarchy query to get all related symptoms
        query = """
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

        SELECT DISTINCT subsymptom_name
        FROM hierarchy
        WHERE subsymptom_name != ?
        """
        
        cursor.execute(query, (symptom_name, symptom_name))
        variants = [row[0] for row in cursor.fetchall()]
        conn.close()
        return variants

    def calculate_remedies(self):
        if not self.selected_symptoms:
            self.result_area.setText("No rubrics selected.")
            return

        result_text = ""
        
        # First, try with original symptoms and show ALL results
        original_remedy_scores, original_all_rows, original_used_symptoms = self.calculate_for_symptoms_all(self.selected_symptoms)
        
        result_text += f"=== Original Results for: {', '.join(original_used_symptoms)} ===\n\n"
        
        if original_all_rows:
            headers = ["subsymptom_id", "symptom", "depth", "hierarchy_path", "section", "remedy", "remedy_grade"]
            table_str = tabulate(original_all_rows, headers=headers, tablefmt="grid")
            result_text += table_str
            result_text += "\n\n=== All Remedies (Ranked by Total Grade) ===\n"
            
            if original_remedy_scores:
                sorted_remedies = sorted(original_remedy_scores.items(), key=lambda x: x[1], reverse=True)
                for i, (remedy, total_grade) in enumerate(sorted_remedies, 1):
                    result_text += f"{i}. {remedy} (Score: {total_grade})\n"
            else:
                result_text += "No remedies found.\n"
        else:
            result_text += "No remedies found for selected rubrics.\n"

        # Check if we need fallback (no common remedies when multiple symptoms)
        common_remedy_scores = self.get_common_remedies_only(original_all_rows, original_used_symptoms)
        
        if len(original_used_symptoms) > 1 and not common_remedy_scores:
            result_text += f"\n=== ANALYSIS: No common remedies found between the {len(original_used_symptoms)} selected symptoms ===\n"
            
            # Show what remedies each symptom has
            symptom_remedies = defaultdict(list)
            for row in original_all_rows:
                symptom = row[1]
                remedy = row[5]
                if remedy:
                    symptom_remedies[symptom].append(remedy)
            
            for symptom, remedies in symptom_remedies.items():
                unique_remedies = list(set(remedies))
                result_text += f"• {symptom}: {', '.join(unique_remedies)}\n"
            
            result_text += "\n"
            
            # Try fallback using database hierarchy navigation
            fallback_symptoms = []
            for symptom in self.selected_symptoms:
                parents = self.get_parent_symptoms_from_db(symptom)
                if parents:
                    # Use the first parent found (could be enhanced to choose best parent)
                    fallback_symptoms.append(parents[0])
                    result_text += f"Parent for '{symptom}': {parents[0]}\n"
                else:
                    fallback_symptoms.append(symptom)
                    result_text += f"No parent found for '{symptom}', using original\n"
            
            if fallback_symptoms != self.selected_symptoms:
                fallback_remedy_scores, fallback_all_rows, fallback_used_symptoms = self.calculate_for_symptoms_all(fallback_symptoms)
                
                result_text += f"\n\n=== FALLBACK: Using parent symptoms from database hierarchy ===\n"
                result_text += f"Fallback symptoms: {', '.join(fallback_used_symptoms)}\n\n"
                
                if fallback_all_rows:
                    table_str = tabulate(fallback_all_rows, headers=headers, tablefmt="grid")
                    result_text += table_str
                    result_text += "\n\n=== Fallback Remedies (Ranked by Total Grade) ===\n"
                    
                    if fallback_remedy_scores:
                        sorted_remedies = sorted(fallback_remedy_scores.items(), key=lambda x: x[1], reverse=True)
                        for i, (remedy, total_grade) in enumerate(sorted_remedies, 1):
                            result_text += f"{i}. {remedy} (Score: {total_grade})\n"
                    else:
                        result_text += "No remedies found in fallback.\n"
                else:
                    result_text += "No remedies found in fallback.\n"
                    
                # Also try expanding to include child symptoms/variants
                result_text += f"\n\n=== ALTERNATIVE: Trying to include related symptoms ===\n"
                expanded_symptoms = list(self.selected_symptoms)
                for symptom in self.selected_symptoms:
                    variants = self.get_all_symptom_variants(symptom)
                    if variants:
                        result_text += f"Related to '{symptom}': {', '.join(variants[:3])}{'...' if len(variants) > 3 else ''}\n"
                        # Add a few variants to expand search
                        expanded_symptoms.extend(variants[:2])  # Add first 2 variants
                
                if expanded_symptoms != self.selected_symptoms:
                    expanded_remedy_scores, expanded_all_rows, expanded_used_symptoms = self.calculate_for_symptoms_all(expanded_symptoms)
                    expanded_common = self.get_common_remedies_only(expanded_all_rows, expanded_used_symptoms)
                    
                    if expanded_common:
                        result_text += f"\nCommon remedies with expanded search:\n"
                        sorted_expanded = sorted(expanded_common.items(), key=lambda x: x[1], reverse=True)
                        for i, (remedy, total_grade) in enumerate(sorted_expanded, 1):
                            result_text += f"{i}. {remedy} (Score: {total_grade})\n"

        self.result_area.setText(result_text)

    def symptom_exists(self, symptom_name):
        """Check if a symptom exists in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM subsymptoms WHERE name = ?", (symptom_name,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        return exists

    def calculate_for_symptoms_all(self, symptoms):
        """Calculate ALL remedies for given symptoms (not just common ones), using best entry for each"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        remedy_scores = defaultdict(int)
        all_rows = []
        used_symptoms = []

        for symptom in symptoms:
            # Get the best entry for this symptom
            best_entry = self.get_best_symptom_entry(symptom)
            if not best_entry:
                continue
                
            best_id = best_entry[0]
            used_symptoms.append(symptom)
            
            # Get all remedies for the best entry only
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
                WHERE s.id = ?
                ORDER BY r.grade DESC
            """, (best_id,))
            
            rows = cursor.fetchall()
            all_rows.extend(rows)
            
            for row in rows:
                remedy = row[5]
                grade = row[6] if row[6] else 0
                if remedy:
                    remedy_scores[remedy] += grade

        conn.close()
        return remedy_scores, all_rows, used_symptoms

    def get_common_remedies_only(self, all_rows, used_symptoms):
        """Get only remedies that appear in ALL symptoms"""
        if len(used_symptoms) <= 1:
            return {}
        
        # Group remedies by symptom to count occurrences properly
        symptom_remedies = defaultdict(set)
        remedy_scores = defaultdict(int)
        
        for row in all_rows:
            symptom = row[1]  # symptom name
            remedy = row[5]   # remedy name
            grade = row[6] if row[6] else 0
            
            if remedy and symptom:
                symptom_remedies[symptom].add(remedy)
                remedy_scores[remedy] += grade
        
        # Find remedies that appear in ALL symptoms
        all_symptoms = set(used_symptoms)
        common_remedies = {}
        
        for remedy, total_score in remedy_scores.items():
            # Count how many symptoms this remedy appears in
            remedy_appears_in = sum(1 for symptom in all_symptoms 
                                  if remedy in symptom_remedies.get(symptom, set()))
            
            # Only include if remedy appears in ALL symptoms
            if remedy_appears_in == len(all_symptoms):
                common_remedies[remedy] = total_score
        
        return common_remedies

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