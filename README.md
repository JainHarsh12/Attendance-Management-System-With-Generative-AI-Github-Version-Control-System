# 🚀 **TaskMasterHub** - A Comprehensive AI-Powered Task Management and Collaboration Platform  

Welcome to **TaskMasterHub**, a cutting-edge platform designed for streamlined task management, collaboration, and productivity, leveraging the power of **Google Gemini AI**. This project is a perfect blend of traditional web application frameworks and next-gen generative AI capabilities.

---

## 📌 **Key Features**
### 🌟 **AI-Powered Task Breakdown**
- **Generative AI Integration**: Utilizes **Google Gemini LLM** to generate detailed task plans from uploaded documents (PDF, DOCX) or text inputs.
- **Custom Prompts**: Transforms user inputs like task names, deadlines, and content into actionable, step-by-step plans.
- **Markdown to HTML Conversion**: Ensures AI-generated plans are rendered beautifully for seamless visualization.

- ![image](https://github.com/user-attachments/assets/d47d38b9-50da-43a9-90f0-5e80465a2880)


### 📋 **Task Management**
- **User Roles**: Supports both **superuser** (admin) and regular user functionalities for robust task assignment and monitoring.
- **Dynamic Deadlines**: Automatically sorts tasks by deadlines and sends reminders for overdue tasks.
- **Progress Tracking**: Tracks daily work done by users and adjusts task statuses dynamically.

### 💡 **Attendance Automation**
- Attendance marked based on **task completion percentage** using a **70% threshold** rule.
- Automated **"Present"** marking for users with completed or no tasks.

### 🧑‍💻 **Collaboration Tools**
- **GitHub-Inspired Repo Management**: Create, upload, and test files with robust commit management.
- **Collaborator Access**: Manage repository collaborators for streamlined teamwork.
- **Code Testing**: Integrated **HTML validation** via W3C and **Python static analysis** with Flake8.

### 🔎 **File Handling**
- **Multi-Format Support**: Handles **PDF, DOCX, HTML, Python scripts**, and ZIP files for tasks and repositories.
- **Automated Content Extraction**: Extracts questions, cases, and project descriptions from uploaded documents.

---

## 🌌 **Generative AI: The Heart of TaskMasterHub**

The core innovation of **TaskMasterHub** lies in its integration with **Google Gemini AI**, a large language model designed for generative tasks. Here's how it transforms the platform:

### **1️⃣ Task Breakdown**
When a superuser uploads educational or project materials:
- **Custom Prompting**: The task details, deadlines, and uploaded content are fed into the **Gemini LLM**.
- **Step-by-Step Plans**: Gemini returns a structured plan breaking down the content into manageable daily tasks.
- **Adaptive Responses**: Plans are tailored dynamically based on the number of days left until the deadline.

#### **Example AI Prompt:**
```plaintext
"You are an expert in educational content creation. Based on the following task and specific content, create a detailed 7-day plan to address the case studies and questions provided. 

Task: 'AI Fundamentals'
Deadline: 7 days
Content: (Extracted content from uploaded documents)
Provide a step-by-step plan that breaks down the content into actionable tasks."


2️⃣ Chatbot Assistance
Role-Based Insights: Gemini AI dynamically generates responses to user queries based on their role (e.g., admin, regular user).
Task Queries: Provides instant information on deadlines, overdue tasks, and task summaries.
Natural Language Processing: Detects intent and provides precise responses (e.g., "What are the deadlines for my tasks?").

![image](https://github.com/user-attachments/assets/0eac49ba-4065-4f3f-a7f9-7429d4761875)


🔧 Technology Stack
Backend
Flask: Lightweight Python framework for RESTful APIs and user authentication.
Flask-PyMongo: For seamless MongoDB integration.
Google Generative AI (Gemini): Core LLM for task automation and chatbot functionalities.

Frontend
HTML/CSS & Jinja2: Dynamic templates for rendering user-specific dashboards.
Streamlit: Optional frontend for generative AI visualization.

Database
MongoDB Atlas: Cloud-hosted database for scalability.
Additional Libraries
PyPDF2 & docx: For file parsing and content extraction.
Flake8 & W3C Validator: Code quality checks and testing.
dotenv: Secure environment variable handling.

⚙️ How It Works
User Authentication: Secure login and role-based access via Flask-Login.
Task Creation:
Admin uploads files or provides task content.
AI processes inputs and generates a structured plan.

Progress Submission:
Users submit their daily work with attached files.
Tasks are dynamically updated based on submission data.

Chatbot Assistance:
Users query the AI-powered assistant for task insights.

GitHub Repository:
Users manage repositories, upload files, and view commit histories.

🌟 Why TaskMasterXHub Stands Out
Generative AI-Powered Productivity: The seamless integration of Google Gemini LLM provides unparalleled task automation.
Comprehensive Ecosystem: From task management to GitHub-style repository handling, it's all in one place.
Real-World Use Cases: Ideal for educators, project managers, and collaborative teams.

🏆 Acknowledgments
This project would not have been possible without the support of:

Google Generative AI for task breakdown and chatbot functionalities.
MongoDB Atlas for seamless database integration.
