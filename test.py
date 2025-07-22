import sqlite3
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

display_symptom_info("kent_repertory.db", "Right testis tearing pain extending to abdomen")
