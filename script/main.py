import requests
import pandas as pd
from bs4 import BeautifulSoup
import sqlite3
from collections import deque
import time

# Configuration
BASE_URL = "https://www.kentrepertory.com/"
COLOR_TO_GRADE = {
    "green": 1,
    "yellow": 2,
    "red": 3
}
DB_NAME = "kent_repertory.db"

class KentRepertoryHierarchyScraper:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.conn = None
        self.setup_database()
    
    def setup_database(self):
        """Initialize SQLite database with required tables"""
        self.conn = sqlite3.connect(self.db_name)
        cursor = self.conn.cursor()
        
        # Create sections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL
            )
        ''')
        
        # Create subsymptoms table (hierarchical - can reference itself)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subsymptoms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                section_id INTEGER,
                parent_subsymptom_id INTEGER,
                depth INTEGER DEFAULT 0,
                FOREIGN KEY (section_id) REFERENCES sections(id),
                FOREIGN KEY (parent_subsymptom_id) REFERENCES subsymptoms(id)
            )
        ''')
        
        # Create remedies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS remedies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                grade INTEGER,
                section_id INTEGER,
                subsymptom_id INTEGER,
                FOREIGN KEY (section_id) REFERENCES sections(id),
                FOREIGN KEY (subsymptom_id) REFERENCES subsymptoms(id)
            )
        ''')
        
        self.conn.commit()
    
    def insert_section(self, name, url):
        """Insert section and return its ID"""
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO sections (name, url) VALUES (?, ?)', (name, url))
        self.conn.commit()
        
        cursor.execute('SELECT id FROM sections WHERE name = ?', (name,))
        return cursor.fetchone()[0]
    
    def insert_subsymptom(self, name, url, section_id, parent_subsymptom_id=None, depth=0):
        """Insert subsymptom and return its ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO subsymptoms (name, url, section_id, parent_subsymptom_id, depth) 
            VALUES (?, ?, ?, ?, ?)
        ''', (name, url, section_id, parent_subsymptom_id, depth))
        self.conn.commit()
        return cursor.lastrowid
    
    def insert_remedy(self, name, grade, section_id, subsymptom_id=None):
        """Insert remedy"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO remedies (name, grade, section_id, subsymptom_id) 
            VALUES (?, ?, ?, ?)
        ''', (name, grade, section_id, subsymptom_id))
        self.conn.commit()
    
    def get_page_content(self, url):
        """Fetch and parse page content"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove navigation dropdowns to prevent false subsymptom detection
            nav_dropdowns = soup.select('li.dropdown')
            for dropdown in nav_dropdowns:
                dropdown.decompose()
            
            # Remove any other navigation elements that might interfere
            nav_elements = soup.select('nav, .navbar, .navigation')
            for nav in nav_elements:
                nav.decompose()
                
            return soup
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_remedies(self, soup):
        """Extract remedies from page - specifically from panel-body div"""
        remedies = []
        
        # Look specifically in the panel-body div for remedies
        panel_body = soup.select('div.panel-body')
        
        for panel in panel_body:
            remedy_tags = panel.select('ul.list-inline a.remedy')
            
            for tag in remedy_tags:
                name = tag.text.strip()
                classes = tag.get("class", [])
                grade = next(
                    (COLOR_TO_GRADE[color] for color in COLOR_TO_GRADE 
                     if any(color in cls for cls in classes)),
                    "Unknown"
                )
                if name:  # Only add if name is not empty
                    remedies.append((name, grade))
        
        return remedies
    
    def extract_subsymptoms(self, soup):
        """Extract subsymptoms from page - specifically from panel-body div"""
        subsymptoms = []
        
        # Look specifically in the panel-body div for subsymptoms
        panel_body = soup.select('div.panel-body')
        
        for panel in panel_body:
            # Find all list items with links inside the panel-body
            sub_symptom_lists = panel.select('ul.list-unstyled.equal-height-list')
            
            for ul in sub_symptom_lists:
                links = ul.find_all("a", href=True)  # Only get links with href
                for link in links:
                    sub_name = link.text.strip()
                    sub_url = link.get("href")
                    
                    # Filter out navigation links and ensure it's a symptom link
                    if (sub_url and sub_name and 
                        'symptoms.php' in sub_url and  # Only symptom pages
                        not any(nav_text in sub_name.lower() for nav_text in 
                               ['session', 'new session', 'resolve', 'start', 'menu', 'home'])):
                        
                        # Handle relative URLs
                        if not sub_url.startswith('http'):
                            sub_url = BASE_URL + sub_url.lstrip('/')
                        subsymptoms.append((sub_name, sub_url))
        
        return subsymptoms
    
    def process_hierarchy_iteratively(self, df):
        """Process the entire hierarchy iteratively using a queue-based approach"""
        
        # Process each section from CSV
        for _, row in df.iterrows():
            section_name = row['name']
            section_url = BASE_URL + row['url']
            
            print(f"\n=== PROCESSING SECTION: {section_name} ===")
            
            # Insert section into database
            section_id = self.insert_section(section_name, section_url)
            
            # Get section page content
            soup = self.get_page_content(section_url)
            if not soup:
                continue
            
            # Extract and store section-level remedies
            remedies = self.extract_remedies(soup)
            print(f"Found {len(remedies)} remedies in section")
            for remedy_name, grade in remedies:
                self.insert_remedy(remedy_name, grade, section_id)
            
            # Extract subsymptoms for hierarchical processing
            subsymptoms = self.extract_subsymptoms(soup)
            print(f"Found {len(subsymptoms)} subsymptoms in section")
            
            # Queue-based iterative processing for hierarchy
            # Each item in queue: (name, url, section_id, parent_subsymptom_id, depth)
            processing_queue = deque()
            
            # Add initial subsymptoms to queue
            for sub_name, sub_url in subsymptoms:
                processing_queue.append((sub_name, sub_url, section_id, None, 1))
            
            # Process queue iteratively (no recursion)
            processed_count = 0
            while processing_queue:
                current_name, current_url, current_section_id, parent_id, depth = processing_queue.popleft()
                
                print(f"  Processing subsymptom (depth {depth}): {current_name}")
                
                # Insert current subsymptom
                current_subsymptom_id = self.insert_subsymptom(
                    current_name, current_url, current_section_id, parent_id, depth
                )
                
                # Get content of current subsymptom page
                current_soup = self.get_page_content(current_url)
                if not current_soup:
                    continue
                
                # Extract and store remedies for current subsymptom
                current_remedies = self.extract_remedies(current_soup)
                print(f"    Found {len(current_remedies)} remedies")
                for remedy_name, grade in current_remedies:
                    self.insert_remedy(remedy_name, grade, current_section_id, current_subsymptom_id)
                
                # Extract child subsymptoms and add to queue
                child_subsymptoms = self.extract_subsymptoms(current_soup)
                print(f"    Found {len(child_subsymptoms)} child subsymptoms")
                
                for child_name, child_url in child_subsymptoms:
                    # Add child to queue with current subsymptom as parent
                    processing_queue.append((child_name, child_url, current_section_id, current_subsymptom_id, depth + 1))
                
                processed_count += 1
                
                # Add delay to be respectful to the server
                
                # Progress indicator
                if processed_count % 10 == 0:
                    print(f"  Processed {processed_count} subsymptoms so far...")
            
            print(f"Completed section '{section_name}' - Total subsymptoms processed: {processed_count}")
    
    def get_hierarchy_summary(self):
        """Print summary of the hierarchy"""
        cursor = self.conn.cursor()
        
        print("\n=== HIERARCHY SUMMARY ===")
        
        # Count sections
        cursor.execute('SELECT COUNT(*) FROM sections')
        section_count = cursor.fetchone()[0]
        print(f"Total sections: {section_count}")
        
        # Count subsymptoms by depth
        cursor.execute('SELECT depth, COUNT(*) FROM subsymptoms GROUP BY depth ORDER BY depth')
        depth_counts = cursor.fetchall()
        print("Subsymptoms by depth:")
        for depth, count in depth_counts:
            print(f"  Depth {depth}: {count}")
        
        # Count total remedies
        cursor.execute('SELECT COUNT(*) FROM remedies')
        remedy_count = cursor.fetchone()[0]
        print(f"Total remedies: {remedy_count}")
        
        # Count remedies by grade
        cursor.execute('SELECT grade, COUNT(*) FROM remedies GROUP BY grade ORDER BY grade')
        grade_counts = cursor.fetchall()
        print("Remedies by grade:")
        for grade, count in grade_counts:
            print(f"  Grade {grade}: {count}")
    
    def get_sample_hierarchy(self, section_name, limit=5):
        """Print sample hierarchy for a section"""
        cursor = self.conn.cursor()
        
        print(f"\n=== SAMPLE HIERARCHY FOR '{section_name}' ===")
        
        # Get section ID
        cursor.execute('SELECT id FROM sections WHERE name = ?', (section_name,))
        result = cursor.fetchone()
        if not result:
            print("Section not found")
            return
        
        section_id = result[0]
        
        # Get subsymptoms with their hierarchy
        cursor.execute('''
            SELECT s.id, s.name, s.depth, s.parent_subsymptom_id,
                   p.name as parent_name
            FROM subsymptoms s
            LEFT JOIN subsymptoms p ON s.parent_subsymptom_id = p.id
            WHERE s.section_id = ?
            ORDER BY s.depth, s.id
            LIMIT ?
        ''', (section_id, limit))
        
        subsymptoms = cursor.fetchall()
        
        for sub_id, name, depth, parent_id, parent_name in subsymptoms:
            indent = "  " * depth
            parent_info = f" (parent: {parent_name})" if parent_name else " (root level)"
            print(f"{indent}{name}{parent_info}")
            
            # Get remedies for this subsymptom
            cursor.execute('SELECT name, grade FROM remedies WHERE subsymptom_id = ? LIMIT 3', (sub_id,))
            remedies = cursor.fetchall()
            for remedy_name, grade in remedies:
                print(f"{indent}  → {remedy_name} (Grade {grade})")
    
    def debug_extraction(self, url, section_name):
        """Debug method to see what's being extracted from a specific URL"""
        print(f"\n=== DEBUG EXTRACTION FOR: {section_name} ===")
        print(f"URL: {url}")
        
        soup = self.get_page_content(url)
        if not soup:
            print("Failed to get page content")
            return
        
        # Check what navigation elements were removed
        print("\n--- Checking for remaining navigation elements ---")
        nav_elements = soup.select('li.dropdown, nav, .navbar, .navigation')
        print(f"Remaining nav elements: {len(nav_elements)}")
        
        # Debug panel-body content
        panel_bodies = soup.select('div.panel-body')
        print(f"\n--- Found {len(panel_bodies)} panel-body divs ---")
        
        for i, panel in enumerate(panel_bodies):
            print(f"\nPanel {i+1}:")
            
            # Check for remedies
            remedy_tags = panel.select('ul.list-inline a.remedy')
            print(f"  Remedies found: {len(remedy_tags)}")
            for remedy in remedy_tags[:3]:  # Show first 3
                print(f"    - {remedy.text.strip()}")
            
            # Check for subsymptoms
            subsymptom_lists = panel.select('ul.list-unstyled.equal-height-list')
            print(f"  Subsymptom lists found: {len(subsymptom_lists)}")
            
            for j, ul in enumerate(subsymptom_lists):
                links = ul.find_all("a", href=True)
                print(f"    List {j+1}: {len(links)} links")
                for link in links[:3]:  # Show first 3
                    href = link.get("href")
                    text = link.text.strip()
                    is_symptom = 'symptoms.php' in href if href else False
                    print(f"      - {text} -> {href} (is_symptom: {is_symptom})")
        
        # Test actual extraction methods
        remedies = self.extract_remedies(soup)
        subsymptoms = self.extract_subsymptoms(soup)
        
        print(f"\n--- FINAL EXTRACTION RESULTS ---")
        print(f"Remedies extracted: {len(remedies)}")
        print(f"Subsymptoms extracted: {len(subsymptoms)}")
        
        if subsymptoms:
            print("\nFirst few subsymptoms:")
            for name, url in subsymptoms[:5]:
                print(f"  - {name} -> {url}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Debug function to test extraction before running full scraper
def debug_single_section(csv_file, section_index=0):
    """Debug extraction for a single section"""
    try:
        df = pd.read_csv(csv_file)
        if section_index >= len(df):
            print(f"Section index {section_index} out of range. CSV has {len(df)} sections.")
            return
        
        row = df.iloc[section_index]
        section_name = row['name']
        section_url = BASE_URL + row['url']
        
        scraper = KentRepertoryHierarchyScraper()
        scraper.debug_extraction(section_url, section_name)
        scraper.close()
        
    except Exception as e:
        print(f"Debug error: {e}")

# Main execution
def main():
    # Initialize scraper
    scraper = KentRepertoryHierarchyScraper()
    
    try:
        # Read CSV file
        df = pd.read_csv("section.csv")
        print(f"Loaded {len(df)} sections from CSV")
        
        # Process hierarchy iteratively
        scraper.process_hierarchy_iteratively(df)
        
        # Print summary
        scraper.get_hierarchy_summary()
        
        # Print sample hierarchy for first section
        if len(df) > 0:
            first_section = df.iloc[0]['name']
            scraper.get_sample_hierarchy(first_section)
        
    except FileNotFoundError:
        print("Error: section.csv file not found!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        scraper.close()

# Test function to debug before running main
def test_debug():
    print("=== TESTING EXTRACTION ===")
    debug_single_section("section.csv", 0)  # Debug first section
    
if __name__ == "__main__":
    # Uncomment the next line to debug first, then comment it and run main()
    # test_debug()
    main()