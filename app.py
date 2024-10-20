from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime, date
import os
import difflib
import subprocess
import requests
import shutil
import re
import google.generativeai as genai
from dotenv import load_dotenv
import markdown
import bson
import logging
import pymongo
import docx  # For DOCX file extraction
import PyPDF2  # For PDF file extraction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')  # Replace with your actual secret key

# Secure Cookie Configuration
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# MongoDB Configuration
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb+srv://jharshit61:New1212@cluster0.sydzy.mongodb.net/developerportal?retryWrites=true&w=majority")  # Replace with your actual MongoDB URI
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

mongo = PyMongo(app)

# Set Google Gemini API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # Ensure you have GEMINI_API_KEY set in .env

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Allowed extensions for file uploads (including PDFs, DOCs, and ZIPs)
ALLOWED_EXTENSIONS = {'py', 'html', 'pdf', 'doc', 'docx', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# User Model
class User(UserMixin):
    def __init__(self, user_id, username=None, email=None, role=None):
        self.id = str(user_id)  # Ensure the id is a string
        self.username = username
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    try:
        # Try to interpret user_id as an ObjectId
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    except (bson.errors.InvalidId, TypeError):
        # If invalid ObjectId, try to find by email
        user = mongo.db.users.find_one({"email": user_id})
    if user:
        return User(
            user_id=user['_id'],
            username=user.get('username'),
            email=user.get('email'),
            role=user.get('role')
        )
    return None

@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

def get_file_diff(file1_path, file2_path):
    """Compares two files and returns the differences."""
    try:
        with open(file1_path, 'r') as file1, open(file2_path, 'r') as file2:
            file1_lines = file1.readlines()
            file2_lines = file2.readlines()
        
        # Generate the diff
        diff = difflib.unified_diff(file1_lines, file2_lines, lineterm='')
        return '\n'.join(diff)
    except FileNotFoundError:
        return "One or both files not found."

# Function to generate a task breakdown using Google Generative AI
def generate_task_breakdown(task_name, deadline_days, content):
    """
    Generates a detailed task breakdown based on the task name, deadline, and specific content.
    """
    prompt = (
        f"You are an expert in educational content creation. Based on the following task and specific content, "
        f"create a detailed {deadline_days}-day plan to address these questions, case studies, and project descriptions.\n\n"
        f"Task: {task_name}\n\n"
        f"Content:\n{content}\n\n"
        f"Provide a step-by-step plan that breaks down the content into actionable tasks."
    )

    try:
        # Use Google Generative AI SDK for content generation
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        # Convert the generated text from Markdown to HTML
        markdown_text = response.text.strip()
        html_content = markdown.markdown(markdown_text)  # Convert to HTML
        
        return html_content

    except Exception as e:
        logger.error(f"Error generating task breakdown: {str(e)}")
        return f"Error generating plan: {str(e)}"

# Helper function to get user repositories
def get_user_repositories(user):
    """Fetches the repositories for the given user."""
    return mongo.db.repos.find({'owner': user.username})

# Helper functions for code checking
def check_python_code(file_path):
    try:
        # Explicitly pass ignore flags to Flake8
        ignore_errors = "E501,F401,W293,W391,E302,E305,E303,W292,W291,F811,F841"
        result = subprocess.run(['flake8', '--ignore=' + ignore_errors, file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return 'No issues found.'
        else:
            return f'Testing failed:<pre>{result.stdout.strip()}</pre>'
    except Exception as e:
        return f'Error checking Python code: {str(e)}'

def check_html_code(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace Jinja2 expressions with placeholders
        sanitized_content = re.sub(r'\{\{.*?\}\}', 'PLACEHOLDER', content)
        sanitized_content = re.sub(r'\{%.*?%\}', '', sanitized_content)
    
        # Send the sanitized HTML content to the W3C validator
        response = requests.post(
            'https://validator.w3.org/nu/',
            headers={'Content-Type': 'text/html; charset=utf-8'},
            data=sanitized_content,
            params={'out': 'json'}
        )
        result = response.json()
        if 'messages' in result and result['messages']:
            errors = '\n'.join([f"Error: {message['message']}" for message in result['messages'] if message['type'] == 'error'])
            if errors:
                return f'Testing failed:<pre>{errors}</pre>'
            else:
                return 'No issues found.'
        else:
            return 'No issues found.'
    except Exception as e:
        return f'HTML parsing error: {str(e)}'

def clean_diff(diff_lines):
    """
    Cleans up the diff by removing lines starting with '---', '+++', or '@@'.
    """
    cleaned_diff = []
    for line in diff_lines:
        if not (line.startswith('---') or line.startswith('+++') or line.startswith('@@')):
            cleaned_diff.append(line)
    return "\n".join(cleaned_diff)

def check_if_collaborator(user, repo):
    """
    Checks if the current user is a collaborator for the given repository.
    """
    return user.username in repo.get('collaborators', [])

# Helper function to convert repo IDs to strings
def convert_repo_ids_to_str(repos):
    for repo in repos:
        repo['_id'] = str(repo['_id'])
    return repos

# Context processor to make current_user available in templates
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# Function to extract questions from a .docx file
def extract_questions(file_path):
    """
    Extracts questions, case studies, and project descriptions from a .docx file.
    Assumes that each section starts with a numbered or titled format.
    """
    try:
        doc = docx.Document(file_path)
        content = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                content.append(text)
        return '\n'.join(content)
    except Exception as e:
        logger.error(f"Error extracting content from {file_path}: {str(e)}")
        return ""

# Function to extract questions from a PDF file
def extract_questions_from_pdf(file_path):
    """
    Extracts text from a PDF file.
    Assumes that questions, case studies, and project descriptions are properly formatted.
    """
    try:
        with open(file_path, 'rb') as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting content from {file_path}: {str(e)}")
        return ""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_username = request.form['email_or_username']
        password = request.form['password']

        # Find the user by email or username
        user = mongo.db.users.find_one({
            "$or": [
                {"email": email_or_username},
                {"username": email_or_username}
            ]
        })
        
        # Check if user exists and verify the password using hashed password check
        if user and check_password_hash(user['password'], password):
            login_user(User(
                user_id=str(user['_id']),  # Ensure it's a string
                username=user.get('username'),
                email=user.get('email'),
                role=user.get('role')
            ))
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'user')  # Default role is 'user'

        # Check if username or email exists
        if mongo.db.users.find_one({"$or": [{"username": username}, {"email": email}]}):
            flash('Username or email already exists', 'danger')
            return redirect(url_for('signup'))
        
        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Insert new user
        mongo.db.users.insert_one({
            'username': username,
            'name': username,  # Ensure 'name' field is also set
            'email': email,
            'password': hashed_password,
            'role': role
        })
        flash('Account created successfully', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

# Dashboard route
@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    user_data = mongo.db.users.find_one({"_id": ObjectId(current_user.id)})

    # Fetch tasks based on user role with sorting by deadline ascending
    if current_user.role == 'superuser':
        # Sort tasks by deadline in ascending order
        tasks = list(mongo.db.tasks.find().sort("deadline", pymongo.ASCENDING))

        # Convert task['_id'] to string and fetch assigned_user_name
        for task in tasks:
            task['_id'] = str(task['_id'])
            user_id = task.get('user_id')
            if user_id:
                assigned_user = mongo.db.users.find_one({"_id": user_id})
                if assigned_user:
                    assigned_user_name = assigned_user.get('username') or assigned_user.get('name', 'Unknown')
                else:
                    assigned_user_name = 'Unknown'
            else:
                assigned_user_name = 'Unassigned'
            task['assigned_user_name'] = assigned_user_name

            # Convert 'deadline' from string to datetime object
            if isinstance(task.get('deadline'), str):
                try:
                    task['deadline'] = datetime.strptime(task['deadline'], '%Y-%m-%d')
                except ValueError:
                    task['deadline'] = None  # Handle invalid date formats as needed

        # Fetch all users except the superuser for task assignment
        all_users = list(mongo.db.users.find({"role": {"$ne": "superuser"}}))

        # Fetch attendance records for all users
        attendance_records = list(mongo.db.attendance.find())
        # Convert 'user_id' to string in attendance_records and ensure 'date' is string
        for record in attendance_records:
            record['user_id'] = str(record['user_id'])
            if isinstance(record.get('date'), datetime):
                record['date'] = record['date'].strftime('%Y-%m-%d')
            else:
                # If date is already a string or another format, ensure it's in 'YYYY-MM-DD'
                try:
                    parsed_date = datetime.strptime(record['date'], '%Y-%m-%d')
                    record['date'] = parsed_date.strftime('%Y-%m-%d')
                except:
                    record['date'] = 'Unknown Date'

        # Fetch user information to map user_id to username
        users = mongo.db.users.find({"role": {"$ne": "superuser"}})
        user_info = {str(user['_id']): user['username'] for user in users}
    else:
        # Sort tasks by deadline in ascending order for regular users
        tasks = list(mongo.db.tasks.find({"user_id": ObjectId(current_user.id)}).sort("deadline", pymongo.ASCENDING))
        # Convert task['_id'] to string and convert 'deadline' to datetime
        for task in tasks:
            task['_id'] = str(task['_id'])
            if isinstance(task.get('deadline'), str):
                try:
                    task['deadline'] = datetime.strptime(task['deadline'], '%Y-%m-%d')
                except ValueError:
                    task['deadline'] = None  # Handle invalid date formats as needed

        all_users = None  # Regular users don't need all user data

        # Fetch attendance records for the current user
        attendance_records = list(mongo.db.attendance.find({"user_id": ObjectId(current_user.id)}))
        # Convert 'user_id' to string in attendance_records and ensure 'date' is string
        for record in attendance_records:
            record['user_id'] = str(record['user_id'])
            if isinstance(record.get('date'), datetime):
                record['date'] = record['date'].strftime('%Y-%m-%d')
            else:
                # If date is already a string or another format, ensure it's in 'YYYY-MM-DD'
                try:
                    parsed_date = datetime.strptime(record['date'], '%Y-%m-%d')
                    record['date'] = parsed_date.strftime('%Y-%m-%d')
                except:
                    record['date'] = 'Unknown Date'

        user_info = None  # Not needed for normal users

        # Check if there's an attendance record for today; if not, mark as 'Absent'
        today_str = date.today().strftime('%Y-%m-%d')
        today_attendance = mongo.db.attendance.find_one({"user_id": ObjectId(current_user.id), "date": today_str})
        if not today_attendance:
            mongo.db.attendance.insert_one({
                "user_id": ObjectId(current_user.id),
                "date": today_str,
                "status": "Absent",
                "percentage": 0.0
            })
            attendance_records.append({
                "user_id": str(current_user.id),
                "date": today_str,
                "status": "Absent",
                "percentage": 0.0
            })

    current_time = datetime.now()

    # Fetch user repositories
    user_repos_cursor = get_user_repositories(current_user)
    user_repos = list(user_repos_cursor)
    user_repos = convert_repo_ids_to_str(user_repos)  # Convert IDs to strings

    # Get the user's display name
    display_name = user_data.get('username') or user_data.get('name', current_user.username)

    # Fetch latest submission times for tasks
    submission_times = {}
    submitted_files = {}
    if current_user.role == 'superuser':
        # For superuser, get submission times and submitted files for all tasks
        for task in tasks:
            task_id_str = task['_id']
            user_id = task.get('user_id')
            if user_id:
                # Fetch the latest progress record
                progress = mongo.db.daily_progress.find_one(
                    {"user_id": ObjectId(user_id), "task_id": ObjectId(task_id_str)},
                    sort=[("submission_time", pymongo.DESCENDING)]
                )
                if progress and 'submission_time' in progress:
                    submission_times[task_id_str] = progress['submission_time']
                else:
                    submission_times[task_id_str] = None

                # Fetch all submitted files for this task by the assigned user
                submissions = list(mongo.db.daily_progress.find(
                    {"user_id": ObjectId(user_id), "task_id": ObjectId(task_id_str)},
                    {"submission_file": 1, "_id": 0}
                ))
                submitted_files[task_id_str] = [submission['submission_file'] for submission in submissions if 'submission_file' in submission]
            else:
                submission_times[task_id_str] = None
                submitted_files[task_id_str] = []
    else:
        # For normal users, get submission times and submitted files based on their own ID
        for task in tasks:
            task_id_str = task['_id']
            progress = mongo.db.daily_progress.find_one(
                {"user_id": ObjectId(current_user.id), "task_id": ObjectId(task_id_str)},
                sort=[("submission_time", pymongo.DESCENDING)]
            )
            if progress and 'submission_time' in progress:
                submission_times[task_id_str] = progress['submission_time']
            else:
                submission_times[task_id_str] = None

            # Fetch all submitted files for this task by the user
            submissions = list(mongo.db.daily_progress.find(
                {"user_id": ObjectId(current_user.id), "task_id": ObjectId(task_id_str)},
                {"submission_file": 1, "_id": 0}
            ))
            submitted_files[task_id_str] = [submission['submission_file'] for submission in submissions if 'submission_file' in submission]

    # Automatically update task status to 'completed' if total work is done
    for task in tasks:
        total_work = task.get('total_work', 0)
        if total_work > 0:
            # Calculate total work done
            total_done = sum([progress.get('work_done', 0) for progress in mongo.db.daily_progress.find({"task_id": ObjectId(task['_id'])})])
            if total_done >= total_work and task.get('status') != 'completed':
                mongo.db.tasks.update_one(
                    {"_id": ObjectId(task['_id'])},
                    {"$set": {"status": "completed"}}
                )
                task['status'] = 'completed'

    return render_template(
        'dashboard.html',
        name=display_name,
        tasks=tasks,
        current_time=current_time,
        users=all_users,
        repos=user_repos,
        attendance_records=attendance_records,
        submission_times=submission_times,
        submitted_files=submitted_files,
        user_info=user_info,
        is_superuser=(current_user.role == 'superuser')
    )

@app.route('/taskmasterhub')
@login_required
def taskmasterhub():
    return redirect(url_for('github_dashboard'))

@app.route('/create_task', methods=['POST'])
@login_required
def create_task():
    if current_user.role != "superuser":
        flash('You do not have permission to create tasks.', 'danger')
        return redirect(url_for('dashboard'))

    # Get the list of assigned users
    user_ids = request.form.getlist('assigned_user_id[]')

    # Other task details
    task_name = request.form['task_name']
    task_date = request.form['task_date']
    deadline_str = request.form['deadline']
    total_work = int(request.form['total_work'])
    daily_work_target = int(request.form['daily_work_target'])

    # Parse the deadline
    try:
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
        days_until_deadline = (deadline - datetime.now()).days
    except ValueError:
        flash('Invalid date format. Please enter a valid date (YYYY-MM-DD).', 'danger')
        return redirect(url_for('dashboard'))

    # Handle file uploads
    uploaded_files = request.files.getlist('task_files')

    # Extract content from uploaded DOCX and PDF files
    combined_content = ""
    for file in uploaded_files:
        if file.filename == '':
            continue
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', filename)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            file.save(temp_path)
            if filename.lower().endswith('.docx'):
                content = extract_questions(temp_path)
                combined_content += content + "\n"
            elif filename.lower().endswith('.pdf'):
                content = extract_questions_from_pdf(temp_path)
                combined_content += content + "\n"
            # Remove the temporary file after extraction
            os.remove(temp_path)
            logger.info(f'Extracted content from {filename}')

    # Call Google Generative AI to generate a task breakdown
    if combined_content:
        task_breakdown = generate_task_breakdown(task_name, days_until_deadline, combined_content)
    else:
        task_breakdown = "No specific content provided to generate a detailed task breakdown."

    # Function to create a task for a single user
    def create_task_for_user(user_id, task_details, files):
        file_paths = []  # Initialize inside the loop for each user
        task_id = mongo.db.tasks.insert_one(task_details).inserted_id
        task_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'task_files', str(task_id))
        os.makedirs(task_folder, exist_ok=True)

        if files:
            for file in files:
                if file.filename == '':
                    continue
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_rel_path = os.path.join(str(task_id), filename)
                    full_path = os.path.join(task_folder, filename)
                    file.save(full_path)
                    file_paths.append(file_rel_path)
                    logger.info(f'User {user_id}: Uploaded file {file_rel_path}')

        # Update the task with its own file paths and task breakdown
        mongo.db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {
                "$set": {
                    "file_paths": file_paths,
                    "task_breakdown": task_breakdown
                }
            }
        )
        logger.info(f'Task {task_id} for user {user_id} updated with file_paths: {file_paths}')

    # Common task details
    task_details_common = {
        "task_name": task_name,
        "task_date": task_date,
        "status": "pending",
        "submission_time": None,
        "deadline": deadline,
        "task_breakdown": task_breakdown,
        "total_work": total_work,
        "daily_work_target": daily_work_target,
        "file_paths": [],  # Initialize empty; will be set per user
        "user_id": None  # Placeholder; will be set per user
    }

    # Create tasks for all assigned users
    for user_id in user_ids:
        # Copy common task details and add user-specific info
        task_details = task_details_common.copy()
        task_details["user_id"] = ObjectId(user_id)

        # Create task and handle file uploads
        create_task_for_user(user_id, task_details, uploaded_files)

    flash('Task and files added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_task/<task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    # Remove file upload handling from this route
    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    new_status = request.form['status']

    deadline = task.get("deadline")
    if isinstance(deadline, str):
        deadline = datetime.strptime(deadline, '%Y-%m-%d')

    current_time = datetime.now()

    if new_status == "completed" and current_time > deadline:
        flash('You missed the deadline and cannot submit this task.', 'danger')
        return redirect(url_for('dashboard'))

    mongo.db.tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": {"status": new_status}}
    )

    flash('Task status updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_task/<task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    if current_user.role != "superuser":
        flash('You do not have permission to delete tasks.', 'danger')
        return redirect(url_for('dashboard'))

    mongo.db.tasks.delete_one({"_id": ObjectId(task_id)})
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    # Log out the user
    logout_user()
    
    # Clear the session to remove any stored flash messages
    session.clear()
    
    # Optionally, you can flash a logout success message
    flash('You have been logged out successfully.', 'success')
    
    # Redirect to the login page
    return redirect(url_for('login'))

# Attendance and Daily Progress Routes

def mark_attendance(user_id, date_value):
    """
    Marks attendance for a user based on the completion of all active tasks up to the given date.
    
    Parameters:
        user_id (str): The ObjectId string of the user.
        date_value (datetime.date or datetime.datetime): The date for which to mark attendance.
    """
    try:
        logger.info(f"Marking attendance for user_id: {user_id} on date: {date_value.strftime('%Y-%m-%d')}")

        # Ensure date_value is a datetime object
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            date_value = datetime.combine(date_value, datetime.min.time())
        
        date_str = date_value.strftime('%Y-%m-%d')
        
        # Fetch all active (not completed) tasks assigned to the user up to the current date
        tasks = list(mongo.db.tasks.find({
            "user_id": ObjectId(user_id),
            "status": {"$ne": "completed"},
            "task_date": {"$lte": date_str}  # Tasks assigned on or before the current date
        }))
        
        total_daily_target = 0
        total_work_done = 0
        
        for task in tasks:
            daily_target = task.get('daily_work_target', 0)
            total_daily_target += daily_target
            
            # Fetch all progress entries for the task on the given date
            progresses = mongo.db.daily_progress.find({
                "user_id": ObjectId(user_id),
                "task_id": task['_id'],
                "date": date_str
            })
            
            for progress in progresses:
                work_done = progress.get('work_done', 0)
                total_work_done += work_done
                logger.debug(f"Task ID: {task['_id']} - Work Done: {work_done}")
        
        # Calculate overall percentage
        if total_daily_target > 0:
            overall_percentage = (total_work_done / total_daily_target) * 100
        else:
            overall_percentage = 0
        
        # If there are no active tasks, automatically mark as "Present"
        if total_daily_target == 0:
            status = 'Present'
            overall_percentage = 100.0
            logger.info("No active tasks. Automatically marking as Present.")
        else:
            status = 'Present' if overall_percentage >= 70 else 'Absent'
            logger.info(f"Total Daily Target: {total_daily_target}, Total Work Done: {total_work_done}, Overall Percentage: {overall_percentage}, Status: {status}")
        
        # Update attendance record
        mongo.db.attendance.update_one(
            {"user_id": ObjectId(user_id), "date": date_str},
            {"$set": {"status": status, "percentage": round(overall_percentage, 2), "date": date_str}},
            upsert=True
        )
        logger.info(f"Attendance for user_id: {user_id} on date: {date_str} marked as {status} with {round(overall_percentage, 2)}%.")

    except Exception as e:
        logger.error(f"Error marking attendance for user {user_id} on {date_value}: {str(e)}")
        flash("An error occurred while marking attendance.", "danger")

def verify_answers_with_ai(file_path):
    # Placeholder function for AI verification
    # Implement your AI logic here
    # For now, we'll return a dummy result
    return "Verified"

@app.route('/submit_progress', methods=['GET', 'POST'])
@login_required
def submit_progress():
    if request.method == 'POST':
        task_id = request.form['task_id']
        work_done = int(request.form['work_done'])
        date_str = request.form['date']
        # Convert date string to datetime object
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format. Please select a valid date.', 'danger')
            return redirect(url_for('submit_progress'))

        # Fetch the task
        task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task:
            flash('Task not found', 'danger')
            return redirect(url_for('dashboard'))

        # Check if the task deadline has passed
        deadline = task.get('deadline')
        if isinstance(deadline, str):
            deadline = datetime.strptime(deadline, '%Y-%m-%d')

        if datetime.now() > deadline:
            flash('You cannot submit progress after the task deadline has passed.', 'danger')
            return redirect(url_for('submit_progress'))

        # Check if the task is assigned to the user
        if str(task.get('user_id')) != str(current_user.id):
            flash('You are not assigned to this task', 'danger')
            return redirect(url_for('dashboard'))

        daily_target = task.get('daily_work_target', 0)
        if work_done > daily_target:
            flash(f'Work done cannot exceed the daily target of {daily_target} units.', 'danger')
            return redirect(url_for('submit_progress'))

        # Handle file upload
        uploaded_file = request.files.get('submission_file')
        submission_time = datetime.now()
        submitted_file_path = None
        full_submitted_path = None

        if uploaded_file and uploaded_file.filename != '':
            filename = secure_filename(uploaded_file.filename)
            # Store submitted files under 'submitted_files/<task_id>/<filename>'
            submitted_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'submitted_files', str(task_id))
            os.makedirs(submitted_folder, exist_ok=True)
            submitted_file_path = os.path.join('submitted_files', str(task_id), filename)
            full_submitted_path = os.path.join(app.config['UPLOAD_FOLDER'], 'submitted_files', str(task_id), filename)
            uploaded_file.save(full_submitted_path)
        else:
            flash('Please upload your work file.', 'danger')
            return redirect(url_for('submit_progress'))

        # AI Verification (Placeholder)
        ai_result = verify_answers_with_ai(full_submitted_path)

        # Check if a progress entry already exists for this user, task, and date
        existing_progress = mongo.db.daily_progress.find_one({
            "user_id": ObjectId(current_user.id),
            "task_id": ObjectId(task_id),
            "date": date_str
        })

        if existing_progress:
            # Update the existing progress entry
            mongo.db.daily_progress.update_one(
                {"_id": existing_progress['_id']},
                {
                    "$set": {
                        "work_done": work_done,
                        "daily_target_met": work_done >= daily_target,
                        "submission_file": submitted_file_path,
                        "submission_time": submission_time,
                        "ai_verification_result": ai_result
                    }
                }
            )
            flash('Progress updated successfully.', 'success')
        else:
            # Insert a new daily progress entry
            mongo.db.daily_progress.insert_one(
                {
                    "user_id": ObjectId(current_user.id),
                    "task_id": ObjectId(task_id),
                    "work_done": work_done,
                    "daily_target_met": work_done >= daily_target,
                    "submission_file": submitted_file_path,
                    "submission_time": submission_time,
                    "ai_verification_result": ai_result,
                    "date": date_obj.strftime('%Y-%m-%d')  # Ensure the date is stored correctly
                }
            )
            flash('Progress submitted successfully.', 'success')

        # Calculate total work done by the user for this task on the given date
        total_done = sum([progress.get('work_done', 0) for progress in mongo.db.daily_progress.find({
            "user_id": ObjectId(current_user.id),
            "task_id": ObjectId(task_id),
            "date": date_obj.strftime('%Y-%m-%d')
        })])

        # Check if total work done meets or exceeds total_work
        if total_done >= task.get('total_work', 0) and task.get('status') != 'completed':
            mongo.db.tasks.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": "completed"}}
            )
            flash('Congratulations! Task completed.', 'success')
        else:
            flash('Progress submitted successfully.', 'success')

        # Mark attendance based on progress
        mark_attendance(current_user.id, date_obj)

        return redirect(url_for('dashboard'))

    # For GET request, fetch tasks assigned to the current user
    tasks = list(mongo.db.tasks.find({"user_id": ObjectId(current_user.id)}))  # Correct field name
    for task in tasks:
        task['_id'] = str(task['_id'])
        if isinstance(task.get('deadline'), datetime):
            task['deadline'] = task['deadline'].strftime('%Y-%m-%d')
    current_time = datetime.now()
    
    # Log the fetched tasks
    logger.info(f"User {current_user.username} has {len(tasks)} assigned tasks.")

    return render_template('submit_progress.html', tasks=tasks, current_time=current_time)

@app.route('/edit_attendance/<user_id>/<date>', methods=['POST'])
@login_required
def edit_attendance(user_id, date):
    if current_user.role != "superuser":
        flash("You do not have permission to edit attendance.", "danger")
        return redirect(url_for('dashboard'))
    
    # Get the status from the form (e.g., 'Present', 'Absent')
    status = request.form.get('status')  # e.g., 'Present', 'Absent'
    
    # Get and validate the percentage value
    try:
        percentage_str = request.form.get('percentage', '0')  # Default to '0' if no value is provided
        percentage = float(percentage_str) if percentage_str else 0.0
    except ValueError:
        percentage = 0.0  # Handle cases where the input is invalid
    
    # Update the attendance record in MongoDB
    mongo.db.attendance.update_one(
        {"user_id": ObjectId(user_id), "date": date},
        {"$set": {"status": status, "percentage": percentage}}
    )
    
    flash('Attendance updated successfully.', 'success')
    return redirect(url_for('attendance'))

@app.route('/delete_attendance/<user_id>/<date>', methods=['POST'])
@login_required
def delete_attendance(user_id, date):
    if current_user.role != "superuser":
        flash("You do not have permission to delete attendance.", "danger")
        return redirect(url_for('dashboard'))
    
    # Delete attendance record
    mongo.db.attendance.delete_one({"user_id": ObjectId(user_id), "date": date})
    
    flash('Attendance deleted successfully.', 'success')
    return redirect(url_for('attendance'))

@app.route('/attendance')
@login_required
def attendance():
    try:
        if current_user.role == 'superuser':
            # Fetch attendance records for all users
            attendance_records = list(mongo.db.attendance.find())
            # Fetch user information to map user_id to username
            users = mongo.db.users.find({"role": {"$ne": "superuser"}})
            user_info = {str(user['_id']): user['username'] for user in users}
            
            # Convert 'user_id' to string and 'date' to datetime object
            for record in attendance_records:
                record['user_id'] = str(record['user_id'])
                
                if isinstance(record.get('date'), str):
                    try:
                        record['date'] = datetime.strptime(record['date'], '%Y-%m-%d')
                    except ValueError:
                        logger.error(f"Invalid date format for record ID {record.get('_id')}: {record.get('date')}")
                        record['date'] = None  # Handle invalid date formats as needed
                elif isinstance(record.get('date'), datetime):
                    # If already a datetime object, no action needed
                    pass
                else:
                    # Handle unexpected types
                    logger.warning(f"Unexpected date type for record ID {record.get('_id')}: {type(record.get('date'))}")
                    record['date'] = None  # or handle as needed

            return render_template('attendance.html', attendance_records=attendance_records, user_info=user_info, is_superuser=True)
        else:
            # Fetch attendance records for the current user only
            attendance_records = list(mongo.db.attendance.find({"user_id": ObjectId(current_user.id)}))
            
            # Convert 'user_id' to string and 'date' to datetime object
            for record in attendance_records:
                record['user_id'] = str(record['user_id'])
                
                if isinstance(record.get('date'), str):
                    try:
                        record['date'] = datetime.strptime(record['date'], '%Y-%m-%d')
                    except ValueError:
                        logger.error(f"Invalid date format for record ID {record.get('_id')}: {record.get('date')}")
                        record['date'] = None  # Handle invalid date formats as needed
                elif isinstance(record.get('date'), datetime):
                    # If already a datetime object, no action needed
                    pass
                else:
                    # Handle unexpected types
                    logger.warning(f"Unexpected date type for record ID {record.get('_id')}: {type(record.get('date'))}")
                    record['date'] = None  # or handle as needed

            return render_template('attendance.html', attendance_records=attendance_records, is_superuser=False)
    
    except Exception as e:
        logger.exception("Error fetching attendance records.")
        flash("An error occurred while fetching attendance records.", "danger")
        return redirect(url_for('dashboard'))

# Route to download task files
@app.route('/download_task_file/<path:filename>')
@login_required
def download_task_file(filename):
    # filename should be in the format 'task_id/filename.ext'
    task_id, file_name = os.path.split(filename)

    # Fetch the task
    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Check permissions
    if current_user.role != 'superuser' and str(task['user_id']) != str(current_user.id):
        flash('You do not have permission to access this file.', 'danger')
        return redirect(url_for('dashboard'))

    # Construct the full file path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'task_files', task_id, file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        flash('File does not exist.', 'danger')
        return redirect(url_for('dashboard'))

    directory = os.path.join(app.config['UPLOAD_FOLDER'], 'task_files', task_id)
    return send_from_directory(directory, file_name, as_attachment=True)

# Route to download submitted files (by superuser or owner)
@app.route('/download_submitted_file/<path:filename>')
@login_required
def download_submitted_file(filename):
    # Ensure the filename is properly split and normalized
    filename = os.path.normpath(filename)  # This normalizes path separators (handles both '/' and '\')
    
    # filename should be in the format 'submitted_files/task_id/filename.ext'
    parts = filename.split(os.sep)  # Split by the OS path separator (works on both Windows and Unix)
    if len(parts) < 3:
        flash('Invalid file path.', 'danger')
        return redirect(url_for('dashboard'))
    
    submitted_folder, task_id, file_name = parts[0], parts[1], parts[2]
    
    # Fetch the task
    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Check permissions
    if current_user.role != 'superuser' and str(task['user_id']) != str(current_user.id):
        flash('You do not have permission to access this file.', 'danger')
        return redirect(url_for('dashboard'))

    # Construct the full file path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'submitted_files', task_id, file_name)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        flash('File does not exist.', 'danger')
        return redirect(url_for('dashboard'))

    # Serve the file for download
    return send_from_directory(os.path.dirname(file_path), file_name, as_attachment=True)

# GitHub Clone Routes

# Index route (GitHub dashboard)
@app.route('/github', methods=['GET'])
@login_required
def github_dashboard():
    # Fetch user repositories
    user_repos_cursor = get_user_repositories(current_user)
    user_repos = list(user_repos_cursor)
    user_repos = convert_repo_ids_to_str(user_repos)  # Convert IDs to strings

    # Fetch explore repositories (owned by others)
    explore_repos_cursor = mongo.db.repos.find({'owner': {'$ne': current_user.username}})
    explore_repos = list(explore_repos_cursor)
    explore_repos = convert_repo_ids_to_str(explore_repos)  # Convert IDs to strings

    return render_template('github/index.html', repos=user_repos, explore_repos=explore_repos)

# Create repository route
@app.route('/github/repo/create', methods=['GET', 'POST'])
@login_required
def create_repo():
    if request.method == 'POST':
        repo_name = request.form.get('repository_name')
        is_private = 'private' in request.form

        if not repo_name:
            flash('Repository name is required', 'danger')
            return redirect(url_for('create_repo'))

        # Check if a repository with the same name exists for the user
        if mongo.db.repos.find_one({'name': repo_name, 'owner': current_user.username}):
            flash('Repository with this name already exists!', 'danger')
            return redirect(url_for('create_repo'))

        # Insert new repository into MongoDB
        mongo.db.repos.insert_one({
            'name': repo_name,
            'owner': current_user.username,
            'is_private': is_private,
            'commits': [],
            'collaborators': [],  # Start with an empty list
            'files': [],
            'branches': ['main'],
            'issues': [],
            'timestamp': datetime.now()
        })

        flash('Repository created successfully!', 'success')
        return redirect(url_for('github_dashboard'))

    return render_template('github/create_repository.html')

# View repository route
@app.route('/github/repo/<repo_id>', methods=['GET', 'POST'])
@login_required
def repo(repo_id):
    # Fetch the repository from MongoDB
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id)})

    if not repo:
        flash('Repository not found', 'danger')
        return redirect(url_for('github_dashboard'))

    file_contents = []  # This will hold the content of all uploaded files
    files = []  # Initialize files as an empty list in case the repository has no files yet
    is_owner = current_user.username == repo['owner']  # Check if the current user is the repository owner
    is_collaborator = check_if_collaborator(current_user, repo) or is_owner  # Check collaborator status or ownership

    if request.method == 'POST':
        # Handle multiple file uploads
        uploaded_files = request.files.getlist('files')
        commit_message = request.form.get('commit_message')

        if uploaded_files and commit_message:
            for file in uploaded_files:
                if file.filename == '':
                    continue
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)

                    # Read the file content if it's a text file
                    if file.filename.endswith(('py', 'html')):
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                        except Exception as e:
                            file_content = f'Error reading file: {str(e)}'
                    else:
                        file_content = None  # We won't display content for non-text files

                    # Store file content and details in the 'files' array in MongoDB
                    mongo.db.repos.update_one({"_id": ObjectId(repo_id)}, {
                        "$push": {
                            "files": {
                                'filename': filename,
                                'filepath': filepath,
                                'commit_message': commit_message,
                                'user': current_user.username,
                                'file_content': file_content,  # Store content if it's a text file
                                'timestamp': datetime.now(),
                            },
                            "commits": {
                                'commit_message': commit_message,
                                'user': current_user.username,
                                'timestamp': datetime.now(),
                            }
                        }
                    })

                    if file_content:
                        file_contents.append(file_content)

            flash('Files uploaded and committed!', 'success')
        else:
            flash('Invalid file type or missing commit message.', 'danger')

    # Fetch the files from the database to display them
    if 'files' in repo:  # Ensure 'files' key exists in the repo document
        files = repo['files']

    return render_template('github/repo.html', repo=repo, files=files, file_contents=file_contents, is_collaborator=is_collaborator, is_owner=is_owner)

