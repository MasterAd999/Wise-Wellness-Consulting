import os
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///diary.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class DiaryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/')
def index():
    return 'Hello, World!'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('diary'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/diary', methods=['GET', 'POST'])
@login_required
def diary():
    if request.method == 'POST':
        text = request.form['text']
        sentiment = TextBlob(text).sentiment.polarity
        sentiment_label = 'positive' if sentiment > 0 else 'negative' if sentiment < 0 else 'neutral'
        new_entry = DiaryEntry(text=text, sentiment=sentiment_label, user_id=current_user.id)
        db.session.add(new_entry)
        db.session.commit()
        flash('Entry added!')
        return redirect(url_for('diary'))
    return render_template('diary.html')

@app.route('/entries')
@login_required
def entries():
    user_entries = DiaryEntry.query.filter_by(user_id=current_user.id).all()
    return render_template('entries.html', entries=user_entries)

@app.route('/leaderboard')
def leaderboard():
    users = User.query.all()
    leaderboard_data = []
    for user in users:
        entry_count = DiaryEntry.query.filter_by(user_id=user.id).count()
        leaderboard_data.append({'username': user.username, 'entries': entry_count})
    leaderboard_data.sort(key=lambda x: x['entries'], reverse=True)
    return render_template('leaderboard.html', leaderboard=leaderboard_data)

@app.route('/send_notification')
@login_required
def send_notification():
    msg = Message('Hello from Love My Diary App',
                  sender='your-email@example.com',
                  recipients=[current_user.username])
    msg.body = "This is a test email sent from your Flask application!"
    mail.send(msg)
    flash('Notification sent!')
    return redirect(url_for('diary'))

@app.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer_email=current_user.username,
        line_items=[{
            'price': os.environ.get('STRIPE_PRICE_ID'),
            'quantity': 1,
        }],
        mode='subscription',
        success_url=url_for('subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('subscription_cancel', _external=True),
    )
    return redirect(session.url, code=303)

@app.route('/subscription_success')
@login_required
def subscription_success():
    flash('Subscription successful!')
    return redirect(url_for('diary'))

@app.route('/subscription_cancel')
@login_required
def subscription_cancel():
    flash('Subscription canceled.')
    return redirect(url_for('diary'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.root_path + '/static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(debug=True)