from http.server import BaseHTTPRequestHandler
import json
import requests
import time
import logging
import re
from typing import List, Dict, Any, Optional
import uuid
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FinChat API Configuration
FINCHAT_URL = "https://finchat-api.adgo.dev"
FINCHAT_BACKOFF_SECONDS = 5

class FinChatClient:
    def __init__(self, log_collector=None):
        self.base_url = FINCHAT_URL
        self.backoff_seconds = FINCHAT_BACKOFF_SECONDS
        self.log_collector = log_collector or []
    
    def log_and_store(self, message: str):
        """Log message and store for frontend"""
        logger.info(message)
        self.log_collector.append(message)
    
    def call_remote(self, method: str, full_url: str, **kwargs) -> Dict[Any, Any]:
        """Generic HTTP caller for FinChat API"""
        self.log_and_store(f"🌐 FINCHAT API CALL: {method.upper()} {full_url}")
        if kwargs:
            self.log_and_store(f"📤 Request payload: {str(kwargs)[:200]}...")  # Truncate for readability
        
        if method == "get":
            res = requests.get(full_url, params=kwargs)
        elif method in ["post", "put"]:
            res = requests.request(method, full_url, json=kwargs)
        else:
            raise ValueError(f"Unsupported method {method}")
        
        self.log_and_store(f"📥 Response status: {res.status_code}")
        
        if res.status_code >= 400:
            error_msg = f"❌ FINCHAT API ERROR: {method} {full_url} failed with status {res.status_code}"
            self.log_and_store(error_msg)
            self.log_and_store(f"❌ Error response: {res.text}")
            raise ValueError(f"Failed to call {method} {full_url}:\nstatus:{res.status_code}\n\n{res.text}")
        
        response_data = res.json()
        self.log_and_store(f"✅ FINCHAT API SUCCESS: {method.upper()} {full_url}")
        return response_data
    
    def call_finchat(self, method: str, path: str, **kwargs) -> Dict[Any, Any]:
        """FinChat-specific wrapper"""
        full_url = f"{self.base_url}{path}"
        return self.call_remote(method, full_url, **kwargs)
    
    def wait_till_idle(self, session_id: str, log_at_checks: int = 5) -> None:
        """Wait for session to complete with dynamic backoff: 30s -> 15s -> 10s -> 5s -> 1s (then stay at 1s)"""
        self.log_and_store(f"⏳ Waiting for session {session_id} to complete...")
        check_count = 0
        
        # Dynamic backoff intervals: start long, decrease as we get closer to completion
        backoff_intervals = [30, 15, 10, 5, 1]  # seconds - final 1s for responsiveness
        
        while True:
            session = self.call_finchat(method="get", path=f"/api/v1/sessions/{session_id}/")
            check_count += 1
            session_status = session["status"]
            
            if session_status == "idle":
                self.log_and_store(f"✅ Session {session_id} is now idle (completed)")
                break
            
            # Determine current backoff interval based on check count
            if check_count <= len(backoff_intervals):
                current_backoff = backoff_intervals[check_count - 1]
            else:
                current_backoff = backoff_intervals[-1]  # Stay at 1 second after initial intervals
                
            if check_count % log_at_checks == 0:
                self.log_and_store(f"⏳ Continuing to check session {session_id} for idle. Currently {session_status}. (Checked {check_count} times)")
            
            self.log_and_store(f"⏳ Next check in {current_backoff} seconds...")
            time.sleep(current_backoff)
    
    def create_session(self) -> str:
        """Create a new FinChat session"""
        self.log_and_store("🆕 Creating new FinChat session...")
        session = self.call_finchat(
            method="post",
            path="/api/v1/sessions/",
            client_id="parsec-backtesting",
            data_source="alpha_vantage",
        )
        session_id = session["id"]
        self.log_and_store(f"✨ Created FinChat session: {session_id}")
        return session_id
    
    def send_write_aid_request(self, session_id: str, sentence: str, full_paragraph: str, author: str) -> None:
        """Send write-aid-1 request with single sentence and full paragraph"""
        magic_string = (
            f"cot write-aid-1 "
            f'$sentence:"{sentence}" '
            f'$paragraph:"{full_paragraph}" '
            f"$author:{author}"
        )
        
        self.log_and_store(f"💬 Sending write-aid-1 request to session {session_id}")
        self.log_and_store(f"📝 Single sentence: {sentence[:50]}...")
        self.log_and_store(f"📝 Full paragraph: {full_paragraph[:100]}...")
        
        self.call_finchat(
            method="post",
            path="/api/v1/chats/",
            session=session_id,
            message=magic_string,
            use_live_cot=False,
        )
        
        self.log_and_store(f"📨 Write-aid request sent to session {session_id}")
    
    def get_result(self, session_id: str) -> Optional[Dict[Any, Any]]:
        """Get analysis result with retry logic"""
        logger.info(f"🔍 Getting results for session {session_id}")
        
        max_retries = 5
        retries = 0
        result_id = None
        
        # Get result ID with dynamic backoff
        logger.info(f"📋 Fetching chat messages to get result_id...")
        result_backoff_intervals = [10, 8, 6, 3, 1]  # More aggressive since result should be available soon after idle
        
        while retries < max_retries and result_id is None:
            chat_messages = self.call_finchat("get", f"/api/v1/chats/?session_id={session_id}")
            if chat_messages["results"]:
                latest_message = chat_messages["results"][-1]
                result_id = latest_message.get("result_id")
                if result_id:
                    logger.info(f"🎯 Found result_id: {result_id}")
            if result_id is None:
                retries += 1
                current_delay = result_backoff_intervals[min(retries - 1, len(result_backoff_intervals) - 1)]
                logger.warning("⏳ No valid result_id found. Retrying in %d seconds... (%d/%d)", current_delay, retries, max_retries)
                time.sleep(current_delay)
        
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
                    # Quick retry backoff for analysis fetching: 3, 2, 1 seconds
                    analysis_backoff = [3, 2, 1][min(retries - 1, 2)]
                    logger.info(f"⏳ Retrying analysis fetch in {analysis_backoff} seconds...")
                    time.sleep(analysis_backoff)
        
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
    def __init__(self, max_workers: int = 1):  # Sequential processing to avoid 60s Vercel timeout
        self.splitter = SentenceSplitter()
        self.client = FinChatClient()
        self.max_workers = max_workers
        self.author = "EB White"
        self.logs = []  # Store logs to send to frontend
    
    def process_sentence(self, target_sentence: str, sentence_index: int, current_paragraph: str) -> Dict[Any, Any]:
        """Process a single sentence with default author (for backward compatibility)"""
        return self.process_sentence_with_author(target_sentence, sentence_index, current_paragraph, self.author)
    
    def process_sentence_with_author(self, target_sentence: str, sentence_index: int, current_paragraph: str, author: str) -> Dict[Any, Any]:
        """Process a single sentence with current paragraph context using specified author"""
        try:
            self.logs.append(f"🔄 Processing sentence {sentence_index + 1} with author '{author}': {target_sentence[:50]}...")
            
            # Create session
            session_id = self.client.create_session()
            
            # Send request with single sentence and current paragraph using specified author
            self.client.send_write_aid_request(session_id, target_sentence, current_paragraph, author)
            
            # Wait for completion
            self.client.wait_till_idle(session_id)
            
            # Get result
            result = self.client.get_result(session_id)
            
            # Extract improved sentence from the analysis result
            improved_sentence = self.client.extract_improved_sentence(result) if result else None
            
            self.logs.append(f"✅ Completed sentence {sentence_index + 1} with author '{author}': {improved_sentence[:50] if improved_sentence else 'No improvement'}")
            
            return {
                "sentence_index": sentence_index,
                "sentence": target_sentence,
                "improved_sentence": improved_sentence,
                "session_id": session_id,
                "session_url": f"https://finchat.adgo.dev/?session_id={session_id}",
                "analysis": result,
                "author_used": author,  # New: track which author was used
                "success": True
            }
            
        except Exception as e:
            error_msg = f"❌ Error processing sentence {sentence_index + 1} with author '{author}': {str(e)}"
            self.logs.append(error_msg)
            return {
                "sentence_index": sentence_index,
                "sentence": target_sentence,
                "improved_sentence": None,
                "error": str(e),
                "author_used": author,
                "success": False
            }
    
    def process_paragraph(self, paragraph: str, processing_direction: str = 'first-to-last', reprocessing_rounds: int = 0, initial_author: str = 'EB White', reprocessing_author: str = 'EB White') -> Dict[str, Any]:
        """Process entire paragraph sentence by sentence with progressive paragraph updating"""
        import time
        
        # Record processing start time
        processing_start_time = time.time()
        
        original_sentences = self.splitter.split_paragraph(paragraph)
        self.logs = []  # Reset logs for this request
        self.client = FinChatClient(self.logs)  # Pass logs to client
        
        self.logs.append(f"⏱️ Starting processing at {processing_start_time}")
        
        # Smart sentence limiting based on Vercel 60s timeout
        # Each sentence takes ~30-40 seconds, so we can safely do 1-2 sentences
        max_sentences_safe = 1  # Conservative limit to avoid 504 timeouts
        
        self.logs.append(f"📊 Found {len(original_sentences)} sentences")
        
        if len(original_sentences) > max_sentences_safe:
            self.logs.append(f"⚠️ Vercel has 60s timeout limit. Processing first {max_sentences_safe} sentence(s) to avoid 504 errors.")
            self.logs.append(f"💡 For complete analysis, use smaller paragraphs or run locally with backend/app.py")
            original_sentences = original_sentences[:max_sentences_safe]
        
        self.logs.append(f"📝 Processing {len(original_sentences)} sentence(s) with progressive paragraph updating")
        self.logs.append(f"🔄 Processing direction: {processing_direction}")
        self.logs.append(f"🔄 Reprocessing rounds: {reprocessing_rounds}")
        self.logs.append(f"🚀 Starting sequential processing with progressive context updates")
        
        if reprocessing_rounds > 0:
            total_processing_time = len(original_sentences) * (1 + reprocessing_rounds)
            self.logs.append(f"🔄 With {reprocessing_rounds} reprocessing round(s), this will process {total_processing_time} sentences total.")
        
        # Initialize tracking variables for all rounds
        current_paragraph = paragraph  # Start with original paragraph
        all_rounds_results = []  # Store results from all rounds
        
        # Process initial round + reprocessing rounds
        for round_num in range(1 + reprocessing_rounds):
            self.logs.append(f"🚀 Starting processing round {round_num + 1}/{1 + reprocessing_rounds}")
            
            # For each round, split the current paragraph (which may have been improved)
            current_sentences = self.splitter.split_paragraph(current_paragraph)
            round_results = []
            
            # Determine processing order based on direction
            if processing_direction == 'last-to-first':
                processing_indices = list(range(len(current_sentences) - 1, -1, -1))  # Reverse order
                self.logs.append(f"🔄 Round {round_num + 1}: Processing sentences in reverse order: {len(current_sentences)} to 1")
            else:
                processing_indices = list(range(len(current_sentences)))  # Forward order
                self.logs.append(f"🔄 Round {round_num + 1}: Processing sentences in forward order: 1 to {len(current_sentences)}")
            
            # Determine which author to use for this round
            current_author = initial_author if round_num == 0 else reprocessing_author
            self.logs.append(f"Round {round_num + 1}: Using author '{current_author}' for this round")
            
            # Process sentences sequentially (no concurrent processing for progressive updates)
            for processing_order, i in enumerate(processing_indices):
                target_sentence = current_sentences[i]
                self.logs.append(f"🎯 Round {round_num + 1}: Processing sentence {i + 1} (order {processing_order + 1}/{len(current_sentences)}) with updated paragraph context")
                
                # Process the sentence with current paragraph context using the appropriate author
                result = self.process_sentence_with_author(target_sentence, i, current_paragraph, current_author)
                # Add round information to the result
                result['round'] = round_num + 1
                result['is_reprocessing'] = round_num > 0
                round_results.append(result)
                
                # If we got an improved sentence, update the paragraph for next iteration
                if result['success'] and result['improved_sentence']:
                    old_sentence = current_sentences[i]
                    new_sentence = result['improved_sentence']
                    
                    # Replace the sentence in the current paragraph
                    current_paragraph = current_paragraph.replace(old_sentence, new_sentence, 1)
                    
                    # Update the current sentences list
                    current_sentences[i] = new_sentence
                    
                    self.logs.append(f"🔄 Round {round_num + 1}: Updated paragraph with improved sentence {i + 1}")
                    self.logs.append(f"📝 Next sentences will use updated context")
                else:
                    self.logs.append(f"⚠️ Round {round_num + 1}: No improvement for sentence {i + 1}, keeping original for context")
            
            # Store results for this round
            all_rounds_results.append({
                'round': round_num + 1,
                'is_reprocessing': round_num > 0,
                'results': round_results,
                'paragraph_after_round': current_paragraph
            })
            
            self.logs.append(f"✅ Completed processing round {round_num + 1}/{1 + reprocessing_rounds}")
        
        # Flatten all results for backward compatibility, but keep the last round as primary
        final_round_results = all_rounds_results[-1]['results'] if all_rounds_results else []
        
        # Calculate total processing time
        processing_end_time = time.time()
        total_processing_time = processing_end_time - processing_start_time
        self.logs.append(f"⏱️ Processing completed in {total_processing_time:.2f} seconds")
        
        # Sort results by sentence index (should already be sorted, but for consistency)
        sorted_results = sorted(final_round_results, key=lambda x: x["sentence_index"])
        
        return {
            "original_paragraph": paragraph,
            "final_paragraph": current_paragraph,  # The progressively updated paragraph
            "sentence_results": sorted_results,
            "total_sentences": len(original_sentences),
            "successful_analyses": len([r for r in sorted_results if r["success"]]),
            "failed_analyses": len([r for r in sorted_results if not r["success"]]),
            "session_urls": [r["session_url"] for r in sorted_results if r["success"]],
            "reprocessing_rounds": reprocessing_rounds,
            "all_rounds_results": all_rounds_results,  # New: detailed results from all rounds
            "processing_time_seconds": total_processing_time,  # New: actual backend processing time
            "summary": {
                "processing_success_rate": len([r for r in sorted_results if r["success"]]) / len(sorted_results) * 100 if sorted_results else 0,
                "sentences_processed": len([r for r in sorted_results if r["success"]]),
                "sentences_failed": len([r for r in sorted_results if not r["success"]]),
                "paragraph_updated": current_paragraph != paragraph,
                "total_rounds_processed": len(all_rounds_results),
                "processing_time_seconds": total_processing_time
            },
            "logs": self.logs
        }

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        """Handle POST request"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Parse JSON
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON")
                return
            
            # Validate input
            if not data or 'paragraph' not in data:
                self.send_error_response(400, "Missing 'paragraph' in request body")
                return
            
            paragraph = data['paragraph'].strip()
            if not paragraph:
                self.send_error_response(400, "Paragraph cannot be empty")
                return
            
            # Get processing direction (default to first-to-last for backward compatibility)
            processing_direction = data.get('processing_direction', 'first-to-last')
            if processing_direction not in ['first-to-last', 'last-to-first']:
                self.send_error_response(400, "Invalid processing_direction. Must be 'first-to-last' or 'last-to-first'")
                return
            
            # Get reprocessing rounds (default to 0 for backward compatibility)
            reprocessing_rounds = data.get('reprocessing_rounds', 0)
            if not isinstance(reprocessing_rounds, int) or reprocessing_rounds < 0 or reprocessing_rounds > 1:
                self.send_error_response(400, "Invalid reprocessing_rounds. Must be 0 or 1")
                return
            
            # Get author names (default to EB White for backward compatibility)
            initial_author = data.get('initial_author', 'EB White').strip()
            reprocessing_author = data.get('reprocessing_author', 'EB White').strip()
            if not initial_author:
                initial_author = 'EB White'
            if not reprocessing_author:
                reprocessing_author = 'EB White'
            
            # Generate unique request ID for tracking
            request_id = str(uuid.uuid4())
            logger.info(f"Starting analysis for request {request_id} with direction {processing_direction}, {reprocessing_rounds} reprocessing rounds, authors: {initial_author}/{reprocessing_author}")
            
            # Process paragraph with adaptive workers based on sentence count
            splitter = SentenceSplitter()
            sentences = splitter.split_paragraph(paragraph)
            
            # Sequential processing to stay within Vercel 60s timeout: always 1 worker
            max_workers = 1
            logger.info(f"Using {max_workers} worker for {len(sentences)} sentences (Sequential processing for 60s Vercel timeout)")
            
            processor = WriteAidProcessor(max_workers=max_workers)
            processing_result = processor.process_paragraph(paragraph, processing_direction, reprocessing_rounds, initial_author, reprocessing_author)
            
            # Extract data from the new format
            sentence_results = processing_result["sentence_results"]
            logs = processing_result["logs"]
            
            # Generate report using the processing_result data
            report = {
                "request_id": request_id,
                "original_paragraph": processing_result["original_paragraph"],
                "final_paragraph": processing_result["final_paragraph"],
                "total_sentences": processing_result["total_sentences"],
                "successful_analyses": processing_result["successful_analyses"],
                "failed_analyses": processing_result["failed_analyses"],
                "sentence_results": sentence_results,
                "session_urls": processing_result["session_urls"],
                "logs": logs,  # Include logs for frontend console
                "summary": processing_result["summary"]
            }
            
            logger.info(f"Completed analysis for request {request_id}. Success rate: {report['summary']['processing_success_rate']:.1f}%")
            
            # Send successful response
            self.send_success_response(report)
            
        except Exception as e:
            logger.error(f"Error in analyze_paragraph: {str(e)}")
            self.send_error_response(500, f"Internal server error: {str(e)}")
    
    def send_success_response(self, data):
        """Send successful JSON response"""
        response = json.dumps(data)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def send_error_response(self, status_code, message):
        """Send error JSON response"""
        error_data = {"error": message}
        response = json.dumps(error_data)
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))