# Route to view file content
@app.route('/github/repo/<repo_id>/view/<file_name>', methods=['GET'])
@login_required
def view_file(repo_id, file_name):
    # Fetch the repository and file content
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id)})
    file = next((f for f in repo['files'] if f['filename'] == file_name), None)

    if not file:
        flash('File not found', 'danger')
        return redirect(url_for('repo', repo_id=repo_id))

    file_content = file.get('file_content', 'No content available')
    is_owner = current_user.username == repo['owner']  # Check if the current user is the repository owner
    is_collaborator = check_if_collaborator(current_user, repo) or is_owner

    return render_template('github/view_file.html', file_name=file_name, file_content=file_content, is_collaborator=is_collaborator)

# Route to edit file content
@app.route('/github/repo/<repo_id>/edit/<file_name>', methods=['GET', 'POST'])
@login_required
def edit_file(repo_id, file_name):
    # Fetch the repository and file content
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id)})
    file = next((f for f in repo['files'] if f['filename'] == file_name), None)

    if not file:
        flash('File not found', 'danger')
        return redirect(url_for('repo', repo_id=repo_id))

    # Check if the user is a collaborator or the owner
    is_owner = current_user.username == repo['owner']
    if not is_owner and not check_if_collaborator(current_user, repo):
        flash('You do not have permission to edit this file', 'danger')
        return redirect(url_for('view_file', repo_id=repo_id, file_name=file_name))

    if request.method == 'POST':
        # Get the updated file content from the form
        updated_content = request.form.get('file_content')
        old_content = file['file_content']

        if not updated_content:
            flash('Content cannot be empty!', 'danger')
            return render_template('github/edit_file.html', file_name=file_name, file_content=old_content)

        # Generate the diff between the old and new content
        if old_content is not None:
            diff_lines = list(difflib.unified_diff(old_content.splitlines(), updated_content.splitlines(), fromfile='before', tofile='after'))
            diff = clean_diff(diff_lines)  # Clean the diff here
        else:
            diff = "Initial commit."

        # Update the file content in MongoDB
        mongo.db.repos.update_one(
            {"_id": ObjectId(repo_id), "files.filename": file_name},
            {
                "$set": {"files.$.file_content": updated_content},
                "$push": {
                    "commits": {
                        'commit_message': f"Updated file: {file_name}",
                        'user': current_user.username,
                        'timestamp': datetime.now(),
                        'diff': diff  # Store the cleaned diff in the commit
                    }
                }
            }
        )

        flash('File updated successfully!', 'success')
        return redirect(url_for('repo', repo_id=repo_id))

    return render_template('github/edit_file.html', file_name=file_name, file_content=file['file_content'])

