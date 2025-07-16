live: [https://ai-notes.streamlit.app]
# AI Content Calendar Creator

A Streamlit application that generates a 7-day content calendar using AI. The application uses the Mistral-7B-Instruct model through OpenRouter to create personalized content strategies.

## Features

- Research industry trends and topics
- Generate a 7-day content strategy
- Create detailed content briefs
- Export results as JSON
- User-friendly interface

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file with your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_api_key_here
   SITE_URL=http://localhost:8501
   SITE_NAME=Content Calendar Creator
   ```

## Usage

1. Run the application:
   ```bash
   streamlit run app.py
   ```
2. Open your browser and go to `http://localhost:8501`
3. Enter your:
   - Industry/Niche
   - Target Audience
   - Content Goals
4. Click "Generate 7-Day Content Calendar"

## Project Structure

```
.
├── .env                # Environment variables
├── .env.example        # Example environment file
├── app.py             # Main application code
├── requirements.txt    # Project dependencies
└── README.md          # Documentation
```

## Dependencies

- streamlit
- python-dotenv
- requests
- urllib3

## License

MIT License 
