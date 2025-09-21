from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import requests
import time
import logging
import re
from typing import List, Dict, Any, Optional
import uuid

app = Flask(__name__)
CORS(app, origins=["*"], methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])  # Enhanced CORS for Railway

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FinChat API Configuration
FINCHAT_URL = "https://finchat-api.adgo.dev"
FINCHAT_BACKOFF_SECONDS = 5

class FinChatClient:
    def __init__(self):
        self.base_url = FINCHAT_URL
        self.backoff_seconds = FINCHAT_BACKOFF_SECONDS
    
    def call_remote(self, method: str, full_url: str, **kwargs) -> Dict[Any, Any]:
        """Generic HTTP caller for FinChat API"""
        logger.info(f"🌐 FINCHAT API CALL: {method.upper()} {full_url}")
        if kwargs:
            logger.info(f"📤 Request payload: {kwargs}")
        
        if method == "get":
            res = requests.get(full_url, params=kwargs)
        elif method in ["post", "put"]:
            res = requests.request(method, full_url, json=kwargs)
        else:
            raise ValueError(f"Unsupported method {method}")
        
        logger.info(f"📥 Response status: {res.status_code}")
        
        if res.status_code >= 400:
            logger.error(f"❌ FINCHAT API ERROR: {method} {full_url} failed with status {res.status_code}")
            logger.error(f"❌ Error response: {res.text}")
            raise ValueError(f"Failed to call {method} {full_url}:\nstatus:{res.status_code}\n\n{res.text}")
        
        response_data = res.json()
        logger.info(f"✅ FINCHAT API SUCCESS: {method.upper()} {full_url}")
        return response_data
    
    def call_finchat(self, method: str, path: str, **kwargs) -> Dict[Any, Any]:
        """FinChat-specific wrapper"""
        full_url = f"{self.base_url}{path}"
        return self.call_remote(method, full_url, **kwargs)
    
    def wait_till_idle(self, session_id: str, log_at_checks: int = 5) -> None:
        """Wait for session to complete"""
        logger.info(f"⏳ Waiting for session {session_id} to complete...")
        check_count = 0
        while True:
            session = self.call_finchat(method="get", path=f"/api/v1/sessions/{session_id}/")
            check_count += 1
            session_status = session["status"]
            
            if session_status == "idle":
                logger.info(f"✅ Session {session_id} is now idle (completed)")
                break
                
            if check_count % log_at_checks == 0:
                logger.info("⏳ Continuing to check session %s for idle. Currently %s. (Checked %s times)",
                           session_id, session_status, check_count)
            
            time.sleep(self.backoff_seconds)
    
    def create_session(self) -> str:
        """Create a new FinChat session"""
        logger.info("🆕 Creating new FinChat session...")
        session = self.call_finchat(
            method="post",
            path="/api/v1/sessions/",
            client_id="parsec-backtesting",
            data_source="alpha_vantage",
        )
        session_id = session["id"]
        logger.info(f"✨ Created FinChat session: {session_id}")
        return session_id
    
    def send_write_aid_request(self, session_id: str, sentence: str, full_paragraph: str, author: str) -> None:
        """Send write-aid-1 request with single sentence and full paragraph"""
        magic_string = (
            f"cot write-aid-1 "
            f'$sentence:"{sentence}" '
            f'$paragraph:"{full_paragraph}" '
            f"$author:{author}"
        )
        
        logger.info(f"💬 Sending write-aid-1 request to session {session_id}")
        logger.info(f"📝 Single sentence: {sentence}")
        logger.info(f"📝 Full paragraph: {full_paragraph[:100]}...")
        
        self.call_finchat(
            method="post",
            path="/api/v1/chats/",
            session=session_id,
            message=magic_string,
            use_live_cot=False,
        )
        
        logger.info(f"📨 Write-aid request sent to session {session_id}")
    
    def get_result(self, session_id: str) -> Optional[Dict[Any, Any]]:
        """Get analysis result with retry logic"""
        logger.info(f"🔍 Getting results for session {session_id}")
        
        max_retries = 5
        retries = 0
        result_id = None
        
        # Get result ID
        logger.info(f"📋 Fetching chat messages to get result_id...")
        while retries < max_retries and result_id is None:
            chat_messages = self.call_finchat("get", f"/api/v1/chats/?session_id={session_id}")
            if chat_messages["results"]:
                latest_message = chat_messages["results"][-1]
                result_id = latest_message.get("result_id")
                if result_id:
                    logger.info(f"🎯 Found result_id: {result_id}")
            if result_id is None:
                retries += 1
                logger.warning("⏳ No valid result_id found. Retrying... (%d/%d)", retries, max_retries)
                time.sleep(15)
        
        if result_id is None:
            logger.error("❌ Max retries reached. Failed to obtain a valid result_id")
            return None
        
        # Fetch full analysis
        logger.info(f"📊 Fetching full analysis for result_id: {result_id}")
        max_retries = 3
        retries = 0
        full_analysis = None
        
        while retries < max_retries:
            try:
                full_analysis = self.call_finchat("get", f"/api/v1/results/{result_id}/")
                logger.info(f"✅ Successfully retrieved analysis for result_id: {result_id}")
                break
            except Exception as e:
                retries += 1
                logger.error("⚠️ Analysis fetch attempt %d/%d failed: %s", retries, max_retries, str(e))
                if retries < max_retries:
                    time.sleep(5)
        
        if full_analysis is None:
            logger.error("❌ Failed to fetch analysis after %d retries", max_retries)
            return None
        
        return full_analysis
    
    def extract_improved_sentence(self, analysis_result: Dict[Any, Any]) -> Optional[str]:
        """Extract the improved sentence from FinChat analysis result"""
        try:
            # The improved sentence is in the 'content' field of the FinChat response
            if isinstance(analysis_result, dict) and 'content' in analysis_result:
                improved_sentence = analysis_result['content']
                if improved_sentence:
                    logger.info(f"✨ Extracted improved sentence: {improved_sentence}")
                    return improved_sentence
                else:
                    logger.warning("⚠️ Content field is empty")
                    return None
            else:
                logger.warning("⚠️ Could not find 'content' field in analysis result")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting improved sentence: {str(e)}")
            return None

