import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from mlxtend.frequent_patterns import apriori
from mlxtend.frequent_patterns import association_rules
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask_migrate import Migrate


app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = r'sqlite:///C:\Users\deeks\OneDrive\Desktop\jupyter test\major_project\4- updated accident detection(3)\4- updated accident detection(3)\4- updated accident detection\accidents.db'
app.config['SECRET_KEY'] = '123'  # Change this to a random value
app.config['EMAIL_PASSWORD'] = 'jjjx vzwb kcfv byok'  # Change this to your email password
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Define User model
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    email = db.Column(db.String(100))  # Add email field

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"

# Define Accident model
class Accident(db.Model):
    __tablename__ = 'accident'
    id = db.Column(db.Integer, primary_key=True)
    route = db.Column(db.String(100))
    location = db.Column(db.String(100))
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    casualties = db.Column(db.Integer)

    def __repr__(self):
        return f"<Accident(id={self.id}, route={self.route}, location={self.location}, date={self.date}, time={self.time}, casualties={self.casualties})>"

# Configure Login Manager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Load the dataset
dataset = pd.read_csv(r'C:\Users\deeks\Downloads\data_sets.csv')

# Encode 'Severity' column to numerical format
severity_mapping = {'high': 2, 'medium': 1, 'low': 0}
dataset['severity_encoded'] = dataset['Severity'].map(severity_mapping)

# Encode 'location' column using one-hot encoding
dataset = pd.get_dummies(dataset, columns=['location'])

# Ensure all columns are boolean after one-hot encoding
dataset = dataset.astype(bool)

# Data Preprocessing
# Assume 'Severity' is the target variable
X = dataset.drop('severity_encoded', axis=1)
y = dataset['severity_encoded']

# Split dataset into train and test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Apply Apriori algorithm to find frequent itemsets
frequent_itemsets = apriori(X_train, min_support=0.1, use_colnames=True)

# Apply association rule mining
rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1)

# SVM Model
svm_model = SVC(kernel='linear')
svm_model.fit(X_train, y_train)

# Evaluate SVM model
svm_accuracy = svm_model.score(X_test, y_test)


print("SVM Accuracy:", svm_accuracy)
print("Association Rules:")
print(rules)


# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('Invalid username. Please register first.', 'error')
            return redirect(url_for('register'))  # Redirect to register page
        elif user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
            return redirect(url_for('login'))  # Redirect to login page with error message
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])  # Hash password
        mail = request.form['mail']  # Add this line to get the email address from the form
        new_user = User(username=username, password=password, email=mail)  # Modify User creation to include email
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/report_accident', methods=['GET', 'POST'])
@login_required
def report_accident():
    if request.method == 'POST':
        route = request.form['route']
        location = request.form['location']
        
        # Change date format to 'yyyy-mm-dd'
        date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        
        # Parse time input and ignore additional characters
        time_input = request.form['time'].split(':')[0] + ':' + request.form['time'].split(':')[1]
        
        # Change time format to 'HH:MM'
        time = datetime.strptime(time_input, '%H:%M').time()
        
        casualties = request.form['casualties']
        new_accident = Accident(route=route, location=location, date=date, time=time, casualties=casualties)
        db.session.add(new_accident)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('report_accident.html')

@app.route('/view_accidents', methods=['GET', 'POST'])
@login_required
def view_accidents():
    if request.method == 'POST':
        selected_route = request.form['route']
        accidents = fetch_accidents(selected_route)
        send_email(accidents)
        return render_template('view_accidents.html', accidents=accidents)
    return render_template('view_accidents.html')

def fetch_accidents(selected_route):
    accidents = Accident.query.filter_by(route=selected_route).all()
    accidents_data = []
    for accident in accidents:
        accident_data = {
            'location': accident.location,
            'date': accident.date.strftime('%Y-%m-%d'),  # Adjust date format string
            'time': accident.time.strftime('%H:%M'),
            'casualties': accident.casualties
        }
        accidents_data.append(accident_data)
        print(accident_data)
    return accidents_data

def send_email(accidents):
    # Email configuration
    sender_email = "deekshithacheemalamarri@gmail.com"  # Replace with your email

    # Retrieve receiver email from the database
    receiver_user = User.query.filter_by(username=current_user.username).first()
    receiver_email = receiver_user.email if receiver_user else None

    if receiver_email:
        # Message setup
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "Accident Report"

        # Compose message
        body = "Accident Report:\n\n"
        for accident in accidents:
            body += f"Location: {accident['location']}\nDate: {accident['date']}\nTime: {accident['time']}\nCasualties: {accident['casualties']}\n\n"

        msg.attach(MIMEText(body, 'plain'))

        # Sending the email
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(sender_email, app.config['EMAIL_PASSWORD'])  # Use email password from config
            smtp_server.sendmail(sender_email, receiver_email, msg.as_string())
    else:
        print("Receiver email not found")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
