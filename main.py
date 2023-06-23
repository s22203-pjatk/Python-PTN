from flask import Flask, request, redirect, render_template, session, flash, url_for, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import os
from flask_sqlalchemy import SQLAlchemy
import datetime

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(basedir, 'instance/database.db')

app = Flask(__name__)
app.secret_key = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False, default='user')

    def __init__(self, username, password, role):
        self.username = username
        self.password = generate_password_hash(password)
        self.role = role

class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(120), nullable=False)

    def __init__(self, name, price, quantity, image):
        self.name = name
        self.price = price
        self.quantity = quantity
        self.image = image


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('part.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

    part = db.relationship('Part', backref=db.backref('purchases', lazy=True))
    user = db.relationship('User', backref=db.backref('purchases', lazy=True))

    def __init__(self, part, user, quantity, timestamp):
        self.part = part
        self.user = user
        self.quantity = quantity
        self.timestamp = timestamp


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    if 'username' in session:
        return redirect('/home')
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form.get('role', 'user')

        user = User.query.filter_by(username=username).first()

        if user:
            flash('This username is already taken!', 'danger')
        else:
            user = User(username, password, role)
            db.session.add(user)
            db.session.commit()

            flash('Registration successful!', 'success')

            return redirect('/')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['username'] = username
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect('/home')
        else:
            flash('Invalid username or password', 'danger')
            return redirect('/')

    return render_template('login.html')

@app.route('/home')
def home():
    if 'username' in session:
        parts = Part.query.all()
        return render_template('home.html', parts = parts)
    return redirect('/')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'username' in session and session['role'] == 'admin':
        if request.method == 'POST':
            for part in Part.query.all():
                stock = request.form.get(f'stock_{part.id}')
                price = request.form.get(f'price_{part.id}')

                if stock is not None:
                    stock = int(stock)
                    part.quantity = stock

                if price is not None:
                    price = float(price)
                    part.price = price

            db.session.commit()
            flash('Changes saved successfully.', 'success')

        parts = Part.query.all()
        return render_template('admin.html', parts=parts)
    return redirect('/')

@app.route('/admin/add_part', methods=['GET', 'POST'])
def add_part():
    if 'username' in session and session['role'] == 'admin':
        if request.method == 'POST':
            name = request.form['name']
            price = float(request.form['price'])
            quantity = int(request.form['quantity'])
            image = request.files['image']

            if name and price and quantity and image and allowed_file(image.filename):
                filename = image.filename

                part = Part(name=name, price=price, quantity=quantity, image=filename)
                db.session.add(part)
                db.session.commit()

                flash('New part added successfully!', 'success')
                return redirect('/admin')
            else:
                flash('Invalid form data', 'danger')

        return render_template('add_part.html')
    return redirect('/')

@app.route('/admin/delete_part/<int:part_id>', methods=['GET', 'POST'])
def delete_part(part_id):
    if 'username' in session and session['role'] == 'admin':
        part = db.session.get(Part, part_id)
        if part:
            db.session.delete(part)
            db.session.commit()
            flash('Part deleted successfully.', 'success')
        else:
            flash('There is no part of this id.', 'danger')
        return redirect('/admin')
    return redirect('/')

@app.route('/admin/purchase_history')
def purchase_history():
    if 'username' in session and session['role'] == 'admin':
        purchases = Purchase.query.all()
        return render_template('purchase_history.html', purchases=purchases)
    return redirect('/')


@app.route('/purchase', methods=['POST'])
def purchase():
    if 'username' in session:
        part_id = request.form.get('part_id')
        quantity = int(request.form.get('quantity'))

        part = db.session.get(Part, part_id)
        user = User.query.filter_by(username=session["username"]).first()
        if part and part.quantity >= quantity:
            part.quantity -= quantity

            purchase = Purchase(part=part, user=user, quantity=quantity, timestamp=datetime.datetime.now())
            db.session.add(purchase)

            db.session.commit()

            flash('Purchase successful.', 'success')
        else:
            flash('Not enough stock.', 'danger')

        return redirect('/home')
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect('/')

@app.route('/api/purchase_history')
def api_purchase_history():
    if 'username' in session and session['role'] == 'admin':
        purchases = Purchase.query.all()
        purchase_history = [
            {
                'part_name': purchase.part.name,
                'username': purchase.user.username,
                'quantity': purchase.quantity,
                'timestamp': purchase.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }
            for purchase in purchases
        ]
        return jsonify(purchase_history)
    return jsonify({'error': 'Unauthorized'})

@app.route('/api/part_history/<int:part_id>')
def api_part_history(part_id):
    if 'username' in session and session['role'] == 'admin':
        part = db.session.get(Part, part_id)
        if part:
            part_history = [
                {
                    'username': purchase.user.username,
                    'quantity': purchase.quantity,
                    'timestamp': purchase.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                }
                for purchase in part.purchases
            ]
            return jsonify(part_history)
        else:
            return jsonify({'error': 'No part of this id'})
    return jsonify({'error': 'Unauthorized'})

@app.route('/api/users')
def api_users():
    if 'username' in session and session['role'] == 'admin':
        users = User.query.all()
        user_list = [{'username': user.username, 'role': user.role} for user in users]
        return jsonify(user_list)
    return jsonify({'error': 'Unauthorized'})

@app.route('/api/parts')
def api_parts():
    if 'username' in session and session['role'] == 'admin':
        parts = Part.query.all()
        part_list = [
            {
                'name': part.name,
                'price': part.price,
                'quantity': part.quantity,
                'image': part.image
            }
            for part in parts
        ]
        return jsonify(part_list)
    return jsonify({'error': 'Unauthorized'})

@app.route('/api/register', methods=['POST'])
def api_register():
    if 'username' in session and session['role'] == 'admin':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')

        if username and password:
            user = User(username, password, role)
            db.session.add(user)
            db.session.commit()

            return jsonify({'message': 'Registration successful'})
        else:
            return jsonify({'error': 'Invalid form data'})

    return jsonify({'error': 'Unauthorized'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

