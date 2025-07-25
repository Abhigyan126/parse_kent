import sqlite3
import csv
from tabulate import tabulate

def display_symptom_info(db_path, symptom_name):
    """Display remedies and location for a given subsymptom name using tabulate."""
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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(query, (symptom_name,))
        rows = cursor.fetchall()
        headers = [desc[0] for desc in cursor.description]

        if rows:
            print(f"\n=== Remedies and Hierarchy for Subsymptom: '{symptom_name}' ===\n")
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            print(f"No data found for subsymptom: {symptom_name}")
    finally:
        conn.close()

def export_subsymptoms_with_remedies_to_csv(db_path, output_csv_path="subsymptoms_with_remedies.csv"):
    """
    Identifies all subsymptoms that have associated remedies and exports their names
    and corresponding section names to a CSV file.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Query to select distinct subsymptom names and their section names
        # for subsymptoms that have at least one entry in the remedies table.
        query = """
        SELECT DISTINCT
            s.name AS subsymptom_name,
            sec.name AS section_name
        FROM
            subsymptoms s
        INNER JOIN
            remedies r ON s.id = r.subsymptom_id
        LEFT JOIN
            sections sec ON s.section_id = sec.id
        ORDER BY
            section_name, subsymptom_name;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if rows:
            with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                csv_writer = csv.writer(csvfile)
                # Write header row
                csv_writer.writerow(["Subsymptom Name", "Section Name"])
                # Write data rows
                csv_writer.writerows(rows)
            print(f"\nSuccessfully exported {len(rows)} subsymptoms with remedies to '{output_csv_path}'.")
        else:
            print("No subsymptoms with associated remedies found in the database.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

# Example usage:
db_file = "kent_repertory.db"

# First, call your existing function for a specific symptom (as per your original request)
display_symptom_info(db_file, "Right testis tearing pain extending to abdomen")
print("\n" + "="*80 + "\n") # Separator for clarity

# Then, call the new function to export all subsymptoms with remedies
export_subsymptoms_with_remedies_to_csv(db_file)