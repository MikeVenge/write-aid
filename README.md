# Write Aid - Sentence-by-Sentence Writing Analysis

Write Aid is a full-stack application that provides sentence-by-sentence writing analysis using the FinChat API. It takes a paragraph as input and analyzes each sentence individually using the `write-aid-1` prompt.

## System Architecture

- **Frontend**: React application with a clean, modern UI
- **Backend**: Flask API server that interfaces with FinChat
- **Analysis**: Each sentence is processed individually through FinChat's `write-aid-1` prompt

## Features

- ✨ **Sentence-by-Sentence Analysis**: Each sentence is analyzed individually for writing improvements
- 🔄 **Parallel Processing**: Multiple sentences processed simultaneously for faster results
- 📊 **Detailed Results**: View analysis results with success rates and session URLs
- 🌐 **FinChat Integration**: Direct links to detailed analysis in FinChat interface
- 📱 **Responsive Design**: Works on desktop and mobile devices
- ⚡ **Real-time Feedback**: Live progress updates during analysis

## Project Structure

```
write-aid/
├── backend/                 # Python Flask backend
│   ├── app.py              # Main Flask application
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend
│   ├── public/
│   │   └── index.html     # HTML template
│   ├── src/
│   │   ├── App.js         # Main React component
│   │   ├── App.css        # Styles
│   │   ├── index.js       # React entry point
│   │   └── index.css      # Global styles
│   └── package.json       # Node.js dependencies
├── finchat_readme.md      # FinChat API documentation
└── README.md              # This file
```

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the Flask server:
   ```bash
   python app.py
   ```

   The backend will be available at `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the React development server:
   ```bash
   npm start
   ```

   The frontend will be available at `http://localhost:3000`

## API Endpoints

### Backend API

- `GET /api/health` - Health check endpoint
- `POST /api/analyze` - Analyze a paragraph
  ```json
  {
    "paragraph": "Your paragraph text here."
  }
  ```
- `POST /api/split-sentences` - Utility endpoint to split sentences
  ```json
  {
    "paragraph": "Your paragraph text here."
  }
  ```

## How It Works

1. **Input**: User enters a paragraph in the React frontend
2. **Sentence Splitting**: Backend splits the paragraph into individual sentences
3. **Parallel Processing**: Each sentence is sent to FinChat API simultaneously
4. **FinChat Analysis**: Each sentence is analyzed using the `write-aid-1` prompt:
   ```
   cot write-aid-1 $sentence:{sentence} $paragraph:{full_paragraph} $author:EB White
   ```
5. **Result Aggregation**: All analysis results are collected and formatted
6. **Display**: Frontend shows results with links to detailed FinChat sessions

## FinChat Integration

The system uses the FinChat API workflow:

1. **Create Session**: `POST /api/v1/sessions/`
2. **Send Message**: `POST /api/v1/chats/` with the write-aid-1 prompt
3. **Wait for Completion**: Poll session status until "idle"
4. **Retrieve Results**: Get the analysis results

Each analysis includes:
- Original sentence
- Analysis results from FinChat
- Direct link to FinChat session for detailed review
- Success/failure status

## Configuration

### Backend Configuration

- **FinChat URL**: `https://finchat-api.adgo.dev`
- **Author**: Currently set to "EB White" (configurable in code)
- **Max Workers**: Default 3 concurrent sentences (configurable)
- **Retry Logic**: Built-in retry mechanisms for API failures

### Frontend Configuration

- **API Base URL**: Automatically configured for development/production
- **Proxy**: Development proxy to backend on port 5000

## Error Handling

The system includes robust error handling:

- **Individual Sentence Failures**: One failed sentence doesn't stop others
- **API Retry Logic**: Automatic retries for transient failures
- **User Feedback**: Clear error messages and status indicators
- **Graceful Degradation**: Partial results shown even with some failures

## Example Usage

1. Enter a paragraph like:
   ```
   Writing is both an art and a craft that requires constant practice and refinement. 
   The best writers understand that their first draft is rarely their final product. 
   Through careful revision and thoughtful editing, a piece of writing can be transformed 
   from a rough collection of ideas into a polished work that communicates clearly and 
   effectively with its intended audience.
   ```

2. Click "Analyze Writing"

3. View results showing:
   - Analysis for each of the 3 sentences
   - Success rate and statistics
   - Links to detailed FinChat sessions
   - Individual sentence feedback

## Development

### Adding New Features

1. **Backend**: Add new endpoints in `backend/app.py`
2. **Frontend**: Add new components in `frontend/src/`
3. **Styling**: Update styles in `frontend/src/App.css`

### Environment Variables

Create `.env` files for environment-specific configuration:

**Backend (.env)**:
```
FINCHAT_URL=https://finchat-api.adgo.dev
MAX_WORKERS=3
AUTHOR=EB White
```

**Frontend (.env)**:
```
REACT_APP_API_URL=http://localhost:5000
```

## Deployment

### Vercel Deployment (Recommended)

The application is configured for easy deployment to Vercel, which handles both the React frontend and Python backend as serverless functions.

#### Prerequisites
- GitHub account with the repository
- Vercel account (free tier available)

#### Deploy Steps

1. **Connect to Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Sign in with your GitHub account
   - Click "New Project"
   - Import the `write-aid` repository

2. **Configure Build Settings**:
   - **Framework Preset**: Other
   - **Root Directory**: Leave empty (uses root)
   - **Build Command**: `cd frontend && npm run build`
   - **Output Directory**: `frontend/build`
   - **Install Command**: `cd frontend && npm install`

3. **Deploy**:
   - Click "Deploy"
   - Vercel will automatically build and deploy your application
   - Your app will be available at `https://your-project-name.vercel.app`

#### Environment Variables
No additional environment variables are required for basic functionality.

#### API Routes
- Frontend: `https://your-app.vercel.app/`
- Backend API: `https://your-app.vercel.app/api/analyze`
- Health Check: `https://your-app.vercel.app/api/health`

### Alternative Deployment Options

#### Backend Deployment

1. Use a WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn backend.app:app
   ```

2. Or deploy to platforms like:
   - Heroku
   - AWS Lambda
   - Google Cloud Run
   - DigitalOcean App Platform

#### Frontend Deployment

1. Build the production bundle:
   ```bash
   cd frontend && npm run build
   ```

2. Deploy to platforms like:
   - Netlify
   - AWS S3 + CloudFront
   - GitHub Pages

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues or questions:
1. Check the FinChat API documentation in `finchat_readme.md`
2. Review the error logs in the browser console and backend logs
3. Open an issue in the repository
