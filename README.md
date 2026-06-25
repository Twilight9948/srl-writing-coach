# SRL Writing Coach

A polished AI-powered writing coach designed to support English writing learning through the lens of Self-Regulated Learning (SRL).

## Project Overview
This project combines conversational AI, writing pedagogy, and a friendly user interface to help students move through a structured writing process:

1. Plan their writing goals
2. Draft their ideas
3. Evaluate their work with feedback or scoring
4. Reflect on their learning journey

The app is designed to be supportive, encouraging, and practical rather than simply giving answers.

## Why this project matters
Many students struggle not only with writing itself, but also with knowing how to organize ideas, revise, and reflect on their progress. This app aims to reduce that barrier by guiding learners step by step.

## Core Features
- Structured SRL workflow: Plan → Draft → Evaluate → Interact
- AI coaching for writing support and self-monitoring
- Rubric-based evaluation for CET, IELTS, TOEFL, and creative writing
- Mobile-friendly and visually refined UI
- Local session saving and optional Supabase logging

## Tech Stack
- Python
- Streamlit
- OpenAI-compatible API (DeepSeek)
- Requests
- JSON / local file storage

## Project Structure
- `srl_coach_ai.py` — main application
- `requirements.txt` — Python dependencies
- `README.md` — project guide and deployment instructions
- `.gitignore` — files excluded from GitHub

## How to Run Locally

### 1. Install Python
Make sure Python 3 is installed on your system.

### 2. Open the project folder in Terminal
```bash
cd /path/to/your/project
```

### 3. Create a virtual environment
```bash
python -m venv .venv
```

Activate it:

On Mac/Linux:
```bash
source .venv/bin/activate
```

On Windows:
```bash
.venv\Scripts\activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Start the app
```bash
streamlit run srl_coach_ai.py
```

Then open the local URL shown in the terminal.

## How to Deploy on Streamlit Cloud

### 1. Push the project to GitHub
If you are new to GitHub, create an account first at https://github.com.

Then run:
```bash
git init
git add .
git commit -m "Initial commit"
```

Create a new repository on GitHub, then connect it:
```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git
git push -u origin main
```

### 2. Deploy on Streamlit Cloud
1. Go to https://streamlit.io/cloud
2. Sign in with GitHub
3. Click "New app"
4. Select your repository
5. Set the main file path to:
```text
srl_coach_ai.py
```
6. Add this secret:
```text
DEEPSEEK_API_KEY = your_deepseek_api_key
```

### 3. Launch the app
After deployment, Streamlit will give you a public URL.

## Important Notes
- The AI features require a valid DeepSeek API key.
- If the API key is missing, the app will display a friendly message instead of failing silently.
- Local data is saved under the `srl_writing_data` folder.

## Future Improvements
Possible next steps include:
- adding screenshots and a demo GIF
- improving analytics and user progress tracking
- supporting more writing genres and learning modes
- adding multilingual support

## Acknowledgments
This project was built as a practical AI-assisted learning tool focused on writing practice, reflection, and student growth.
