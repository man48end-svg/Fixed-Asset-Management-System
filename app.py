from flask import Flask, render_template, request, redirect, session, url_for, abort
import pyodbc

app = Flask(__name__)
app.secret_key = 'bank_secret_123'

# 1. DATABASE CONNECTION
def get_db_connection():
    conn_str = (
        r'DRIVER={ODBC Driver 17 for SQL Server};'
        r'SERVER=localhost\SQLEXPRESS02;'
        r'DATABASE=FIXEDASSET2SQL;'
        r'Trusted_Connection=yes;'
        r'connection Timeout=5;'
    )
    return pyodbc.connect(conn_str)

# 2. LOGIN & AUTHENTICATION
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Admin (Full Access)
        if username == 'admin' and password == '1234':
            session.update({'user': username, 'role': 'admin', 'scope': 'All'})
            return redirect(url_for('home'))
            
        # Head Office Chiefs (Read Only - Sees All)
        elif username == 'ho_chief' and password == 'chief123':
            session.update({'user': username, 'role': 'manager', 'scope': 'All'})
            return redirect(url_for('home'))

        # District Directors (Read Only - Sees their specific District only)
        # These names MUST match the "LOCATION NAME HO/District" column in your SQL table
        districts = {
            'arada_dir':     {'pw': 'arada123', 'scope': 'Arada District'},
            'merkato_dir':   {'pw': 'merka456', 'scope': 'Merkato District'},
            'northeast_dir': {'pw': 'north789', 'scope': 'North East District'},
            'southwest_dir': {'pw': 'south111', 'scope': 'South west District'},
            'west_dir':      {'pw': 'west222',  'scope': 'west district'},
            'north_dir':     {'pw': 'north333', 'scope': 'north District'},
            'east_dir':     {'pw': 'east444', 'scope': 'east District'}
        }

        if username in districts and password == districts[username]['pw']:
            session.update({
                'user': username, 
                'role': 'manager', 
                'scope': districts[username]['scope']
            })
            return redirect(url_for('home'))
            
        return "Login Failed"
    
    return render_template('login.html') # Fixed: Added closing parenthesis

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

# 3. VIEW DATA (Filtered by Role/Scope)
@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # If a District Director is logged in, filter by their specific scope
    if session.get('scope') != 'All':
        sql = "SELECT * FROM [dbo].[All Data] WHERE [LOCATION NAME HO/District] = ?"
        cursor.execute(sql, (session.get('scope'),))
    else:
        # Admin and HO Chiefs see everything
        cursor.execute("SELECT * FROM [dbo].[All Data]")
    
    columns = [column[0] for column in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return render_template('index.html', data=data) # Fixed: Added closing parenthesis

# 4. SEARCH (Maintains filtering)
@app.route('/search', methods=['GET'])
def search_assets():
    if 'user' not in session:
        return redirect(url_for('login'))

    query = request.args.get('query', '').strip()
    if not query:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    term = f"%{query}%"

    # Filtered search: Users only find items they are allowed to see within their specific scope
    if session.get('scope') and session.get('scope') != 'All':
        # Added LOCATION2 to the search logic for scoped users
        sql = """SELECT * FROM [dbo].[All Data] 
                 WHERE [LOCATION NAME HO/District] = ? 
                 AND ([CodeID] LIKE ? 
                      OR [descreption] LIKE ? 
                      OR [EMPLOYEE NAME] LIKE ? 
                      OR [LOCATION2] LIKE ?)"""
        
        # We pass scope first, then the 4 search terms for the 4 LIKE clauses
        cursor.execute(sql, (session.get('scope'), term, term, term, term))
        
    else:
        # For 'All' / Admin: Search across all columns including LOCATION2
        sql = """SELECT * FROM [dbo].[All Data] 
                 WHERE [CodeID] LIKE ? 
                 OR [descreption] LIKE ? 
                 OR [EMPLOYEE NAME] LIKE ?
                 OR [LOCATION NAME HO/District] LIKE ?
                 OR [LOCATION2] LIKE ?"""
        
        # 5 placeholders = 5 terms in the tuple
        cursor.execute(sql, (term, term, term, term, term))

    # Get column names for dictionary mapping
    columns = [column[0] for column in cursor.description] 
    
    # Fetch all matching rows
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    
    cursor.close()
    conn.close()

    # Pass the data back to your results page
    return render_template('index.html', data=data)

# 5. ADD NEW ASSET (Admin Only)
@app.route('/add', methods=['GET', 'POST'])
def add():
    if session.get('role') != 'admin':
        abort(403)
        
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO [dbo].[All Data]
            ([CodeID], [DESCREPTION], [SERIAL NUMBER], [LOCATION NAME HO/District], 
             [LOCATION2], [EMPLOYEE ID], [EMPLOYEE NAME], [CONDITION], [REMARK]) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form['CodeID'], request.form['DESCREPTION'],
            request.form['SERIAL NUMBER'], request.form['LOCATION NAME HO/District'],
            request.form['LOCATION2'], request.form['EMPLOYEE ID'],
            request.form['EMPLOYEE NAME'], request.form['CONDITION'],
            request.form['REMARK']
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add.html')

# 6. EDIT ASSET (Admin Only)
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_asset(id):
    if session.get('role') != 'admin':
        abort(403)

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE [dbo].[All Data]
            SET [CodeID] = ?, [DESCREPTION] = ?, [SERIAL NUMBER] = ?, 
                [LOCATION NAME HO/District] = ?, [LOCATION2] = ?, 
                [EMPLOYEE ID] = ?, [EMPLOYEE NAME] = ?, [CONDITION] = ?, [REMARK] = ?
            WHERE [ID] = ?
        """, (
            request.form['CodeID'], request.form['DESCREPTION'],
            request.form['SERIAL NUMBER'], request.form['LOCATION NAME HO/District'],
            request.form['LOCATION2'], request.form['EMPLOYEE ID'],
            request.form['EMPLOYEE NAME'], request.form['CONDITION'],
            request.form['REMARK'], id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM [dbo].[All Data] WHERE [ID] = ?", (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Asset not found", 404
        
    columns = [column[0] for column in cursor.description]
    asset_data = dict(zip(columns, row))
    conn.close()
    return render_template('edit.html', data=asset_data)

# 7. DELETE ASSET (Admin Only)
@app.route('/delete/<int:id>')
def delete_asset(id):
    if session.get('role') != 'admin':
        abort(403)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [dbo].[All Data] WHERE [ID] = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# 8. LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)