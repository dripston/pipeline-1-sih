import os
import requests
import json
import sys
from typing import Dict, Any
from geopy.geocoders import Nominatim


class WeatherAgent:
    def __init__(self, weatherapi_key: str = None):
        """
        Initialize the weather agent with required services.
        
        Args:
            weatherapi_key: API key for WeatherAPI.com (optional)
        """
        self.geolocator = Nominatim(user_agent="weather_agent")
        self.weatherapi_key = weatherapi_key or os.getenv("WEATHERAPI_KEY")
        self.primary_weather_api = "open-meteo"
    
    def _get_location_name(self, latitude: float, longitude: float) -> str:
        """
        Convert coordinates to human readable address using OpenStreetMap.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Human readable address
        """
        try:
            location = self.geolocator.reverse(f"{latitude}, {longitude}")
            # Clean up the address to make it more readable
            if location and location.address:
                # Take only the first part of the address for brevity
                address_parts = location.address.split(',')
                if len(address_parts) > 3:
                    return ', '.join(address_parts[:3]) + ', ' + address_parts[-1]  # Include city and country
                return location.address
            return "Unknown location"
        except Exception as e:
            print(f"Error getting location name: {e}")
            return "Unknown location"
    
    def _get_weather_data_open_meteo(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch weather data from Open-Meteo API.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Weather data dictionary
        """
        try:
            # Open-Meteo API endpoint
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,pressure_msl,wind_direction_10m,cloud_cover",
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,precipitation_probability",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_sum,wind_speed_10m_max",
                "timezone": "auto"
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Open-Meteo API request failed with status code: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"Error fetching weather data from Open-Meteo: {e}")
            return {}
    
    def _get_weather_data_weather_gov(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch weather data from US National Weather Service API.
        Note: This service works best for US locations.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Weather data dictionary
        """
        try:
            # US National Weather Service API endpoint
            url = f"https://api.weather.gov/points/{latitude},{longitude}"
            
            # First get the forecast URL
            response = requests.get(url, timeout=10, headers={"User-Agent": "WeatherAgent/1.0"})
            
            if response.status_code == 200:
                point_data = response.json()
                forecast_url = point_data["properties"]["forecast"]
                
                # Get the forecast data
                forecast_response = requests.get(forecast_url, timeout=10, headers={"User-Agent": "WeatherAgent/1.0"})
                
                if forecast_response.status_code == 200:
                    forecast_data = forecast_response.json()
                    return {
                        "source": "weather_gov",
                        "point_data": point_data,
                        "forecast_data": forecast_data
                    }
                else:
                    print(f"Weather.gov forecast API request failed with status code: {forecast_response.status_code}")
                    return {}
            else:
                print(f"Weather.gov points API request failed with status code: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"Error fetching weather data from Weather.gov: {e}")
            return {}
    
    def _get_weather_data_weatherapi(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch weather data from WeatherAPI.com.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Weather data dictionary
        """
        weatherapi_key = self.weatherapi_key or os.getenv("WEATHERAPI_KEY")
        
        if not weatherapi_key:
            print("WeatherAPI key not provided, skipping this source.")
            return {}
        
        try:
            # WeatherAPI.com endpoint
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                "key": weatherapi_key,
                "q": f"{latitude},{longitude}",
                "aqi": "no"
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                data["source"] = "weatherapi"
                return data
            else:
                print(f"WeatherAPI request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return {}
                
        except Exception as e:
            print(f"Error fetching weather data from WeatherAPI: {e}")
            return {}
    
    def _get_weather_data(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch weather data from multiple sources with fallback.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Weather data dictionary
        """
        # Try primary source (Open-Meteo)
        print("Fetching weather data from Open-Meteo...")
        weather_data = self._get_weather_data_open_meteo(latitude, longitude)
        
        if weather_data:
            weather_data["source"] = "open-meteo"
            return weather_data
        
        # Fallback to US National Weather Service (works best for US locations)
        print("Falling back to US National Weather Service...")
        weather_data = self._get_weather_data_weather_gov(latitude, longitude)
        
        if weather_data:
            return weather_data
        
        # Final fallback to WeatherAPI.com
        print("Falling back to WeatherAPI.com...")
        weather_data = self._get_weather_data_weatherapi(latitude, longitude)
        
        if weather_data:
            return weather_data
        
        # If all sources fail, return empty data
        print("All weather data sources failed.")
        return {}
    
    def _weather_code_to_description(self, weather_code: int) -> str:
        """
        Convert weather code to descriptive text.
        
        Args:
            weather_code: Weather code from Open-Meteo
            
        Returns:
            Descriptive weather text
        """
        weather_descriptions = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "fog",
            48: "depositing rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            56: "light freezing drizzle",
            57: "dense freezing drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            66: "light freezing rain",
            67: "heavy freezing rain",
            71: "slight snow fall",
            73: "moderate snow fall",
            75: "heavy snow fall",
            77: "snow grains",
            80: "slight rain showers",
            81: "moderate rain showers",
            82: "violent rain showers",
            85: "slight snow showers",
            86: "heavy snow showers",
            95: "thunderstorm",
            96: "thunderstorm with slight hail",
            99: "thunderstorm with heavy hail"
        }
        return weather_descriptions.get(weather_code, "unknown weather condition")
    
    def _format_weather_summary_open_meteo(self, location_name: str, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data from Open-Meteo into a detailed natural language summary.
        
        Args:
            location_name: Human readable location name
            weather_data: Raw weather data from Open-Meteo API
            
        Returns:
            Formatted weather summary as a detailed paragraph
        """
        if not weather_data or "current" not in weather_data:
            return "Unable to generate weather summary due to missing data."
        
        try:
            current = weather_data["current"]
            daily = weather_data.get("daily", {})
            
            # Extract key current weather information
            temperature = current.get("temperature_2m", "N/A")
            humidity = current.get("relative_humidity_2m", "N/A")
            wind_speed = current.get("wind_speed_10m", "N/A")
            wind_direction = current.get("wind_direction_10m", "N/A")
            pressure = current.get("pressure_msl", "N/A")
            cloud_cover = current.get("cloud_cover", "N/A")
            weather_code = current.get("weather_code", 0)
            weather_description = self._weather_code_to_description(weather_code)
            
            # Get daily min/max temperatures if available
            temp_max = daily.get("temperature_2m_max", [None])[0] if daily.get("temperature_2m_max") else "N/A"
            temp_min = daily.get("temperature_2m_min", [None])[0] if daily.get("temperature_2m_min") else "N/A"
            
            # Get precipitation information
            precipitation_sum = daily.get("precipitation_sum", [None])[0] if daily.get("precipitation_sum") else "N/A"
            wind_speed_max = daily.get("wind_speed_10m_max", [None])[0] if daily.get("wind_speed_10m_max") else "N/A"
            
            # Get sunrise and sunset times
            sunrise = daily.get("sunrise", [None])[0] if daily.get("sunrise") else "N/A"
            sunset = daily.get("sunset", [None])[0] if daily.get("sunset") else "N/A"
            
            # Format sunrise/sunset times
            if sunrise != "N/A":
                sunrise = sunrise.split("T")[1][:5]  # Extract time part
            if sunset != "N/A":
                sunset = sunset.split("T")[1][:5]  # Extract time part
            
            # Create a detailed natural language summary
            summary = (
                f"The current weather at {location_name} is characterized by {weather_description} conditions "
                f"with a temperature of {temperature} degrees Celsius. The relative humidity is at {humidity} percent, "
                f"and there is a cloud cover of {cloud_cover} percent.\n\n"
                f"The atmospheric pressure is {pressure} hPa, indicating stable weather patterns. "
                f"Wind conditions show speeds of {wind_speed} meters per second coming from a {wind_direction} degree direction. "
                f"Today's maximum wind speed is expected to reach {wind_speed_max} meters per second.\n\n"
                f"The daily temperature range shows a high of {temp_max} degrees Celsius and a low of {temp_min} degrees Celsius. "
                f"Total precipitation for the day is forecasted to be {precipitation_sum} millimeters.\n\n"
                f"Daylight hours today extend from sunrise at {sunrise} to sunset at {sunset}. "
                f"This weather pattern suggests comfortable conditions for outdoor activities, though "
                f"the wind may require consideration for light outdoor items."
            )
            
            return summary.strip()
            
        except Exception as e:
            print(f"Error formatting weather summary: {e}")
            return "Unable to generate weather summary due to formatting error."
    
    def _format_weather_summary_weather_gov(self, location_name: str, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data from US National Weather Service into a summary.
        
        Args:
            location_name: Human readable location name
            weather_data: Raw weather data from Weather.gov API
            
        Returns:
            Formatted weather summary as a detailed paragraph
        """
        if not weather_data or "forecast_data" not in weather_data:
            return "Unable to generate weather summary due to missing data."
        
        try:
            # Extract current weather from forecast data
            periods = weather_data["forecast_data"]["properties"]["periods"]
            if not periods:
                return "Unable to generate weather summary due to missing forecast data."
            
            # Get current period (first in the list)
            current_period = periods[0]
            
            # Extract key information
            temperature = current_period.get("temperature", "N/A")
            temperature_unit = current_period.get("temperatureUnit", "F")
            wind_speed = current_period.get("windSpeed", "N/A")
            wind_direction = current_period.get("windDirection", "N/A")
            short_forecast = current_period.get("shortForecast", "N/A")
            detailed_forecast = current_period.get("detailedForecast", "N/A")
            
            # Create a summary
            summary = (
                f"The current weather at {location_name} is characterized by {short_forecast.lower()} conditions "
                f"with a temperature of {temperature} degrees {temperature_unit}. "
                f"Wind conditions show speeds of {wind_speed} coming from a {wind_direction} direction.\n\n"
                f"Forecast details: {detailed_forecast}"
            )
            
            return summary.strip()
            
        except Exception as e:
            print(f"Error formatting weather summary: {e}")
            return "Unable to generate weather summary due to formatting error."
    
    def _format_weather_summary_weatherapi(self, location_name: str, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data from WeatherAPI.com into a summary.
        
        Args:
            location_name: Human readable location name
            weather_data: Raw weather data from WeatherAPI.com
            
        Returns:
            Formatted weather summary as a detailed paragraph
        """
        if not weather_data or "current" not in weather_data:
            return "Unable to generate weather summary due to missing data."
        
        try:
            current = weather_data["current"]
            
            # Extract key information
            temperature = current.get("temp_c", "N/A")
            humidity = current.get("humidity", "N/A")
            wind_speed = current.get("wind_kph", "N/A")
            wind_direction = current.get("wind_degree", "N/A")
            wind_direction_text = current.get("wind_dir", "N/A")
            pressure = current.get("pressure_mb", "N/A")
            cloud_cover = current.get("cloud", "N/A")
            condition = current.get("condition", {}).get("text", "N/A")
            feels_like = current.get("feelslike_c", "N/A")
            
            # Create a summary
            summary = (
                f"The current weather at {location_name} is characterized by {condition.lower()} conditions "
                f"with a temperature of {temperature} degrees Celsius (feels like {feels_like} degrees). "
                f"The relative humidity is at {humidity} percent, and there is a cloud cover of {cloud_cover} percent.\n\n"
                f"The atmospheric pressure is {pressure} mb. Wind conditions show speeds of {wind_speed} kilometers per hour "
                f"coming from a {wind_direction} degree direction ({wind_direction_text}).\n\n"
                f"This weather pattern suggests comfortable conditions for outdoor activities."
            )
            
            return summary.strip()
            
        except Exception as e:
            print(f"Error formatting weather summary: {e}")
            return "Unable to generate weather summary due to formatting error."
    
    def _format_weather_summary(self, location_name: str, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data into a detailed natural language summary based on the data source.
        
        Args:
            location_name: Human readable location name
            weather_data: Raw weather data from API
            
        Returns:
            Formatted weather summary as a detailed paragraph
        """
        source = weather_data.get("source", "open-meteo")
        
        if source == "open-meteo":
            return self._format_weather_summary_open_meteo(location_name, weather_data)
        elif source == "weather_gov":
            return self._format_weather_summary_weather_gov(location_name, weather_data)
        elif source == "weatherapi":
            return self._format_weather_summary_weatherapi(location_name, weather_data)
        else:
            # Default formatting
            return self._format_weather_summary_open_meteo(location_name, weather_data)
    
    def get_weather_summary(self, latitude: float, longitude: float) -> Dict[str, str]:
        """
        Main method to get weather summary for given coordinates.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Weather summary in JSON format
        """
        # Get location name
        location_name = self._get_location_name(latitude, longitude)
        
        # Get weather data
        weather_data = self._get_weather_data(latitude, longitude)
        
        # Generate summary
        summary_text = self._format_weather_summary(location_name, weather_data)
        
        # Return in JSON format
        return {
            "weather_agent_summary": summary_text
        }
    
    def run_interactive(self):
        """
        Run the agent in interactive mode, accepting latitude and longitude from terminal.
        """
        print("=== Weather Agent ===")
        print("Enter latitude and longitude to get weather information.")
        
        try:
            latitude = float(input("Enter latitude: "))
            longitude = float(input("Enter longitude: "))
            
            result = self.get_weather_summary(latitude, longitude)
            # Use json.dumps with ensure_ascii=False to prevent Unicode escaping
            print("\n" + json.dumps(result, indent=2, ensure_ascii=False))
            
        except ValueError:
            print("Invalid input. Please enter valid numbers for latitude and longitude.")
        except KeyboardInterrupt:
            print("\nExiting...")
        except Exception as e:
            print(f"An error occurred: {e}")


# Example usage
if __name__ == "__main__":
    # Create the agent (replace with your actual WeatherAPI key if you have one)
    WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY", "5b9f3eb5d5f34729b6f140342252309")
    agent = WeatherAgent(weatherapi_key=WEATHERAPI_KEY)
    
    # Run in interactive mode
    agent.run_interactive()