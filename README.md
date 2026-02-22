# Promtx Studio - AI Video Editor

Promtx Studio is a powerful, AI-driven video editing application that allows you to generate, edit, and transform videos using simple natural language prompts. Powered by Google Gemini and Veo, it handles everything from captioning to background removal and video generation.

## 🚀 Features

- **Text-to-Video Generation**: Create stunning videos using Google Veo.
- **AI Captions**: Automatically generate and add subtitles in multiple languages.
- **Watermark Removal**: Cleanly remove watermarks using AI-powered healing.
- **Background Removal**: Strip backgrounds from videos effortlessly.
- **Smart Trimming**: Cut silences or specific time ranges using natural language.
- **Video Transformation**: Resize for Shorts/Reels (9:16) or YouTube (16:9), adjust speed, and extract audio.
- **Summarization**: Get deep content analysis and summaries of your videos.

## 🛠️ Installation

### Prerequisites

- Python 3.10+
- FFmpeg (system dependency)
- Google Gemini API Key

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dhairyabh/Promtx-Studio.git
   cd Promtx-Studio
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables:**
   Create a `.env` file in the root directory and add your Gemini API Key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

5. **Run the application:**
   ```bash
   uvicorn main:app --reload
   ```
   Access the UI at `http://localhost:8000`

## 🐳 Docker Setup

If you have Docker installed, you can run the entire studio without worrying about system dependencies:

1. **Build the image:**
   ```bash
   docker build -t promtx-studio .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8000:8000 -e GEMINI_API_KEY=your_api_key_here promtx-studio
   ```

## ☁️ Deployment on Render

To deploy Promtx Studio on [Render](https://render.com):

1. **Connect your GitHub repository** to Render.
2. **Create a new Web Service**.
3. **Runtime**: Select `Docker`.
4. **Environment Variables**: Add `GEMINI_API_KEY`.
5. **Plan**: This project requires a significant amount of RAM for AI processing (Whisper/Rembg). A starter plan or higher is recommended.

## 🔒 Security Note

**Never** commit your `.env` file or hardcode your API keys. This project uses environment variables for security. The `uploads/` and `outputs/` folders are ignored by default.

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