class SentenceSplitter:
    def __init__(self):
        # Regex pattern for sentence boundaries
        self.sentence_pattern = r'(?<=[.!?])\s+'
    
    def split_paragraph(self, paragraph: str) -> List[str]:
        """Split paragraph into individual sentences"""
        sentences = re.split(self.sentence_pattern, paragraph.strip())
        # Clean and filter empty sentences
        return [s.strip() for s in sentences if s.strip()]

class WriteAidProcessor:
    def __init__(self, max_workers: int = 2):  # Reduced to 2 workers to avoid timeouts
        self.splitter = SentenceSplitter()
        self.client = FinChatClient()
        self.max_workers = max_workers
        self.author = "EB White"
    
    def process_sentence(self, target_sentence: str, sentence_index: int, current_paragraph: str) -> Dict[Any, Any]:
        """Process a single sentence with current paragraph context"""
        try:
            logger.info(f"Processing sentence {sentence_index + 1}: {target_sentence[:50]}...")
            
            # Create session
            session_id = self.client.create_session()
            
            # Send request with single sentence and current paragraph (which may have been updated)
            self.client.send_write_aid_request(session_id, target_sentence, current_paragraph, self.author)
            
            # Wait for completion
            self.client.wait_till_idle(session_id)
            
            # Get result
            result = self.client.get_result(session_id)
            
            # Extract improved sentence from the analysis result
            improved_sentence = self.client.extract_improved_sentence(result) if result else None
            
            return {
                "sentence_index": sentence_index,
                "sentence": target_sentence,
                "improved_sentence": improved_sentence,
                "session_id": session_id,
                "session_url": f"https://finchat.adgo.dev/?session_id={session_id}",
                "analysis": result,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error processing sentence {sentence_index + 1}: {str(e)}")
            return {
                "sentence_index": sentence_index,
                "sentence": target_sentence,
                "error": str(e),
                "success": False
            }
    
    def process_paragraph(self, paragraph: str) -> Dict[str, Any]:
        """Process entire paragraph sentence by sentence with progressive paragraph updating"""
        original_sentences = self.splitter.split_paragraph(paragraph)
        logger.info(f"Processing {len(original_sentences)} sentences with progressive paragraph updating")
        
        # Initialize tracking variables
        current_paragraph = paragraph  # Start with original paragraph
        current_sentences = original_sentences.copy()  # Track current sentence states
        results = []
        
        # Process sentences sequentially (no concurrent processing for progressive updates)
        for i in range(len(original_sentences)):
            target_sentence = current_sentences[i]
            logger.info(f"Processing sentence {i + 1} with updated paragraph context")
            
            # Process the sentence with current paragraph context
            result = self.process_sentence(target_sentence, i, current_paragraph)
            results.append(result)
            
            # If we got an improved sentence, update the paragraph for next iteration
            if result['success'] and result['improved_sentence']:
                old_sentence = current_sentences[i]
                new_sentence = result['improved_sentence']
                
                # Replace the sentence in the current paragraph
                current_paragraph = current_paragraph.replace(old_sentence, new_sentence, 1)
                
                # Update the current sentences list
                current_sentences[i] = new_sentence
                
                logger.info(f"Updated paragraph with improved sentence {i + 1}")
                logger.info(f"Next sentences will use updated context")
            else:
                logger.info(f"No improvement for sentence {i + 1}, keeping original for context")
        
        # Sort results by sentence index (should already be sorted, but for consistency)
        sorted_results = sorted(results, key=lambda x: x["sentence_index"])
        
        return {
            "original_paragraph": paragraph,
            "final_paragraph": current_paragraph,  # The progressively updated paragraph
            "sentence_results": sorted_results,
            "total_sentences": len(original_sentences),
            "successful_analyses": len([r for r in sorted_results if r["success"]]),
            "failed_analyses": len([r for r in sorted_results if not r["success"]]),
            "session_urls": [r["session_url"] for r in sorted_results if r["success"]],
            "summary": {
                "processing_success_rate": len([r for r in sorted_results if r["success"]]) / len(sorted_results) * 100 if sorted_results else 0,
                "sentences_processed": len([r for r in sorted_results if r["success"]]),
                "sentences_failed": len([r for r in sorted_results if not r["success"]]),
                "paragraph_updated": current_paragraph != paragraph
            }
        }

# Global processor instance
processor = WriteAidProcessor()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "write-aid-backend"})

