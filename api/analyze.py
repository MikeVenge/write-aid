from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import logging
import re
import concurrent.futures
from typing import List, Dict, Any, Optional
import uuid

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
    
    def send_write_aid_request(self, session_id: str, sentence: str, paragraph: str, author: str) -> None:
        """Send write-aid-1 request"""
        magic_string = (
            f"cot write-aid-1 "
            f'$sentence:"{sentence}" '
            f'$paragraph:"{paragraph}" '
            f"$author:{author}"
        )
        
        logger.info(f"💬 Sending write-aid-1 request to session {session_id}")
        logger.info(f"📝 Magic string: {magic_string}")
        
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
    def __init__(self, max_workers: int = 3):
        self.splitter = SentenceSplitter()
        self.client = FinChatClient()
        self.max_workers = max_workers
        self.author = "EB White"
    
    def process_sentence(self, sentence: str, paragraph: str, sentence_index: int) -> Dict[Any, Any]:
        """Process a single sentence through FinChat API"""
        try:
            logger.info(f"Processing sentence {sentence_index + 1}: {sentence[:50]}...")
            
            # Create session
            session_id = self.client.create_session()
            
            # Send request
            self.client.send_write_aid_request(session_id, sentence, paragraph, self.author)
            
            # Wait for completion
            self.client.wait_till_idle(session_id)
            
            # Get result
            result = self.client.get_result(session_id)
            
            # Extract improved sentence from the analysis result
            improved_sentence = self.client.extract_improved_sentence(result) if result else None
            
            return {
                "sentence_index": sentence_index,
                "sentence": sentence,
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
                "sentence": sentence,
                "improved_sentence": None,
                "error": str(e),
                "success": False
            }
    
    def process_paragraph(self, paragraph: str) -> List[Dict[Any, Any]]:
        """Process entire paragraph sentence by sentence"""
        sentences = self.splitter.split_paragraph(paragraph)
        logger.info(f"Processing {len(sentences)} sentences")
        
        # Process sentences in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for i, sentence in enumerate(sentences):
                future = executor.submit(self.process_sentence, sentence, paragraph, i)
                futures.append(future)
            
            results = []
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
        
        # Sort results by sentence index
        return sorted(results, key=lambda x: x["sentence_index"])

# Global processor instance
processor = WriteAidProcessor()

def handler(request):
    """Vercel serverless function handler"""
    if request.method == 'OPTIONS':
        # Handle preflight CORS request
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            },
            'body': ''
        }
    
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': jsonify({"error": "Method not allowed"}).data
        }
    
    try:
        data = request.get_json()
        
        if not data or 'paragraph' not in data:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': jsonify({"error": "Missing 'paragraph' in request body"}).data
            }
        
        paragraph = data['paragraph'].strip()
        if not paragraph:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': jsonify({"error": "Paragraph cannot be empty"}).data
            }
        
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        logger.info(f"Starting analysis for request {request_id}")
        
        # Process paragraph
        results = processor.process_paragraph(paragraph)
        
        # Generate report
        successful_analyses = [r for r in results if r["success"]]
        failed_analyses = [r for r in results if not r["success"]]
        
        report = {
            "request_id": request_id,
            "original_paragraph": paragraph,
            "total_sentences": len(results),
            "successful_analyses": len(successful_analyses),
            "failed_analyses": len(failed_analyses),
            "sentence_results": results,
            "session_urls": [r["session_url"] for r in successful_analyses],
            "summary": {
                "processing_success_rate": len(successful_analyses) / len(results) * 100 if results else 0,
                "sentences_processed": len(successful_analyses),
                "sentences_failed": len(failed_analyses)
            }
        }
        
        logger.info(f"Completed analysis for request {request_id}. Success rate: {report['summary']['processing_success_rate']:.1f}%")
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': jsonify(report).data
        }
        
    except Exception as e:
        logger.error(f"Error in analyze_paragraph: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': jsonify({"error": f"Internal server error: {str(e)}"}).data
        }
