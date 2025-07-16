# Reddit Persona Generator

**Summary**: The Reddit Persona Generator is a Python tool that creates detailed, privacy-focused UX personas from Reddit user data. It scrapes public profiles and posts, then uses Google's Gemini API to generate insights on demographics, personality, motivations, and behaviors. Perfect for researchers, marketers, and designers, it offers text, HTML, or JSON outputs, with HTML featuring interactive visualizations like motivation bars and personality sliders.

---

## Features

- **Reddit Profile Scraping**: Extracts user details (karma, bio, Reddit age, social links) using Reddit's JSON API and BeautifulSoup.
- **Post & Comment Analysis**: Analyzes up to a specified number of posts/comments to uncover user behavior and interests.
- **AI-Powered Persona Generation**: Leverages Google's Gemini API to craft personas with demographics, personality traits, motivations, and more.
- **Privacy-Focused**: Avoids personal identifiers, using general categories (e.g., "25-35" age range, "Technology" occupation).
- **Multiple Output Formats**: Supports text, HTML, and JSON outputs for versatile use.
- **Visual Persona Design**: HTML output includes styled motivation bars, personality sliders, and subreddit tags.
- **Customizable**: Configurable via command-line arguments for Reddit URL, API key, post limit, and output format.

---

## Prerequisites

To run this project, you need:

- **Python**: Version 3.8 or higher
- **Dependencies**:
  - `requests`: For HTTP requests to Reddit's API
  - `beautifulsoup4`: For HTML parsing
  - `google-generativeai`: For Google's Gemini API
  - `argparse`: For command-line argument parsing
- **Google Gemini API Key**: Get one from [Google's Gemini API](https://ai.google.dev/) and set as `GEMINI_API_KEY` environment variable or pass via command line.

Install dependencies:
```bash
pip install requests beautifulsoup4 google-generativeai
```

## Installation
**1. Clone the Repository**
```bash
git clone https://github.com/Tanuja137/Reddit.git
cd Reddit
```
**2. Install Dependencies**
```bash
pip install -r requirements.txt
```
**3. Set up environment variable (optional)**
```bash
export GEMINI_API_KEY='your-api-key-here'
```

## Usage
**Run the Script with**
```bash
python main.py <reddit_url> [--gemini-api-key <key>] [--limit <number>] [--output-format <format>] [--output-file <filename>]
```
**Arguments**
- **reddit_url**: Reddit user profile URL (e.g., https://www.reddit.com/user/username)
- **--gemini-api-key**: Google Gemini API key (optional if set via environment variable)
- **--limit**: Number of posts/comments to analyze (default: 100)
- **--output-format**: Output format (text, html, or json) (default: text)
- **--output-file**: Custom output file name (default: persona_output.<format>)