@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
def analyze_paragraph():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    """Analyze a paragraph using Write Aid"""
    try:
        data = request.get_json()
        
        if not data or 'paragraph' not in data:
            return jsonify({"error": "Missing 'paragraph' in request body"}), 400
        
        paragraph = data['paragraph'].strip()
        if not paragraph:
            return jsonify({"error": "Paragraph cannot be empty"}), 400
        
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        logger.info(f"Starting analysis for request {request_id}")
        
        # Process paragraph
        processing_result = processor.process_paragraph(paragraph)
        
        # Extract sentence results for compatibility
        sentence_results = processing_result["sentence_results"]
        successful_analyses = [r for r in sentence_results if r["success"]]
        failed_analyses = [r for r in sentence_results if not r["success"]]
        
        report = {
            "request_id": request_id,
            "original_paragraph": processing_result["original_paragraph"],
            "final_paragraph": processing_result["final_paragraph"],  # New: progressively updated paragraph
            "total_sentences": processing_result["total_sentences"],
            "successful_analyses": processing_result["successful_analyses"],
            "failed_analyses": processing_result["failed_analyses"],
            "sentence_results": sentence_results,
            "session_urls": processing_result["session_urls"],
            "summary": processing_result["summary"]
        }
        
        logger.info(f"Completed analysis for request {request_id}. Success rate: {report['summary']['processing_success_rate']:.1f}%")
        
        # Create response with proper headers for Railway
        response = jsonify(report)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    except Exception as e:
        logger.error(f"Error in analyze_paragraph: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/split-sentences', methods=['POST'])
def split_sentences():
    """Split a paragraph into sentences (utility endpoint)"""
    try:
        data = request.get_json()
        
        if not data or 'paragraph' not in data:
            return jsonify({"error": "Missing 'paragraph' in request body"}), 400
        
        paragraph = data['paragraph'].strip()
        if not paragraph:
            return jsonify({"error": "Paragraph cannot be empty"}), 400
        
        splitter = SentenceSplitter()
        sentences = splitter.split_paragraph(paragraph)
        
        return jsonify({
            "paragraph": paragraph,
            "sentences": sentences,
            "sentence_count": len(sentences)
        })
        
    except Exception as e:
        logger.error(f"Error in split_sentences: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# For Railway deployment, the app needs to be available at module level
# Railway will call this directly
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
