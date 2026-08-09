import re

with open('app.py', 'r') as f:
    code = f.read()

# Define a function to inject the user variables
def inject_user_vars(match):
    return match.group(0) + """
    user = get_current_user()
    role = user.get('role', 'patient') if user else 'patient'
    user_str = dict(user) if user else {}
    if user_str and '_id' in user_str:
        user_str['_id'] = str(user_str['_id'])
"""

# For each route, find the def and inject the variables.
# We'll replace the render_template calls separately.

routes = ['braintumor', 'lung', 'cataract', 'disease_predict', 'videocall']

for route in routes:
    # 1. Update the variables
    # Find something like:
    # def braintumor():
    #     user = get_current_user()
    #     username = user['username']
    
    # Actually, they all already have:
    # user = get_current_user()
    # username = user['username']
    
    # Let's just replace that exact pattern with the expanded one
    pattern = r'def ' + route + r'\(\):\n\s+user = get_current_user\(\)\n\s+username = user\[\'username\'\]'
    replacement = f"""def {route}():
    user = get_current_user()
    username = user['username'] if user else 'Guest'
    role = user.get('role', 'patient') if user else 'patient'
    user_str = dict(user) if user else {{}}
    if user_str and '_id' in user_str:
        user_str['_id'] = str(user_str['_id'])"""
    code = re.sub(pattern, replacement, code)
    
    # 2. Update render_template to include role and user
    # Find render_template('braintumor.html', username=username, ...)
    rt_pattern = r"render_template\('" + route.replace('_', '-') + r"\.html', username=username"
    rt_replacement = f"render_template('{route.replace('_', '-')}.html', username=username, role=role, user=user_str"
    
    # Note: disease_predict route uses disease_predict.html (underscore), let's check
    if route == 'disease_predict':
        rt_pattern = r"render_template\('disease_predict\.html', username=username"
        rt_replacement = f"render_template('disease_predict.html', username=username, role=role, user=user_str"
    elif route == 'videocall':
        rt_pattern = r"render_template\('videocall\.html', username=username"
        rt_replacement = f"render_template('videocall.html', username=username, role=role, user=user_str"
    
    code = re.sub(rt_pattern, rt_replacement, code)

with open('app.py', 'w') as f:
    f.write(code)

print("app.py updated!")
