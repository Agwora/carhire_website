from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import database as db
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

db.init_db()

@app.route('/')
def index():
    search = request.args.get('search', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    sort = request.args.get('sort', '')
    
    filters = {}
    if search:
        filters['search'] = search
    if min_price and min_price.isdigit():
        filters['min_price'] = int(min_price)
    if max_price and max_price.isdigit():
        filters['max_price'] = int(max_price)
    if sort in ['price_asc', 'price_desc']:
        filters['sort'] = sort
    
    cars = db.get_all_cars(filters if filters else None)
    
    return render_template('index.html', 
                         cars=cars, 
                         search=search,
                         min_price=min_price,
                         max_price=max_price,
                         sort=sort)

@app.route('/book/<int:car_id>', methods=['GET', 'POST'])
def book(car_id):
    car = db.get_car_by_id(car_id)
    if not car:
        return "Car not found", 404
    
    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        customer_email = request.form.get('customer_email')
        pickup_date = request.form.get('pickup_date')
        return_date = request.form.get('return_date')
        
        errors = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        if not all([customer_name, customer_email, pickup_date, return_date]):
            errors.append("All fields are required.")
        
        if pickup_date and pickup_date < today:
            errors.append("Pickup date cannot be in the past.")
        
        if return_date and pickup_date and return_date <= pickup_date:
            errors.append("Return date must be after pickup date.")
        
        if not errors and db.check_availability(car_id, pickup_date, return_date):
            days = (datetime.strptime(return_date, '%Y-%m-%d') - datetime.strptime(pickup_date, '%Y-%m-%d')).days
            total_price = days * car['price_per_day']
            booking_id = db.create_booking(car_id, customer_name, customer_email, pickup_date, return_date, total_price)
            return redirect(url_for('confirm', booking_id=booking_id))
        elif not errors:
            errors.append("Car is not available for the selected dates.")
        
        return render_template('book.html', car=car, errors=errors, 
                             customer_name=customer_name, customer_email=customer_email,
                             pickup_date=pickup_date, return_date=return_date)
    
    return render_template('book.html', car=car, errors=None)

@app.route('/confirm/<int:booking_id>')
def confirm(booking_id):
    booking = db.get_booking_by_id(booking_id)
    if not booking:
        return "Booking not found", 404
    return render_template('success.html', booking=booking)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = db.get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username = ? AND password_hash = ?", 
                           (username, password)).fetchone()
        conn.close()
        
        if admin:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")
    
    return render_template('admin_login.html', error=None)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    cars = db.get_all_cars_admin()
    bookings = db.get_all_bookings()
    return render_template('admin_dashboard.html', cars=cars, bookings=bookings)

@app.route('/admin/add_car', methods=['POST'])
def admin_add_car():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    name = request.form.get('name')
    price = request.form.get('price')
    image_url = request.form.get('image_url', '')
    is_available = request.form.get('is_available') == 'on'
    
    if name and price and price.isdigit():
        db.add_car(name, int(price), image_url, is_available)
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_car/<int:car_id>', methods=['POST'])
def admin_edit_car(car_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    name = request.form.get('name')
    price = request.form.get('price')
    image_url = request.form.get('image_url', '')
    is_available = request.form.get('is_available') == 'on'
    
    if name and price and price.isdigit():
        db.update_car(car_id, name, int(price), image_url, is_available)
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_car/<int:car_id>', methods=['POST'])
def admin_delete_car(car_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    db.delete_car(car_id)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/cancel_booking/<int:booking_id>', methods=['POST'])
def admin_cancel_booking(booking_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    db.cancel_booking(booking_id)
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
