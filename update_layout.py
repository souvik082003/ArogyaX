import re
import os

# 1. Create partials directory
os.makedirs('templates/partials', exist_ok=True)

# 2. Extract Doctor Sidebar from doctor-dashboard.html
with open('templates/doctor-dashboard.html', 'r') as f:
    doc_html = f.read()

doc_sidebar_match = re.search(r'(<!-- SIDEBAR -->\s*<aside class="sidebar".*?</aside>)', doc_html, re.DOTALL)
if doc_sidebar_match:
    with open('templates/partials/doctor_sidebar.html', 'w') as f:
        f.write(doc_sidebar_match.group(1))

# Update doctor-dashboard.html to use include
new_doc_html = doc_html.replace(doc_sidebar_match.group(1), "{% include 'partials/doctor_sidebar.html' %}")
with open('templates/doctor-dashboard.html', 'w') as f:
    f.write(new_doc_html)


# 3. Extract Patient Sidebar from patient-dashboard.html
with open('templates/patient-dashboard.html', 'r') as f:
    pat_html = f.read()

pat_sidebar_match = re.search(r'(<!-- SIDEBAR -->\s*<aside class="sidebar".*?</aside>)', pat_html, re.DOTALL)
if pat_sidebar_match:
    with open('templates/partials/patient_sidebar.html', 'w') as f:
        f.write(pat_sidebar_match.group(1))

# Update patient-dashboard.html to use include
new_pat_html = pat_html.replace(pat_sidebar_match.group(1), "{% include 'partials/patient_sidebar.html' %}")
with open('templates/patient-dashboard.html', 'w') as f:
    f.write(new_pat_html)

print("Partials created and dashboards updated.")
