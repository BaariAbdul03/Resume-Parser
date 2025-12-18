# 🧠 AI-Powered Universal Resume Parser

A next-generation Resume Parser that moves beyond simple keyword counting. This application uses **Large Language Models (Google Gemini 2.5 Flash)** to perform semantic analysis, auto-detect job roles, and evaluate candidates using a strict **"Gap Analysis"** scoring protocol.

## 🌐 Live Demo

[Click here to view the live app](https://resume-parser-gdhd.onrender.com)

---

### 🚀 Key Features

* **🤖 AI-Driven Semantic Analysis** – Uses Gemini 1.5 Flash to understand context (e.g., recognizing that "ReactJS" and "React.js" are the same, or that "Principal Engineer" implies leadership).
* **🎯 Universal Role Detection** – Automatically infers the candidate's target role (e.g., "Full Stack Dev", "Digital Marketer") from the resume content if no Job Description is provided.
* **⚖️ Strict "Gap Analysis" Scoring** – Unlike traditional ATS that *adds* points for keywords, this system starts at **100** and *deducts* points for:
    * **Critical Skill Gaps (-25 pts):** Missing foundational skills (e.g., SQL for a Backend Dev).
    * **Experience Gaps (-10 pts):** Vague bullet points lacking quantifiable metrics.
    * **Formatting Issues (-5 pts):** Messy layouts or missing contact info.
* **📄 PDF Intelligence** – Utilizes `pdfplumber` to accurately extract text from complex, multi-column resume layouts.
* **🎨 Glassmorphism UI** – A clean, modern, and responsive user interface.

---

### 🛠️ Tech Stack

**Frontend:**
* HTML5, CSS3 (Custom Glassmorphism Design)
* Vanilla JavaScript (Fetch API for asynchronous data handling)

**Backend:**
* **Python 3.10+**
* **Flask** (Micro-web framework)
* **Google Gemini API (1.5 Flash)** (The intelligence engine)
* **pdfplumber** (For robust PDF text extraction)

**Deployment:**
* **Render** (Cloud Hosting)
* **Gunicorn** (Production Server)

---

## ⚙️ Setup & Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-username/resume-parser.git
cd resume-parser
```

2. **Create a Virtual Environment**
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up Environment Variables Create a .env file in the root directory and add your Google Gemini API Key:**
```
GEMINI_API_KEY=your_actual_api_key_here
```

5. **Run the Application**
```
python app.py
```


## 🧪 Upcoming Improvements

- 🗂️ Export parsed data to CSV or Excel
- 🔐 User authentication and dashboard
- 📦 Resume parser API for third-party integration

---


## 📄 License

This project is open-source under the [MIT License](LICENSE).

---

> ✨ Building smarter hiring tools, one resume at a time.