# Route to add a collaborator
@app.route('/github/repo/<repo_id>/add_collaborator', methods=['POST'])
@login_required
def add_collaborator(repo_id):
    collaborator_username = request.form['collaborator_username']

    # Check if the collaborator exists in the 'users' collection
    collaborator = mongo.db.users.find_one({"username": collaborator_username})

    if not collaborator:
        flash('User not found. Please ensure the user has signed up.', 'danger')
        return redirect(url_for('repo', repo_id=repo_id))

    # Check if the collaborator is already part of the repository
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id)})
    if collaborator_username in repo.get('collaborators', []):
        flash('This user is already a collaborator.', 'warning')
        return redirect(url_for('repo', repo_id=repo_id))

    # Add the collaborator to the 'collaborators' array in the repo
    result = mongo.db.repos.update_one(
        {"_id": ObjectId(repo_id)},
        {"$addToSet": {"collaborators": collaborator_username}}  # Use $addToSet to avoid duplicates
    )

    if result.modified_count == 1:
        flash('Collaborator added successfully.', 'success')
    else:
        flash('Failed to add collaborator. Please try again.', 'danger')

    return redirect(url_for('repo', repo_id=repo_id))

# Route to view commit history for a repository
@app.route('/github/repo/<repo_id>/history')
@login_required
def commit_history(repo_id):
    # Fetch the repository from MongoDB
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id)})

    if not repo:
        flash('Repository not found', 'danger')
        return redirect(url_for('github_dashboard'))

    # Fetch all the commits for this repository
    commits = repo.get('commits', [])

    return render_template('github/commit_history.html', repo=repo, commits=commits)

