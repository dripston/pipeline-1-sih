# Weather and Visual Summary Agents

This repository contains two AI agents designed for different purposes:

1. **Weather Agent**: Fetches weather data based on latitude and longitude coordinates
2. **Visual Summary Agent**: Generates detailed visual descriptions from images

## Weather Agent

A weather agent that takes latitude and longitude coordinates, converts them to human-readable addresses using OpenStreetMap, fetches weather data from Open-Meteo API, and generates a detailed summary in JSON format.

### Features

- Takes latitude and longitude as input from terminal
- Converts coordinates to human-readable addresses using OpenStreetMap
- Fetches comprehensive weather data from Open-Meteo API (free and reliable)
- Generates detailed weather summaries with multiple weather parameters
- Outputs structured JSON for easy integration with other agents
- Includes fallback data sources (US National Weather Service, WeatherAPI.com)
- Suitable for integration with multi-agent systems

### Usage

Run the weather agent:

```bash
python weather_agent.py
```

Then enter the latitude and longitude when prompted.

## Visual Summary Agent

An AI agent that generates detailed visual descriptions from images using the SambaNova API.

### Features

- Takes image file path as input
- Generates comprehensive visual summaries using SambaNova's Llama 3.2 90B Vision model
- Outputs structured JSON with detailed image descriptions
- Suitable for integration with other agents in a multi-agent system

### Usage

Run the visual summary agent:

```bash
python visual_summary_agent.py
```

Then enter the path to an image file when prompted.

## Reasoning Engine

The main reasoning engine that combines both agents to analyze disaster situations:

1. Takes an image and GPS coordinates as input
2. Analyzes the image to determine if it's related to weather emergencies
3. Fetches weather data for the location
4. Generates emergency response reports using SambaNova API

### Features

- Accepts image uploads and GPS data from frontend
- Multiple SambaNova API key fallbacks for reliability
- AI-generated image detection to prevent processing fake images
- Emergency situation filtering to focus on real disasters
- Generates structured reports for authorities, public, and volunteers

## Deployment on Render

This application is ready for deployment on Render with the following configuration:

### Environment Variables

Set these environment variables in your Render dashboard:

- `SAMBANOVA_API_KEY_1`: First SambaNova API key (primary)
- `SAMBANOVA_API_KEY_2`: Second SambaNova API key (fallback)
- `SAMBANOVA_API_KEY_3`: Third SambaNova API key (fallback)
- `SAMBANOVA_API_KEY_4`: Fourth SambaNova API key (fallback)
- `WEATHERAPI_KEY`: WeatherAPI key (optional, for additional weather data)
- `HUGGINGFACE_API_KEY`: Hugging Face API key (optional, for AI image detection)
- `PORT`: Port for the web server (Render will set this automatically)

### Render Configuration

1. Create a new Web Service on Render
2. Connect your repository
3. Set the build command to:
   ```
   pip install -r requirements.txt
   ```
4. Set the start command to:
   ```
   python main.py
   ```
5. Add the environment variables in the Render dashboard
6. Deploy!

### API Endpoints

Once deployed, the application exposes the following endpoints:

- `GET /`: Health check endpoint
- `POST /process`: Main processing endpoint that accepts:
  - `image`: Multipart form file upload
  - `gps`: JSON string with GPS coordinates in the format:
    ```json
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
    ```

## Requirements

- Python 3.8+
- Internet connection
- API keys for services used (SambaNova for visual summary agent)

## Installation

1. Clone this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

## API Keys

- **SambaNova**: Required for the visual summary agent and reasoning engine
  - Multiple API keys can be configured for fallback reliability
  - Replace the placeholders in the environment variables with your actual API keys

## Integration with Other Agents

Both agents are designed for easy integration into multi-agent systems:

1. The agents accept inputs as parameters
2. They return structured JSON output
3. The output can be used by other agents for decision making

Example integration:
```python
from weather_agent import WeatherAgent
from visual_summary_agent import VisualSummaryAgent

# Weather agent
weather_agent = WeatherAgent()
weather_result = weather_agent.get_weather_summary(latitude=12.9629, longitude=77.5775)

# Visual summary agent
visual_agent = VisualSummaryAgent(sambanova_api_key="your-api-key")
visual_result = visual_agent.get_visual_summary(image_path="path/to/image.jpg")
```

## License

This project is licensed under the MIT License.