import json
import requests
import os
import uvicorn
from typing import Dict, Any
from dotenv import load_dotenv
from weather_agent import WeatherAgent
from visual_summary_agent import VisualSummaryAgent

# Load environment variables
load_dotenv()

class ReasoningEngine:
    def __init__(self):
        # Load API keys from environment variables with fallbacks
        self.weatherapi_key = os.getenv("WEATHERAPI_KEY")
        self.sambanova_api_keys = [
            os.getenv("SAMBANOVA_API_KEY_1"),
            os.getenv("SAMBANOVA_API_KEY_2"),
            os.getenv("SAMBANOVA_API_KEY_3"),
            os.getenv("SAMBANOVA_API_KEY_4")
        ]
        # Filter out None values
        self.sambanova_api_keys = [key for key in self.sambanova_api_keys if key]
        
        # Initialize agents with environment variables
        self.weather_agent = WeatherAgent(weatherapi_key=self.weatherapi_key)
        self.visual_agent = VisualSummaryAgent(
            sambanova_api_keys=self.sambanova_api_keys,
            huggingface_api_key=os.getenv("HUGGINGFACE_API_KEY")
        )
        self.reasoning_model = "Llama-4-Maverick-17B-128E-Instruct"

    def is_screen_capture(self, visual_summary):
        """Simple check if visual summary indicates screen capture"""
        if not visual_summary:
            return False
            
        visual_lower = visual_summary.lower()
        
        # Direct screen indicators
        screen_keywords = [
            'screen', 'tablet', 'phone', 'device', 'displayed on', 'shown on',
            'captured on', 'photograph of a screen', 'image of a screen'
        ]
        
        return any(keyword in visual_lower for keyword in screen_keywords)

    def is_weather_emergency_related(self, visual_summary):
        """Check if content is related to weather emergencies"""
        if not visual_summary:
            return False
            
        visual_lower = visual_summary.lower()
        
        # Weather and emergency related keywords
        weather_keywords = [
            'flood', 'rain', 'storm', 'hurricane', 'cyclone', 'typhoon', 'tornado',
            'landslide', 'earthquake', 'tsunami', 'wildfire', 'blizzard', 'hail',
            'lightning', 'thunder', 'precipitation', 'downpour', 'deluge',
            'submerged', 'inundated', 'water level', 'high water', 'rising water'
        ]
        
        emergency_keywords = [
            'disaster', 'emergency', 'damage', 'destroyed', 'evacuation', 'rescue',
            'stranded', 'trapped', 'emergency services', 'first responders',
            'devastation', 'catastrophe', 'crisis', 'alert', 'warning'
        ]
        
        # Must have at least one weather keyword AND one emergency keyword
        has_weather = any(keyword in visual_lower for keyword in weather_keywords)
        has_emergency = any(keyword in visual_lower for keyword in emergency_keywords)
        
        return has_weather and has_emergency

    def should_process_image(self, visual_summary):
        """Determine if we should process this image for emergency response"""
        if self.is_screen_capture(visual_summary):
            print("❌ Image appears to be a screen capture - stopping processing")
            return False
            
        if not self.is_weather_emergency_related(visual_summary):
            print("❌ Image not related to weather emergencies - stopping processing")
            return False
            
        return True

    def generate_reports(self, visual_summary, weather_summary, location_name):
        """Generate intelligent emergency reports that correlate weather and visual data"""
        # Try each SambaNova API key until one works
        for i, api_key in enumerate(self.sambanova_api_keys):
            try:
                print(f"Trying SambaNova API key {i+1}/{len(self.sambanova_api_keys)}...")

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                # First, generate trust evaluation
                trust_prompt = f"""
                Evaluate the reliability and trustworthiness of this emergency report data:

                VISUAL ANALYSIS: {visual_summary}
                WEATHER DATA: {weather_summary}
                LOCATION: {location_name}

                Provide a trust score from 0-100 and brief reasoning considering:
                - Data consistency between visual and weather information
                - Information quality and specificity
                - Potential reliability concerns

                Format: Score: [number], Reasoning: [brief explanation]
                """

                trust_payload = {
                    "model": self.reasoning_model,
                    "messages": [{"role": "user", "content": trust_prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3
                }

                trust_response = requests.post(
                    "https://api.sambanova.ai/v1/chat/completions",
                    headers=headers,
                    json=trust_payload,
                    timeout=15
                )

                trust_score = 75  # default
                trust_reasoning = "Standard reliability assessment"

                if trust_response.status_code == 200:
                    trust_content = trust_response.json()["choices"][0]["message"]["content"]
                    # Extract score from response
                    import re
                    score_match = re.search(r'Score:\s*(\d+)', trust_content, re.IGNORECASE)
                    if score_match:
                        trust_score = min(max(int(score_match.group(1)), 0), 100)
                    trust_reasoning = trust_content

                # Now generate correlated reports
                prompt = f"""
                Generate intelligent emergency response reports that SPECIFICALLY correlate the weather and visual data:

                VISUAL ANALYSIS: {visual_summary}
                WEATHER CONDITIONS: {weather_summary}
                LOCATION: {location_name}
                TRUST SCORE: {trust_score}/100 ({trust_reasoning})

                IMPORTANT: Your reports must directly reference and correlate specific details from BOTH the visual analysis and weather data. Do not generate generic reports.

                Generate three data-driven reports:

                1. AUTHORITY REPORT: For emergency responders - reference specific weather conditions, visual damage assessment, immediate risks based on the actual data, and location-specific resource needs.

                2. PUBLIC ALERT: For residents - correlate current weather patterns with observed flooding/damage, provide location-specific safety instructions based on the actual conditions.

                3. VOLUNTEER GUIDANCE: For helpers - reference specific visual elements (buildings affected, people locations) and weather conditions to guide targeted assistance.

                Each report must demonstrate understanding of how the weather conditions are causing or exacerbating the visual situation. Include the trust score context in authority report.
                """

                payload = {
                    "model": self.reasoning_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.4
                }

                response = requests.post(
                    "https://api.sambanova.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"]

                    reports = {
                        "authority_report": self._extract_section(content, "AUTHORITY REPORT"),
                        "public_alert": self._extract_section(content, "PUBLIC ALERT"),
                        "volunteer_guidance": self._extract_section(content, "VOLUNTEER GUIDANCE")
                    }

                    # Add trust evaluation to the response
                    reports["trust_evaluation"] = {
                        "score": trust_score,
                        "reasoning": trust_reasoning
                    }

                    return reports
                else:
                    print(f"SambaNova API request failed with status code: {response.status_code}")
                    print(f"Response: {response.text}")

            except Exception as e:
                print(f"Error with SambaNova API key {i+1}: {e}")
                continue

        return {"error": "Failed to generate reports with all available API keys"}

    def _extract_section(self, content, section_name):
        """Extract a specific section from the response"""
        lines = content.split('\n')
        section_lines = []
        in_section = False

        for line in lines:
            if section_name in line.upper():
                in_section = True
                continue
            elif in_section and any(header in line.upper() for header in 
                                   ["AUTHORITY REPORT", "PUBLIC ALERT", "VOLUNTEER GUIDANCE"]) and line.strip():
                break
            elif in_section:
                section_lines.append(line)

        return '\n'.join(section_lines).strip()

    def process_request(self, image_path, latitude, longitude):
        """Main processing function - simplified and focused"""
        print("Processing your request...")

        # Get visual summary first to decide if we should proceed
        print("Analyzing image content...")
        visual_result = self.visual_agent.get_visual_summary(image_path)
        visual_summary = visual_result.get("visual_summary", "")

        # Check if we should process this image
        if not self.should_process_image(visual_summary):
            return {
                "status": "REJECTED",
                "reason": "Image is either a screen capture or not related to weather emergencies",
                "visual_summary": visual_summary,
                "screen_capture_detected": self.is_screen_capture(visual_summary),
                "weather_emergency_related": self.is_weather_emergency_related(visual_summary)
            }

        # Only proceed if it's a valid emergency situation
        print("✅ Valid emergency situation detected - proceeding...")

        # Get weather data
        print("Fetching weather data...")
        weather_result = self.weather_agent.get_weather_summary(latitude, longitude)
        weather_summary = weather_result.get("weather_agent_summary", "Weather data unavailable")

        # Get location name
        location_name = self.weather_agent._get_location_name(latitude, longitude)

        # Generate reports
        print("Generating emergency reports...")
        reports = self.generate_reports(visual_summary, weather_summary, location_name)

        return {
            "status": "PROCESSED",
            "location": location_name,
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "weather_summary": weather_summary,
            "visual_summary": visual_summary,
            "reports": reports
        }

    def process_frontend_request(self, image_bytes: bytes, gps_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process request from frontend with multipart form data and GPS JSON.
        
        Args:
            image_bytes: Image data uploaded from frontend
            gps_data: GPS data in the format:
                {
                  "coords": {
                    "latitude": 12.9715987,
                    "longitude": 77.5945627,
                    "altitude": null,
                    "accuracy": 25,
                    "altitudeAccuracy": null,
                    "heading": null,
                    "speed": null
                  },
                  "timestamp": 1675343423000
                }
                
        Returns:
            Processed result in JSON format
        """
        try:
            # Extract coordinates from GPS data
            coords = gps_data.get("coords", {})
            latitude = coords.get("latitude")
            longitude = coords.get("longitude")
            
            if latitude is None or longitude is None:
                return {
                    "status": "ERROR",
                    "message": "Invalid GPS data: missing latitude or longitude"
                }
            
            # Process image using visual agent
            print("Analyzing image content from frontend...")
            visual_result = self.visual_agent.get_visual_summary_from_bytes(image_bytes)
            visual_summary = visual_result.get("visual_summary", "")
            
            # Check if we should process this image
            if not self.should_process_image(visual_summary):
                return {
                    "status": "REJECTED",
                    "reason": "Image is either a screen capture or not related to weather emergencies",
                    "visual_summary": visual_summary,
                    "screen_capture_detected": self.is_screen_capture(visual_summary),
                    "weather_emergency_related": self.is_weather_emergency_related(visual_summary)
                }
            
            # Only proceed if it's a valid emergency situation
            print("✅ Valid emergency situation detected - proceeding...")
            
            # Get weather data
            print("Fetching weather data...")
            weather_result = self.weather_agent.get_weather_summary(latitude, longitude)
            weather_summary = weather_result.get("weather_agent_summary", "Weather data unavailable")
            
            # Get location name
            location_name = self.weather_agent._get_location_name(latitude, longitude)
            
            # Generate reports
            print("Generating emergency reports...")
            reports = self.generate_reports(visual_summary, weather_summary, location_name)
            
            return {
                "status": "PROCESSED",
                "location": location_name,
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "timestamp": gps_data.get("timestamp"),
                "weather_summary": weather_summary,
                "visual_summary": visual_summary,
                "trust_evaluation": reports.get("trust_evaluation", {"score": 75, "reasoning": "Default assessment"}),
                "reports": {
                    "authority_report": reports.get("authority_report", ""),
                    "public_alert": reports.get("public_alert", ""),
                    "volunteer_guidance": reports.get("volunteer_guidance", "")
                }
            }
            
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Failed to process request: {str(e)}"
            }

    def get_user_input(self):
        """Get image path and GPS coordinates from user"""
        print("=== Disaster Response Reasoning Engine ===")
        print("Please provide the following information:")

        image_path = input("Enter image path: ").strip()
        latitude = float(input("Enter latitude: "))
        longitude = float(input("Enter longitude: "))

        return image_path, latitude, longitude

    def run_interactive(self):
        """Run in interactive mode"""
        try:
            image_path, latitude, longitude = self.get_user_input()
            result = self.process_request(image_path, latitude, longitude)

            print("\n" + "="*60)
            print("RESULTS:")
            print("="*60)
            print(json.dumps(result, indent=2, ensure_ascii=False))

        except KeyboardInterrupt:
            print("\nExiting...")
        except Exception as e:
            print(f"An error occurred: {e}")

# For deployment on Render, we'll create a FastAPI app
def create_app():
    from fastapi import FastAPI, File, UploadFile, Form
    import tempfile
    
    app = FastAPI(title="Disaster Response Reasoning Engine")
    engine = ReasoningEngine()
    
    @app.get("/")
    async def root():
        return {
            "message": "Disaster Response Reasoning Engine API", 
            "status": "running"
        }
    
    @app.post("/process")
    async def process_disaster_report(
        image: UploadFile = File(...),
        gps: str = Form(...)
    ):
        """
        Process disaster report from frontend.
        
        Args:
            image: Uploaded image file
            gps: GPS data as JSON string in the format:
                {
                  "coords": {
                    "latitude": 12.9715987,
                    "longitude": 77.5945627,
                    "altitude": null,
                    "accuracy": 25,
                    "altitudeAccuracy": null,
                    "heading": null,
                    "speed": null
                  },
                  "timestamp": 1675343423000
                }
        """
        try:
            # Parse GPS data
            gps_data = json.loads(gps)
            
            # Read image bytes
            image_bytes = await image.read()
            
            # Process the request
            result = engine.process_frontend_request(image_bytes, gps_data)
            
            return result
            
        except json.JSONDecodeError:
            return {
                "status": "ERROR",
                "message": "Invalid GPS data format. Must be valid JSON."
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Failed to process request: {str(e)}"
            }
    
    return app

if __name__ == "__main__":
    # Check if running in deployment mode (Render sets PORT environment variable)
    port = int(os.getenv("PORT", 8000))
    
    # Create and run the FastAPI app
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port)