import re

files = [
    'templates/brain-tumor.html',
    'templates/lung.html',
    'templates/cataract.html',
    'templates/disease_predict.html',
    'templates/videocall.html'
]

header_replacement = """
    <div class="dashboard-layout">
        {% if role == 'doctor' %}
            {% set doctor = user %}
            {% include 'partials/doctor_sidebar.html' %}
        {% else %}
            {% set patient = user %}
            {% include 'partials/patient_sidebar.html' %}
        {% endif %}
        
        <main class="dashboard-main">
            <header class="dashboard-header">
                <div class="header-search"></div>
                <div class="header-actions">
                    <div class="user-pill">
                        <div class="avatar">{{ username[0]|upper }}</div>{{ username }}
                    </div>
                    <a href="{{url_for('logout')}}" class="btn-outline" style="padding:6px 12px;font-size:0.85rem; border-radius:8px;"><i class="fas fa-sign-out-alt"></i></a>
                </div>
            </header>
            
            <div class="page-container" style="padding: 2rem;">
"""

for filepath in files:
    with open(filepath, 'r') as f:
        html = f.read()
    
    # Replace header block
    # Note: Using regex to match from <header class="header"> to <div class="page-container">
    pattern = r'<header class="header">.*?</header>\s*<div class="page-container">'
    html = re.sub(pattern, header_replacement.strip(), html, flags=re.DOTALL)
    
    # Replace closing tags
    html = html.replace('</body>', '</main></div></body>')
    
    with open(filepath, 'w') as f:
        f.write(html)
    print(f"Updated {filepath}")

