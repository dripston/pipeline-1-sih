import base64
import requests
import os
import json
import tempfile
from typing import Dict, Any, Optional
from PIL import Image, ExifTags


class VisualSummaryAgent:
    def __init__(self, sambanova_api_keys: list = None, huggingface_api_key: str = None):
        """
        Initialize the visual summary agent with SambaNova API keys and optional Hugging Face credentials.
        
        Args:
            sambanova_api_keys: List of API keys for SambaNova (for fallback)
            huggingface_api_key: API key for Hugging Face (optional)
        """
        # Use provided keys or get from environment variables
        self.sambanova_api_keys = sambanova_api_keys or [
            os.getenv("SAMBANOVA_API_KEY_1"),
            os.getenv("SAMBANOVA_API_KEY_2"),
            os.getenv("SAMBANOVA_API_KEY_3"),
            os.getenv("SAMBANOVA_API_KEY_4")
        ]
        # Filter out None values
        self.sambanova_api_keys = [key for key in self.sambanova_api_keys if key]
        
        self.huggingface_api_key = huggingface_api_key or os.getenv("HUGGINGFACE_API_KEY")
        self.api_url = "https://api.sambanova.ai/v1/chat/completions"
        # Use the specific model you mentioned
        self.model = "Llama-4-Maverick-17B-128E-Instruct"
        # Hugging Face model for AI-generated image detection
        self.hf_model_url = "https://api-inference.huggingface.co/models/umm-maybe/AI-image-detector"
    
    def _detect_ai_generated_hf(self, image_path: str) -> Dict[str, Any]:
        """
        Detect if an image is AI-generated using Hugging Face API.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            AI-generated detection results
        """
        if not self.huggingface_api_key:
            print("Hugging Face API key not provided. Skipping AI-generated image detection.")
            return {"status": "skipped", "reason": "No API key provided"}
        
        try:
            # Clean the path by removing surrounding quotes if present
            clean_path = image_path.strip().strip('"').strip("'")
            
            # Check if file exists
            if not os.path.exists(clean_path):
                return {"status": "error", "reason": "Image file not found"}
            
            # Prepare the API request
            headers = {
                "Authorization": f"Bearer {self.huggingface_api_key}"
            }
            
            # Read the image file
            with open(clean_path, "rb") as f:
                data = f.read()
            
            # Make the API request
            response = requests.post(self.hf_model_url, headers=headers, data=data)
            
            if response.status_code == 200:
                result = response.json()
                # Check if any label indicates AI-generated content with high confidence
                is_ai_generated = False
                for item in result:
                    label = item.get("label", "").lower()
                    score = item.get("score", 0)
                    if ("artificial" in label or "ai" in label) and score > 0.5:
                        is_ai_generated = True
                        break
                
                return {
                    "status": "ai-generated" if is_ai_generated else "natural",
                    "data": result,
                    "confidence": max([item.get("score", 0) for item in result]) if result else 0
                }
            else:
                print(f"Hugging Face API request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return {"status": "error", "reason": f"API request failed with status {response.status_code}"}
                
        except Exception as e:
            print(f"Error detecting AI-generated content: {e}")
            return {"status": "error", "reason": str(e)}
    
    def _check_exif_data(self, image_path: str) -> Dict[str, Any]:
        """
        Check EXIF data of an image to detect potential AI generation.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            EXIF analysis results
        """
        try:
            # Clean the path by removing surrounding quotes if present
            clean_path = image_path.strip().strip('"').strip("'")
            
            # Check if file exists
            if not os.path.exists(clean_path):
                return {"status": "error", "reason": "Image file not found"}
            
            # Open image and extract EXIF data
            image = Image.open(clean_path)
            exif_data = image._getexif()
            
            if not exif_data:
                return {
                    "status": "suspicious", 
                    "reason": "No EXIF data found - possible AI-generated image",
                    "exif_present": False
                }
            
            # Convert EXIF tags to readable format (handle serialization issues)
            exif_readable = {}
            if exif_data:
                for tag, value in exif_data.items():
                    try:
                        tag_name = ExifTags.TAGS.get(tag, tag)
                        # Convert value to string to avoid serialization issues
                        if hasattr(value, '__dict__') or str(type(value)) == "<class 'PIL.TiffImagePlugin.IFDRational'>":
                            exif_readable[tag_name] = str(value)
                        else:
                            exif_readable[tag_name] = value
                    except Exception:
                        # Skip problematic tags
                        continue
            
            # Check for common AI generation indicators in EXIF data
            suspicious_indicators = []
            
            # Check for software that's commonly used for AI generation
            software = str(exif_readable.get('Software', '')).lower()
            if any(ai_tool in software for ai_tool in ['dall', 'midjourney', 'stable diffusion', 'openai', 'imagen']):
                suspicious_indicators.append(f"AI software detected in EXIF: {software}")
            
            # Check for missing or incomplete EXIF data
            important_tags = ['Make', 'Model', 'DateTime', 'DateTimeOriginal']
            missing_tags = [tag for tag in important_tags if tag not in exif_readable]
            if len(missing_tags) > 2:
                suspicious_indicators.append(f"Missing important EXIF tags: {missing_tags}")
            
            # Check for generic or suspicious values
            make = str(exif_readable.get('Make', '')).lower()
            model = str(exif_readable.get('Model', '')).lower()
            if 'ai' in make or 'ai' in model or 'generated' in make or 'generated' in model:
                suspicious_indicators.append(f"Suspicious camera info: {make} {model}")
            
            return {
                "status": "suspicious" if suspicious_indicators else "ok",
                "reason": suspicious_indicators if suspicious_indicators else "EXIF data appears normal",
                "exif_present": True,
                "exif_data": exif_readable,
                "suspicious_indicators": suspicious_indicators
            }
            
        except Exception as e:
            print(f"Error checking EXIF data: {e}")
            return {
                "status": "error", 
                "reason": f"Error checking EXIF data: {str(e)}",
                "exif_present": False
            }
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        try:
            # Clean the path by removing surrounding quotes if present
            clean_path = image_path.strip().strip('"').strip("'")
            
            # Check if file exists
            if not os.path.exists(clean_path):
                print(f"Image file not found: {clean_path}")
                return ""
            
            with open(clean_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image: {e}")
            return ""
    
    def _get_visual_summary_from_image_with_fallback(self, image_path: str) -> str:
        """
        Generate visual summary from an image using SambaNova API with fallback keys.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Visual summary description
        """
        # Try each API key in sequence until one works
        for i, api_key in enumerate(self.sambanova_api_keys):
            try:
                print(f"Trying SambaNova API key {i+1}/{len(self.sambanova_api_keys)}...")
                
                # Encode the image
                base64_image = self._encode_image(image_path)
                
                if not base64_image:
                    return "Failed to encode image."
                
                # Prepare the API request with the specified model
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Provide a detailed visual description of this image. Include information about the main subjects, colors, setting, objects, actions, and overall composition. Be thorough and descriptive."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
                
                # Make the API request
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    print(f"SambaNova API request failed with status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except Exception as e:
                print(f"Error with SambaNova API key {i+1}: {e}")
                continue
        
        return "Failed to generate visual summary with all available API keys."
    
    def get_visual_summary(self, image_path: str) -> Dict[str, str]:
        """
        Main method to get visual summary for an image with AI-generated detection.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Visual summary in JSON format
        """
        # First, check EXIF data for AI generation indicators
        print("Checking EXIF data for AI generation indicators...")
        exif_result = self._check_exif_data(image_path)
        
        # If EXIF data is suspicious or missing, use Hugging Face for detection
        if exif_result.get("status") == "suspicious" or not exif_result.get("exif_present"):
            print("Suspicious or missing EXIF data found. Checking with Hugging Face...")
            hf_result = self._detect_ai_generated_hf(image_path)
            
            if hf_result.get("status") == "ai-generated":
                print("AI-generated image detected. Skipping visual summary generation.")
                return {
                    "visual_summary": "Image detected as AI-generated based on EXIF data analysis and Hugging Face detection. Visual summary generation skipped for security reasons.",
                    "exif_analysis": exif_result,
                    "ai_detection": hf_result
                }
        
        # If no clear AI indicators, proceed with visual summary
        print("No clear AI indicators found. Generating visual summary...")
        summary_text = self._get_visual_summary_from_image_with_fallback(image_path)
        
        result = {
            "visual_summary": summary_text
        }
        
        # Include analysis results
        result["exif_analysis"] = exif_result
        
        # Include Hugging Face detection if it was performed
        if 'hf_result' in locals():
            result["ai_detection"] = hf_result
        
        return result
    
    def get_visual_summary_from_bytes(self, image_bytes: bytes, filename: str = "temp_image.jpg") -> Dict[str, str]:
        """
        Get visual summary from image bytes (for handling multipart form data from frontend).
        
        Args:
            image_bytes: Image data as bytes
            filename: Temporary filename to use
            
        Returns:
            Visual summary in JSON format
        """
        # Save bytes to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(image_bytes)
            tmp_file_path = tmp_file.name
        
        try:
            # Process the temporary file
            result = self.get_visual_summary(tmp_file_path)
            return result
        finally:
            # Clean up the temporary file
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                print(f"Warning: Could not delete temporary file {tmp_file_path}: {e}")
    
    def run_interactive(self):
        """
        Run the agent in interactive mode, accepting image path from terminal.
        """
        print("=== Visual Summary Agent ===")
        print("Enter the path to an image file to get a visual summary.")
        print("Supported formats: JPEG, PNG, etc.")
        
        while True:
            try:
                image_path = input("\nEnter image path (or 'quit' to exit): ")
                
                if image_path.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if not image_path.strip():
                    print("Please enter a valid image path.")
                    continue
                
                print("\nProcessing image...")
                result = self.get_visual_summary(image_path)
                
                # Pretty print the JSON result
                print("\n" + "="*50)
                print("RESULTS:")
                print("="*50)
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                print("="*50)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                print("Please try again with a different image.")


# Example usage
if __name__ == "__main__":
    # Get API keys from environment variables
    SAMBANOVA_API_KEYS = [
        os.getenv("SAMBANOVA_API_KEY_1"),
        os.getenv("SAMBANOVA_API_KEY_2"),
        os.getenv("SAMBANOVA_API_KEY_3"),
        os.getenv("SAMBANOVA_API_KEY_4")
    ]
    # Filter out None values
    SAMBANOVA_API_KEYS = [key for key in SAMBANOVA_API_KEYS if key]
    
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    
    # Create the agent
    agent = VisualSummaryAgent(
        sambanova_api_keys=SAMBANOVA_API_KEYS,
        huggingface_api_key=HUGGINGFACE_API_KEY
    )
    
    # Run in interactive mode
    agent.run_interactive()