# Route to handle code testing (only HTML and Python)
@app.route('/github/repo/<repo_id>/test', methods=['POST'])
@login_required
def test_code(repo_id):
    # Fetch the repository from MongoDB
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id)})

    if not repo:
        flash('Repository not found', 'danger')
        return redirect(url_for('github_dashboard'))

    # Check if the user is a collaborator or the owner
    is_owner = current_user.username == repo['owner']
    if not is_owner and not check_if_collaborator(current_user, repo):
        flash('You do not have permission to test code in this repository', 'danger')
        return redirect(url_for('repo', repo_id=repo_id))

    # Handle file uploads for testing
    uploaded_files = request.files.getlist('test_files')
    if not uploaded_files:
        flash('No files uploaded for testing.', 'danger')
        return redirect(url_for('repo', repo_id=repo_id))

    results = []
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', current_user.username)
    
    # Clean the temporary directory before saving new files
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    for file in uploaded_files:
        filename = secure_filename(file.filename)
        if '.' not in filename:
            results.append({'filename': filename, 'status': 'Invalid file name'})
            continue
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            results.append({'filename': filename, 'status': 'Unsupported file type'})
            continue

        # Save the uploaded file to a temporary location
        temp_path = os.path.join(temp_dir, filename)
        try:
            file.save(temp_path)
        except Exception as e:
            results.append({'filename': filename, 'status': f'Failed to save file: {str(e)}'})
            continue

        # Perform code checking based on file type
        if file_ext == 'py':
            result = check_python_code(temp_path)
        elif file_ext == 'html':
            result = check_html_code(temp_path)
        else:
            result = 'No checker available for this file type.'

        results.append({'filename': filename, 'status': result})

    # Clean up the temporary directory
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {str(e)}")

    return render_template('github/test_results.html', results=results, repo_id=repo_id)

