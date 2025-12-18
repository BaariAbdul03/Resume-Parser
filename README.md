# 🧠 Resume Parser with ATS Scoring and Skill Search

A smart, user-friendly Resume Parser web application that extracts key candidate information from uploaded resumes, evaluates their ATS (Applicant Tracking System) score, and allows sorting and filtering based on skills. Built with HTML, CSS, JavaScript, and Python (Flask) for a seamless full-stack experience.

## 🌐 Live Demo

[Click here to view the live app](https://resume-parser-gdhd.onrender.com)

---

## 🚀 Features

- 📥 **Upload Multiple Resumes** – Drag-and-drop or select multiple PDF resumes for batch parsing.
- 🧠 **Resume Parsing** – Automatically extracts name, email, phone, skills, experience, and more using NLP techniques.
- 📊 **ATS Score Calculation** – Evaluates resumes based on keyword relevance and formatting.
- 🧹 **Missing Field Handling** – Leaves fields like email or skills empty if not found instead of crashing or faking data.
- 🔍 **Skill-Based Search** – Instantly filter resumes by specific technical or soft skills.
- 🔢 **ATS Score Sorting** – Sort resumes in descending order based on ATS scores for easy comparison.
- 📱 **Responsive UI** – Clean and intuitive layout for both desktop and mobile devices.

---

## 🛠️ Tech Stack

### Frontend:
- HTML5, CSS3
- Vanilla JavaScript (no frameworks)
- Dynamic DOM rendering and event handling

### Backend:
- Python 3.x
- Flask (for API and resume parsing)
- `pdfplumber`, `PyMuPDF`, `re`, and NLP libraries (like spaCy or similar)

---

## 📁 Folder Structure

```
resume-parser/
│
├── static/
│   ├── css/
│   └── js/
├── templates/
│   └── index.html
├── uploads/
│   └── [temporary uploaded resumes]
├── app.py
├── parser.py
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup & Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-username/resume-parser.git
cd resume-parser
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the Flask app**
```bash
python app.py
```

4. **Open in browser**
```
http://localhost:5000
```


## 🧪 Upcoming Improvements

- 🗂️ Export parsed data to CSV or Excel
- 🧠 AI-based keyword match scoring (Job-Resume fit)
- 🔐 User authentication and dashboard
- 📦 Resume parser API for third-party integration

---


## 📄 License

This project is open-source under the [MIT License](LICENSE).

---

> ✨ Building smarter hiring tools, one resume at a time.