# Route to delete a repository
@app.route('/github/repo/<repo_id>/delete', methods=['POST'])
@login_required
def delete_repo(repo_id):
    # Find the repository owned by the current user
    repo = mongo.db.repos.find_one({"_id": ObjectId(repo_id), "owner": current_user.username})
    
    # If the repository exists and is owned by the current user, delete it
    if repo:
        mongo.db.repos.delete_one({"_id": ObjectId(repo_id)})
        flash('Repository deleted successfully.', 'success')
    else:
        flash('Repository not found or you do not have permission to delete it.', 'danger')
    
    return redirect(url_for('my_repositories'))

# Explore repositories route
@app.route('/github/explore')
@login_required
def explore_repositories():
    repos_cursor = mongo.db.repos.find({'owner': {'$ne': current_user.username}})
    repos = list(repos_cursor)
    repos = convert_repo_ids_to_str(repos)  # Convert IDs to strings
    return render_template('github/explore.html', repos=repos)

# Profile route
@app.route('/github/profile')
@login_required
def profile():
    user_repos = get_user_repositories(current_user)
    user_repos = list(user_repos)
    user_repos = convert_repo_ids_to_str(user_repos)  # Convert IDs to strings
    user_info = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    return render_template('github/profile.html', user_repos=user_repos, user_info=user_info)

# My repositories route
@app.route('/github/my_repositories')
@login_required
def my_repositories():
    # Fetch the user's repositories from the database
    user_repos_cursor = get_user_repositories(current_user)
    user_repos = list(user_repos_cursor)  # Convert cursor to list
    user_repos = convert_repo_ids_to_str(user_repos)  # Convert IDs to strings
    return render_template('github/my_repositories.html', repos=user_repos)

# Custom error handler for 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, port=5001)







